"""
monitoring/monitor_service.py — Central polling coordinator.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from config import CUConfig, RNConfig
from connection.mock_connection import MockConnection
from connection.paramiko_stub import ParamikoConnection
from events.event_manager import EventManager
from models.node import RNState
from parser.cli_parser import (
    parse_pci,
    parse_state,
    parse_uptime,
    parse_rn_statuses,
    parse_cell_pcis,
    parse_radionode_table,
    parse_cell_table
)
from state.state_manager import StateManager

if TYPE_CHECKING:
    from config import CUConfig, Settings
    from websocket.ws_manager import WebSocketManager
    from database.db_manager import DBManager

logger = logging.getLogger(__name__)


def compute_node_status(oper_state: str, uptime_sec: int, previous_state: RNState | None) -> str:
    """
    Determine Node Status according to rules:
    - OOS: If OperState starts with or contains OOS (e.g. OOS-INIT, OOS-NOTPRESENT).
    - REBOOTED: If working node (e.g. IS-NORMAL) has reduced uptime compared to previous poll.
    - HEALTHY: Working node with normal/increasing uptime.
    """
    oper_state_upper = oper_state.upper()
    if "OOS" in oper_state_upper:
        return "OOS"
        
    # If not OOS, it's operational
    if previous_state and previous_state.node_state in ("HEALTHY", "REBOOTED"):
        if uptime_sec < previous_state.uptime_seconds:
            return "REBOOTED"
            
    return "HEALTHY"


class MonitorService:
    def __init__(
        self,
        settings: Settings,
        state_manager: StateManager,
        event_manager: EventManager,
        ws_manager: WebSocketManager,
        db_manager: DBManager,
    ) -> None:
        self._settings = settings
        self._state = state_manager
        self._events = event_manager
        self._ws = ws_manager
        self._db = db_manager
        self._settings_lock = threading.Lock()

    def poll_all(self) -> None:
        logger.info("=== Poll cycle start ===")
        with self._settings_lock:
            cus = list(self._settings.cus)
        with ThreadPoolExecutor(max_workers=self._settings.max_workers) as pool:
            futures = {
                pool.submit(self._poll_cu, cu): cu
                for cu in cus
            }
            for future in as_completed(futures):
                cu = futures[future]
                try:
                    future.result()
                except Exception:
                    logger.exception("Error polling CU %s", cu.name)

        self._broadcast_state()
        logger.info("=== Poll cycle end ===")

    def discover_and_add_cu(self, cu_ip: str, cu_name: str | None = None) -> CUConfig:
        """Discover a CU's connected RNs over SSH and add it to the poll list."""
        normalized_ip = cu_ip.strip()
        if not normalized_ip:
            raise ValueError("CU IP is required")

        with self._settings_lock:
            if any(cu.ip == normalized_ip for cu in self._settings.cus):
                raise ValueError(f"CU {normalized_ip} is already registered")

        discovered = self._discover_remote_cu(normalized_ip, cu_name)

        with self._settings_lock:
            self._settings.cus.append(discovered)

        return discovered

    def remove_cu(self, cu_ip: str) -> CUConfig:
        """Remove a CU from polling and clear its current state."""
        normalized_ip = cu_ip.strip()
        if not normalized_ip:
            raise ValueError("CU IP is required")

        with self._settings_lock:
            for index, cu in enumerate(self._settings.cus):
                if cu.ip == normalized_ip:
                    removed = self._settings.cus.pop(index)
                    self._state.remove_cu(removed.name)
                    self._db.delete_current_status_by_cu(removed.name)
                    return removed

        raise ValueError(f"CU {normalized_ip} was not found")

    def _discover_remote_cu(self, cu_ip: str, cu_name: str | None = None) -> CUConfig:
        ssh_username = os.environ.get("SSH_USERNAME", "vboxuser")
        ssh_password = os.environ.get("SSH_PASSWORD", "123")
        remote_dir = os.environ.get("CU_SIMULATOR_DIR", "/home/vboxuser/cu_simulator")
        remote_script = os.environ.get("CU_SIMULATOR_SCRIPT", "cu_simulator.py")

        with ParamikoConnection(
            host=cu_ip,
            username=ssh_username,
            password=ssh_password,
            remote_command_template=(
                f"cd {remote_dir} && python3 {remote_script} {{command}}"
            ),
        ) as conn:
            raw_radionode = conn.execute("show radionode")

        rn_table = parse_radionode_table(raw_radionode)
        if not rn_table:
            raise ValueError(f"Could not discover any RNs from CU {cu_ip}")

        discovered_rns: list[RNConfig] = []
        for row in rn_table:
            rn_name = row.get("name") or f"RN-{row.get('rn_id', 'unknown')}"
            rn_ip = row.get("ip") or ""
            if rn_ip == "-":
                rn_ip = ""
            discovered_rns.append(RNConfig(name=rn_name, ip=rn_ip))

        resolved_name = (cu_name or "").strip() or f"CU-{cu_ip.replace('.', '-')}"
        return CUConfig(name=resolved_name, ip=cu_ip, rns=discovered_rns)

    def _poll_cu(self, cu: CUConfig) -> None:
        logger.debug("Polling CU %s (%s) — %d RNs", cu.name, cu.ip, len(cu.rns))

        if cu.ip.startswith("10.0."):
            # Legacy MockConnection logic
            for rn_cfg in cu.rns:
                self._poll_rn(cu.name, cu.name, cu.ip, rn_cfg.name, rn_cfg.ip)
            return

        # Real SSH polling logic
        try:
            ssh_username = os.environ.get("SSH_USERNAME", "vboxuser")
            ssh_password = os.environ.get("SSH_PASSWORD", "123")
            remote_dir = os.environ.get("CU_SIMULATOR_DIR", "/home/vboxuser/cu_simulator")
            remote_script = os.environ.get("CU_SIMULATOR_SCRIPT", "cu_simulator.py")

            conn = ParamikoConnection(
                host=cu.ip,
                username=ssh_username,
                password=ssh_password,
                remote_command_template=(
                    f"cd {remote_dir} && python3 {remote_script} {{command}}"
                ),
            )
            with conn:
                raw_radionode = conn.execute("show radionode")
                raw_cell_nr = conn.execute("show cell nr")
                raw_cell_lte = conn.execute("show cell lte")
                
                # Some systems might just use "show cells" and "show rn status"
                # so fallback if the new format isn't there
                rn_table = parse_radionode_table(raw_radionode)
                cell_pcis_nr = parse_cell_table(raw_cell_nr)
                cell_pcis_lte = parse_cell_table(raw_cell_lte)
                
                cell_pcis = {**cell_pcis_nr, **cell_pcis_lte}

            # Map configured RNs to the parsed table data
            for idx, rn_cfg in enumerate(cu.rns):
                rn_id = str(idx + 1)
                oper_state = "OOS-UNKNOWN"
                rn_ip = rn_cfg.ip
                
                # Match RN from table
                for row in rn_table:
                    if row['name'] == rn_cfg.name or row['rn_id'] == rn_id:
                        oper_state = row['oper_state']
                        rn_id = row['rn_id']
                        if row['ip'] != "-":
                            rn_ip = row['ip']
                        break

                pci = cell_pcis.get(rn_id, 0)
                
                # Get uptime directly from the RN's IP via SSH
                uptime_sec = 0
                if rn_ip and rn_ip != "-":
                    try:
                        rn_conn = ParamikoConnection(
                            host=rn_ip,
                            username="root", 
                            password="", # typically passwordless or known for lab
                            remote_command_template="{command}"
                        )
                        with rn_conn:
                            raw_uptime = rn_conn.execute("uptime")
                            uptime_sec = parse_uptime(raw_uptime)
                    except Exception:
                        pass # Could not fetch uptime

                previous = self._state.get_previous(cu.name, rn_cfg.name)
                
                # Compute status
                status = compute_node_status(oper_state, uptime_sec, previous)

                last_seen = datetime.now(timezone.utc).isoformat()
                
                new_state = RNState(
                    rn_id=rn_id,
                    cu_id=cu.name,
                    cu_name=cu.name,
                    cu_ip=cu.ip,
                    rn_name=rn_cfg.name,
                    ip=rn_ip,
                    pci=pci,
                    uptime_seconds=uptime_sec,
                    node_state=status,
                    last_seen=last_seen,
                    reboot_count=previous.reboot_count if previous else 0,
                )

                event = self._events.check_reboot(previous, new_state)
                if event is not None:
                    new_state.reboot_count += 1
                    
                if status == "REBOOTED" and not event:
                    # Make sure reboot_count increments if status is REBOOTED
                    # even if event_manager didn't catch it this exact cycle
                    pass

                self._state.update(new_state)
                
                # Persist to SQLite
                self._db.upsert_current_status(
                    rn_id=f"{cu.name}-{rn_id}", # Global unique ID
                    cu_id=cu.name,
                    status=status,
                    uptime=uptime_sec,
                    last_seen=last_seen,
                    pci=pci
                )

        except Exception:
            logger.exception("Failed to SSH poll CU %s (%s)", cu.name, cu.ip)

    def _poll_rn(self, cu_id: str, cu_name: str, cu_ip: str, rn_name: str, rn_ip: str) -> None:
        try:
            conn = MockConnection(host=rn_ip)
            with conn:
                raw_uptime = conn.execute("show uptime")
                raw_pci = conn.execute("show pci")
                raw_state = conn.execute("show state")

            uptime_sec = parse_uptime(raw_uptime)
            pci = parse_pci(raw_pci)
            oper_state = parse_state(raw_state)

            previous = self._state.get_previous(cu_name, rn_name)
            status = compute_node_status(oper_state, uptime_sec, previous)
            last_seen = datetime.now(timezone.utc).isoformat()
            
            # Using mock name as rn_id for uniqueness
            rn_id = rn_name

            new_state = RNState(
                rn_id=rn_id,
                cu_id=cu_id,
                cu_name=cu_name,
                cu_ip=cu_ip,
                rn_name=rn_name,
                ip=rn_ip,
                pci=pci,
                uptime_seconds=uptime_sec,
                node_state=status,
                last_seen=last_seen,
                reboot_count=previous.reboot_count if previous else 0,
            )

            event = self._events.check_reboot(previous, new_state)
            if event is not None:
                new_state.reboot_count += 1

            self._state.update(new_state)
            self._db.upsert_current_status(
                rn_id=f"{cu_id}-{rn_id}",
                cu_id=cu_id,
                status=status,
                uptime=uptime_sec,
                last_seen=last_seen,
                pci=pci
            )

        except Exception:
            logger.exception("Failed to poll RN %s/%s (%s)", cu_name, rn_name, rn_ip)

    def _broadcast_state(self) -> None:
        all_states = self._state.get_all()
        recent_events = self._events.get_recent_events(limit=50)

        payload = {
            "type": "state_update",
            "nodes": [s.to_dict() for s in all_states],
            "recent_events": [e.to_dict() for e in recent_events],
        }
        self._ws.broadcast(payload)

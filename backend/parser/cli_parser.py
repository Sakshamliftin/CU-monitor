"""
parser/cli_parser.py — Parse raw CLI text output into structured values.
"""

from __future__ import annotations

import re


def parse_uptime(text: str) -> int:
    """
    Parse a ``show uptime`` or linux ``uptime`` response into total seconds.

    Supports:
    1) "System Uptime : 5 days 03:12:15"
    2) "12 days" or "12 days 05:10:00"
    3) Linux uptime: "11:35:52 up  1:20,  0 users,  load average..."
    4) Linux uptime: "11:35:52 up 2 days, 3:15, 0 users, ..."
    5) Linux uptime: "11:35:52 up 45 min, 0 users, ..."
    6) "10325" (raw seconds)
    """
    text = text.strip()
    
    # 3/4/5 Linux uptime
    if "load average:" in text or "up " in text:
        # e.g., " 11:35:52 up 1:20,  0 users"
        # e.g., " 11:35:52 up 2 days, 3:15,  0 users"
        # e.g., " 11:35:52 up 45 min,  0 users"
        up_match = re.search(r"up\s+(.*?),\s+\d+\s+users", text)
        if up_match:
            uptime_str = up_match.group(1).strip()
            total_sec = 0
            
            # check days
            days_match = re.search(r"(\d+)\s+days?", uptime_str)
            if days_match:
                total_sec += int(days_match.group(1)) * 86400
                
            # check min
            min_match = re.search(r"(\d+)\s+min", uptime_str)
            if min_match:
                total_sec += int(min_match.group(1)) * 60
                
            # check HH:MM
            time_match = re.search(r"(\d+):(\d+)", uptime_str)
            if time_match:
                hrs, mins = int(time_match.group(1)), int(time_match.group(2))
                total_sec += (hrs * 3600) + (mins * 60)
                
            return total_sec

    # 1. System Uptime : 5 days 03:12:15
    pattern_full = r"System Uptime\s*:\s*(\d+)\s*days?\s+(\d{2}):(\d{2}):(\d{2})"
    match_full = re.search(pattern_full, text, re.IGNORECASE)
    if match_full:
        days, hours, minutes, seconds = (int(g) for g in match_full.groups())
        return days * 86400 + hours * 3600 + minutes * 60 + seconds
    
    # 2. X days HH:MM:SS or just X days
    pattern_days_time = r"(\d+)\s*days?\s+(\d{2}):(\d{2}):(\d{2})"
    match_dt = re.search(pattern_days_time, text, re.IGNORECASE)
    if match_dt:
        days, hours, minutes, seconds = (int(g) for g in match_dt.groups())
        return days * 86400 + hours * 3600 + minutes * 60 + seconds

    pattern_days = r"(\d+)\s*days?"
    match_days = re.search(pattern_days, text, re.IGNORECASE)
    if match_days:
        days = int(match_days.group(1))
        return days * 86400

    # 3. Raw number
    try:
        return int(text)
    except ValueError:
        pass

    raise ValueError(f"Cannot parse uptime from: {text!r}")


def parse_pci(text: str) -> int:
    """Parse legacy show pci"""
    pattern = r"PCI\s*:\s*(\d+)"
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Cannot parse PCI from: {text!r}")
    return int(match.group(1))


def parse_state(text: str) -> str:
    """Parse legacy show state"""
    pattern = r"State\s*:\s*(\S+)"
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Cannot parse state from: {text!r}")
    return match.group(1).upper()


def parse_rn_statuses(text: str) -> dict[str, str]:
    """Legacy simulated RN statuses"""
    results = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.lower().startswith("unknown command"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            rn_id, status = parts
            results[rn_id.upper()] = status.upper()
    return results


def parse_cell_pcis(text: str) -> dict[str, int]:
    """Legacy simulated cell PCIs"""
    results = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.lower().startswith("unknown command"):
            continue
        pattern = r"(\S+)\s+PCI\s+(\d+)"
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            cell_id, pci_str = match.groups()
            results[cell_id.upper()] = int(pci_str)
    return results


def parse_radionode_table(text: str) -> list[dict]:
    """
    Parse a multiline ``show radionode`` output table.
    
    Returns a list of dicts:
      [{'rn_id': '1', 'name': 'LTE', 'ip': '-', 'oper_state': 'OOS-NOTPRESENT'}, ...]
    """
    results = []
    lines = text.strip().splitlines()
    
    # Find the header row to determine column indices
    header = []
    data_start = -1
    for i, line in enumerate(lines):
        if "RN" in line and "Name" in line and "OperState" in line:
            header = line.split()
            data_start = i + 2 # Skip header and "----" row
            break
            
    if data_start == -1 or data_start >= len(lines):
        return results
        
    # Attempt mapping column indexes based on header
    rn_idx = header.index("RN") if "RN" in header else -1
    name_idx = header.index("Name") if "Name" in header else -1
    ip_idx = header.index("IPAddress") if "IPAddress" in header else -1
    oper_state_idx = header.index("OperState") if "OperState" in header else -1
    
    if -1 in [rn_idx, oper_state_idx]:
        return results
        
    for line in lines[data_start:]:
        line = line.strip()
        if not line or line.startswith("[ok]"):
            continue
            
        parts = line.split()
        if len(parts) >= len(header):
            results.append({
                'rn_id': parts[rn_idx],
                'name': parts[name_idx] if name_idx != -1 else "-",
                'ip': parts[ip_idx] if ip_idx != -1 else "-",
                'oper_state': parts[oper_state_idx]
            })
            
    return results


def parse_cell_table(text: str) -> dict[str, int]:
    """
    Parse ``show cell nr`` or ``show cell lte`` output.
    Returns mapping of RN ID (string) -> PCI (int).
    """
    results = {}
    lines = text.strip().splitlines()
    
    header = []
    data_start = -1
    for i, line in enumerate(lines):
        if ("DU/RN" in line or "RN" in line) and "PCI" in line:
            header = line.split()
            data_start = i + 2
            break
            
    if data_start == -1 or data_start >= len(lines):
        return results
        
    rn_idx = header.index("DU/RN") if "DU/RN" in header else header.index("RN")
    pci_idx = header.index("PCI")
    
    for line in lines[data_start:]:
        line = line.strip()
        if not line or line.startswith("[ok]"):
            continue
            
        parts = line.split()
        if len(parts) >= max(rn_idx, pci_idx) + 1:
            try:
                rn_id = parts[rn_idx]
                pci = int(parts[pci_idx])
                results[rn_id] = pci
            except ValueError:
                pass
                
    return results

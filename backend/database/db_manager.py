"""
database/db_manager.py - SQLite Database Manager for Telecom Lab Monitor

Handles creation, insertion and querying of the `current_status` and 
`status_history` tables.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self, db_path: str = "lab_monitor.db"):
        # Make sure the directory exists (e.g. if db_path contains dirs)
        db_file = Path(db_path)
        if db_file.parent and not db_file.parent.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)
            
        self.db_path = str(db_file)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create tables if they do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Table: current_status
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS current_status (
                        rn_id TEXT PRIMARY KEY,
                        cu_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        uptime INTEGER DEFAULT 0,
                        last_seen TEXT NOT NULL,
                        pci INTEGER DEFAULT 0
                    )
                ''')
                # Table: status_history
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS status_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        rn_id TEXT NOT NULL,
                        old_status TEXT,
                        new_status TEXT NOT NULL
                    )
                ''')
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.exception("Failed to initialize database")
            raise

    def upsert_current_status(self, rn_id: str, cu_id: str, status: str, uptime: int, last_seen: str, pci: int) -> None:
        """
        Upsert a node's current status.
        If the status has changed compared to the existing record, an entry
        is automatically added to the status_history table.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check previous status to see if it changed
                cursor.execute("SELECT status FROM current_status WHERE rn_id = ?", (rn_id,))
                row = cursor.fetchone()
                
                old_status = row["status"] if row else None
                
                # Insert into history if changed
                if old_status != status:
                    cursor.execute('''
                        INSERT INTO status_history (timestamp, rn_id, old_status, new_status)
                        VALUES (?, ?, ?, ?)
                    ''', (last_seen, rn_id, old_status, status))
                
                # Upsert current_status
                cursor.execute('''
                    INSERT INTO current_status (rn_id, cu_id, status, uptime, last_seen, pci)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(rn_id) DO UPDATE SET
                        cu_id=excluded.cu_id,
                        status=excluded.status,
                        uptime=excluded.uptime,
                        last_seen=excluded.last_seen,
                        pci=excluded.pci
                ''', (rn_id, cu_id, status, uptime, last_seen, pci))
                
                conn.commit()
        except Exception as e:
            logger.exception(f"Failed to upsert status for RN {rn_id}")

    def get_all_current_status(self) -> List[Dict[str, Any]]:
        """Return all current status records."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM current_status")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.exception("Failed to get all current status")
            return []

    def get_status_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent status history records."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM status_history ORDER BY timestamp DESC LIMIT ?", (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.exception("Failed to get status history")
            return []

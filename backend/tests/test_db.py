"""
tests/test_db.py — Unit tests for the SQLite DBManager.
"""
import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from database.db_manager import DBManager


class TestDBManager(unittest.TestCase):
    def setUp(self):
        # Use a temp file so tests don't affect the real database
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = DBManager(db_path=self.tmp.name)

    def tearDown(self):
        # On Windows, SQLite keeps file handles. We need to ensure all
        # connections are closed before the file can be deleted.
        import gc
        self.db = None
        gc.collect()
        try:
            os.unlink(self.tmp.name)
        except PermissionError:
            pass  # File will be cleaned up by OS on next run

    def test_tables_created(self):
        """Tables should exist after init."""
        import sqlite3
        conn = sqlite3.connect(self.tmp.name)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        self.assertIn('current_status', tables)
        self.assertIn('status_history', tables)

    def test_upsert_and_get(self):
        """Upserting a node should be retrievable."""
        self.db.upsert_current_status(
            rn_id='CU1-RN1', cu_id='CU1', status='HEALTHY',
            uptime=3600, last_seen='2026-07-25T10:00:00Z', pci=42
        )
        all_records = self.db.get_all_current_status()
        self.assertEqual(len(all_records), 1)
        rec = all_records[0]
        self.assertEqual(rec['rn_id'], 'CU1-RN1')
        self.assertEqual(rec['status'], 'HEALTHY')
        self.assertEqual(rec['pci'], 42)

    def test_upsert_updates_existing(self):
        """Upserting twice should update, not duplicate."""
        self.db.upsert_current_status(
            rn_id='CU1-RN1', cu_id='CU1', status='HEALTHY',
            uptime=3600, last_seen='2026-07-25T10:00:00Z', pci=42
        )
        self.db.upsert_current_status(
            rn_id='CU1-RN1', cu_id='CU1', status='OOS',
            uptime=0, last_seen='2026-07-25T10:10:00Z', pci=42
        )
        all_records = self.db.get_all_current_status()
        self.assertEqual(len(all_records), 1)
        self.assertEqual(all_records[0]['status'], 'OOS')

    def test_status_change_logged_to_history(self):
        """Status change should be logged in status_history."""
        self.db.upsert_current_status(
            rn_id='CU1-RN1', cu_id='CU1', status='HEALTHY',
            uptime=3600, last_seen='2026-07-25T10:00:00Z', pci=0
        )
        self.db.upsert_current_status(
            rn_id='CU1-RN1', cu_id='CU1', status='OOS',
            uptime=0, last_seen='2026-07-25T10:30:00Z', pci=0
        )
        history = self.db.get_status_history()
        # Should have 2 history entries: initial insert + status change
        self.assertGreaterEqual(len(history), 2)
        last_change = next((h for h in history if h['new_status'] == 'OOS'), None)
        self.assertIsNotNone(last_change)
        self.assertEqual(last_change['old_status'], 'HEALTHY')

    def test_no_history_on_same_status(self):
        """No history entry if status doesn't change."""
        self.db.upsert_current_status(
            rn_id='CU1-RN2', cu_id='CU1', status='HEALTHY',
            uptime=3600, last_seen='2026-07-25T10:00:00Z', pci=0
        )
        count_before = len(self.db.get_status_history())
        self.db.upsert_current_status(
            rn_id='CU1-RN2', cu_id='CU1', status='HEALTHY',
            uptime=7200, last_seen='2026-07-25T11:00:00Z', pci=0
        )
        count_after = len(self.db.get_status_history())
        self.assertEqual(count_before, count_after)


if __name__ == '__main__':
    unittest.main()

"""
tests/test_status.py — Unit tests for compute_node_status logic.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from monitoring.monitor_service import compute_node_status
from models.node import RNState


def _make_state(status: str, uptime: int) -> RNState:
    return RNState(
        rn_id='RN1', cu_id='CU1', cu_name='CU1', rn_name='RN-01',
        ip='1.2.3.4', pci=0, uptime_seconds=uptime, node_state=status,
        last_seen='2026-07-25T10:00:00Z', reboot_count=0
    )


class TestComputeNodeStatus(unittest.TestCase):

    def test_oos_init(self):
        self.assertEqual(compute_node_status('OOS-INIT', 0, None), 'OOS')

    def test_oos_notpresent(self):
        self.assertEqual(compute_node_status('OOS-NOTPRESENT', 100, None), 'OOS')

    def test_oos_disabled(self):
        self.assertEqual(compute_node_status('OOS-DISABLED', 3600, None), 'OOS')

    def test_oos_unprovisioned(self):
        self.assertEqual(compute_node_status('OOS-UNPROVISIONED', 0, None), 'OOS')

    def test_oos_inherited(self):
        self.assertEqual(compute_node_status('OOS-INHERITED', 0, None), 'OOS')

    def test_healthy_no_previous(self):
        self.assertEqual(compute_node_status('IS-NORMAL', 7200, None), 'HEALTHY')

    def test_healthy_increasing_uptime(self):
        prev = _make_state('HEALTHY', 3600)
        self.assertEqual(compute_node_status('IS-NORMAL', 7200, prev), 'HEALTHY')

    def test_rebooted_when_uptime_drops(self):
        prev = _make_state('HEALTHY', 7200)
        # Uptime fell from 7200 to 120 — reboot
        self.assertEqual(compute_node_status('IS-NORMAL', 120, prev), 'REBOOTED')

    def test_rebooted_after_rebooted_state(self):
        prev = _make_state('REBOOTED', 5000)
        self.assertEqual(compute_node_status('IS-NORMAL', 60, prev), 'REBOOTED')

    def test_healthy_after_oos_previous(self):
        # If previous was OOS, we don't compare uptime for reboot detection
        prev = _make_state('OOS', 0)
        self.assertEqual(compute_node_status('IS-NORMAL', 120, prev), 'HEALTHY')


if __name__ == '__main__':
    unittest.main()

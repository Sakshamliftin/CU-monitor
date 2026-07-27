"""
tests/test_parser.py — Unit tests for CLI parser functions.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from parser.cli_parser import (
    parse_uptime,
    parse_radionode_table,
    parse_cell_table,
)


class TestParseUptime(unittest.TestCase):
    def test_linux_uptime_hh_mm(self):
        text = "11:35:52 up  1:20,  0 users,  load average: 4.34, 3.20, 2.86"
        self.assertEqual(parse_uptime(text), 1 * 3600 + 20 * 60)

    def test_linux_uptime_days(self):
        text = " 10:00:00 up 2 days, 3:15,  0 users,  load average: 1.0"
        self.assertEqual(parse_uptime(text), 2 * 86400 + 3 * 3600 + 15 * 60)

    def test_linux_uptime_min(self):
        text = " 10:05:00 up 45 min,  1 users,  load average: 0.5"
        self.assertEqual(parse_uptime(text), 45 * 60)

    def test_system_uptime_format(self):
        text = "System Uptime : 5 days 03:12:15"
        self.assertEqual(parse_uptime(text), 5 * 86400 + 3 * 3600 + 12 * 60 + 15)

    def test_days_only(self):
        self.assertEqual(parse_uptime("12 days"), 12 * 86400)

    def test_raw_seconds(self):
        self.assertEqual(parse_uptime("3600"), 3600)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_uptime("invalid text no matches")


class TestParseRadionodeTable(unittest.TestCase):
    def setUp(self):
        self.sample = """
admin@ME2K-1> show radionode

RN    Name                              NodeType           Enable  EthernetID         IPAddress        OuterIPAddress   OperState         

----  --------------------------------  -----------------  ------  -----------------  ---------------  ---------------  ------------------

  30  7300-1                            IntegratedUnit     true    00:a0:0a:00:28:4e  172.20.30.200    172.20.30.200    IS-NORMAL         

  60  SimnovusRN                        IntegratedUnit     true    00:a0:0a:00:28:58  172.20.30.201    172.20.30.201    IS-NORMAL         

2050  -                                 DistributedUnit    false   00:24:48:11:11:55  172.20.30.204    172.20.30.204    OOS-UNPROVISIONED 

[ok][2026-07-21 12:00:18]
"""

    def test_parse_returns_list(self):
        result = parse_radionode_table(self.sample)
        self.assertIsInstance(result, list)

    def test_parse_finds_nodes(self):
        result = parse_radionode_table(self.sample)
        self.assertGreater(len(result), 0)

    def test_parse_oos_state(self):
        result = parse_radionode_table(self.sample)
        oos_nodes = [r for r in result if "OOS" in r['oper_state']]
        self.assertTrue(len(oos_nodes) > 0)

    def test_parse_normal_state(self):
        result = parse_radionode_table(self.sample)
        normal_nodes = [r for r in result if r['oper_state'] == 'IS-NORMAL']
        self.assertTrue(len(normal_nodes) > 0)


class TestParseCellTable(unittest.TestCase):
    def setUp(self):
        self.nr_sample = """
admin@ME2K-1> show cell nr

CellHandle  Name                              DU/RN  RadioUnit  Radio  CellID  NRCellIdentity  PCI  ModeInUse     DLCarriers  ULCarriers  PBCHPowerInUse  MaxDLULLayers  TxPowerPercentage

----------  --------------------------------  -----  ---------  -----  ------  --------------  ---  ------------  ----------  ----------  --------------  -------------  -----------------

         3  -                                     3          -      1       3             771    0           NSA           1           1               8          2 , 1                100

        20  -                                    20          -      1      20             788    2           NSA           1           1             -10          2 , 1                100

[ok][2026-07-21 11:59:36]
"""
        self.lte_sample = """
admin@ME2K-1> show cell lte

CellHandle  Name                              RN     CellID  ECI         PCI  RefSignalPwr  ModeInUse     RLs

----------  --------------------------------  -----  ------  ----------  ---  ------------  ------------  ---

         1  -                                     1       1       25857    0            -7     LTEeNodeB    0

        51  SimnovusLTECellBand4                 60       0       25856   51           -15     LTEeNodeB    0

[ok][2026-07-21 11:59:43]
"""

    def test_parse_nr_cells(self):
        result = parse_cell_table(self.nr_sample)
        self.assertIsInstance(result, dict)
        self.assertIn('3', result)
        self.assertIn('20', result)
        self.assertEqual(result['3'], 0)
        self.assertEqual(result['20'], 2)

    def test_parse_lte_cells(self):
        result = parse_cell_table(self.lte_sample)
        self.assertIsInstance(result, dict)
        self.assertIn('1', result)
        self.assertIn('60', result)
        self.assertEqual(result['1'], 0)
        self.assertEqual(result['60'], 51)


if __name__ == '__main__':
    unittest.main()

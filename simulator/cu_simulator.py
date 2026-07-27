#!/usr/bin/env python3
"""
cu_simulator.py — Simulated Control Unit (CU) Command Line Interface.

This script simulates a CU console interface. It supports:
- Interactive shell mode (when run without arguments).
- Direct command arguments (e.g., cu_simulator.py show uptime).
- -c flag execution (e.g., cu_simulator.py -c "show uptime").
- SSH Forced Command execution (via SSH_ORIGINAL_COMMAND environment variable).

It reads its state dynamically from state.json.
"""

from __future__ import annotations

import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE_PATH = os.path.join(SCRIPT_DIR, "state.json")


def load_state() -> dict:
    """Load the state from state.json. Fallback to default if load fails."""
    try:
        if os.path.exists(STATE_FILE_PATH):
            with open(STATE_FILE_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass

    # Default fallback data
    return {
        "uptime": "12 days",
        "rns": [
            {"id": "RN1", "state": "ACTIVE"},
            {"id": "RN2", "state": "ACTIVE"},
            {"id": "RN3", "state": "IDLE"},
            {"id": "RN4", "state": "OOS"},
            {"id": "RN5", "state": "ACTIVE"}
        ],
        "cells": [
            {"pci": 101},
            {"pci": 102},
            {"pci": 103}
        ]
    }


def execute_command(command_str: str) -> None:
    """Execute a single CU command and output results to stdout."""
    cmd = command_str.strip().lower()
    if not cmd:
        return

    state_data = load_state()

    if cmd == "show rn status":
        rns = state_data.get("rns", [])
        for rn in rns:
            print(f"{rn.get('id')} {rn.get('state')}")
    elif cmd == "show cells":
        cells = state_data.get("cells", [])
        for i, cell in enumerate(cells, 1):
            print(f"Cell{i} PCI {cell.get('pci')}")
    elif cmd == "show uptime":
        print(state_data.get("uptime", "0 days"))
    else:
        print("Unknown command")


def main() -> None:
    # 1. Check for SSH Forced Command environment variable
    ssh_cmd = os.environ.get("SSH_ORIGINAL_COMMAND")
    if ssh_cmd:
        execute_command(ssh_cmd)
        return

    # 2. Check for command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "-c":
            if len(sys.argv) > 2:
                execute_command(sys.argv[2])
            else:
                print("Error: -c option requires an argument", file=sys.stderr)
                sys.exit(1)
        else:
            # Join arguments (e.g. show rn status)
            command_str = " ".join(sys.argv[1:])
            execute_command(command_str)
        return

    # 3. Interactive Shell Mode (fallback)
    is_tty = sys.stdin.isatty()
    if is_tty:
        print("CU Simulator Interactive Shell. Type 'exit' or 'quit' to close.")
    
    try:
        while True:
            if is_tty:
                sys.stdout.write("cu> ")
                sys.stdout.flush()
            line = sys.stdin.readline()
            if not line:
                break  # EOF
            
            cleaned_line = line.strip()
            if cleaned_line.lower() in ("exit", "quit"):
                break
            
            if cleaned_line:
                execute_command(cleaned_line)
    except KeyboardInterrupt:
        if is_tty:
            print()
        sys.exit(0)


if __name__ == "__main__":
    main()

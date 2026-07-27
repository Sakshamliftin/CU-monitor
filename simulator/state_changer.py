#!/usr/bin/env python3
"""
state_changer.py — Periodic state randomizer for the dummy CU simulator.

Runs in a continuous loop. Every 20–30 seconds, it:
1. Loads the current state from state.json.
2. Selects a random Radio Node (RN).
3. Changes the state of that RN to a random choice (ACTIVE, IDLE, OOS).
4. Saves the updated state back to state.json atomically.
"""

from __future__ import annotations

import os
import sys
import json
import time
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE_PATH = os.path.join(SCRIPT_DIR, "state.json")
TEMP_FILE_PATH = os.path.join(SCRIPT_DIR, "state.json.tmp")

ALLOWED_STATES = ["ACTIVE", "IDLE", "OOS"]


def load_state() -> dict:
    """Load the state from state.json. Returns a default dictionary if loading fails."""
    if os.path.exists(STATE_FILE_PATH):
        try:
            with open(STATE_FILE_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Warning: Failed to read state.json: {e}", file=sys.stderr)
    
    # Return fallback defaults
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


def save_state_atomic(data: dict) -> None:
    """Save state data to state.json atomically using write-and-replace."""
    # Write to a temporary file in the same directory
    with open(TEMP_FILE_PATH, "w") as f:
        json.dump(data, f, indent=2)
    # Perform atomic replace (rename)
    os.replace(TEMP_FILE_PATH, STATE_FILE_PATH)


def main() -> None:
    print("Dummy CU state changer daemon started. Press Ctrl+C to stop.")
    
    # Initialize state.json if it doesn't exist
    if not os.path.exists(STATE_FILE_PATH):
        try:
            save_state_atomic(load_state())
            print(f"Initialized default {STATE_FILE_PATH}")
        except Exception as e:
            print(f"Failed to initialize state file: {e}", file=sys.stderr)
            sys.exit(1)

    while True:
        try:
            state = load_state()
            rns = state.get("rns", [])
            
            if not rns:
                print("Warning: No RNs found in state.json", file=sys.stderr)
                time.sleep(5)
                continue

            # Pick a random RN and random state
            rn = random.choice(rns)
            old_state = rn.get("state", "UNKNOWN")
            new_state = random.choice(ALLOWED_STATES)

            # Update and save atomically
            rn["state"] = new_state
            save_state_atomic(state)

            print(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"Updated {rn.get('id')}: {old_state} -> {new_state}",
                flush=True
            )

            # Random sleep interval between 20 and 30 seconds
            sleep_sec = random.uniform(20.0, 30.0)
            time.sleep(sleep_sec)

        except KeyboardInterrupt:
            print("\nStopping state changer daemon.")
            break
        except Exception as e:
            print(f"Error in main loop: {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    main()

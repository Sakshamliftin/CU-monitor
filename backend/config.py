"""
config.py — Application configuration loader.

Reads topology.yaml and exposes a Settings dataclass with all
configurable parameters: polling interval, worker pool size,
and the full CU/RN topology.
"""

from __future__ import annotations

# import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RNConfig:
    """Configuration for a single Radio Node."""
    name: str
    ip: str


@dataclass
class CUConfig:
    """Configuration for a Control Unit and its connected RNs."""
    name: str
    ip: str
    rns: list[RNConfig] = field(default_factory=list)


@dataclass
class Settings:
    """Top-level application settings parsed from topology.yaml."""
    poll_interval_sec: int = 10
    max_workers: int = 5
    cus: list[CUConfig] = field(default_factory=list)


def load_settings(config_path: str | Path | None = None) -> Settings:
    """
    Load settings from a YAML configuration file.

    Args:
        config_path: Path to topology.yaml. Defaults to
                     ``backend/topology.yaml`` relative to this file.

    Returns:
        A fully populated Settings instance.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "topology.yaml"
    else:
        config_path = Path(config_path)

    with open(config_path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    # --- Parse settings block ------------------------------------------------
    raw_settings = raw.get("settings", {})
    poll_interval = int(raw_settings.get("poll_interval_sec", 10))
    max_workers = int(raw_settings.get("max_workers", 5))

    # --- Parse CU / RN topology ----------------------------------------------
    cus: list[CUConfig] = []
    for cu_dict in raw.get("cus", []):
        rns = [
            RNConfig(name=rn["name"], ip=rn["ip"])
            for rn in cu_dict.get("rns", [])
        ]
        cus.append(CUConfig(name=cu_dict["name"], ip=cu_dict["ip"], rns=rns))

    return Settings(
        poll_interval_sec=poll_interval,
        max_workers=max_workers,
        cus=cus,
    )

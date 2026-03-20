"""Fleet data models — pure dataclasses, no logic."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class FleetMeta:
    """Top-level fleet metadata."""

    name: str
    duration: int
    interval: int
    hostname_prefix: str
    hardware: str


@dataclass
class HostsConfig:
    """Baseline host configuration."""

    count: int
    baseline: str
    baseline_path: Path
    jitter: float = 0.0


@dataclass
class BadActorsConfig:
    """Bad-actor host configuration."""

    count: int = 0
    jitter: float = 0.0
    profiles: List[str] = field(default_factory=list)
    profile_paths: List[Path] = field(default_factory=list)


@dataclass
class FleetProfile:
    """Parsed fleet profile — the full fleet specification."""

    meta: FleetMeta
    hosts: HostsConfig
    bad_actors: BadActorsConfig


@dataclass
class HostAssignment:
    """One host's role, jitter factor, and workload path."""

    hostname: str
    role: str  # "baseline" or "bad_actor"
    jitter_factor: float
    workload_path: Path
    workload_rel: str = ""

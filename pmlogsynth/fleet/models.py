"""Fleet data models — pure dataclasses, no logic."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class FleetMeta:
    """Top-level fleet metadata."""

    name: str
    duration: int
    interval: int
    hostname_prefix: str
    hardware: str


@dataclass
class InlineProfile:
    """A named workload profile defined inline in a fleet file."""

    phases: List[Dict[str, Any]]


@dataclass
class HostsConfig:
    """Baseline host configuration."""

    count: int
    baseline: str
    jitter: float = 0.0


@dataclass
class BadActorsConfig:
    """Bad-actor host configuration."""

    count: int = 0
    jitter: float = 0.0
    profiles: List[str] = field(default_factory=list)


@dataclass
class FleetProfile:
    """Parsed fleet profile — the full fleet specification."""

    meta: FleetMeta
    hosts: HostsConfig
    bad_actors: BadActorsConfig
    profiles: Dict[str, InlineProfile] = field(default_factory=dict)


@dataclass
class HostAssignment:
    """One host's role, jitter factor, and workload profile name."""

    hostname: str
    role: str  # "baseline" or "bad_actor"
    jitter_factor: float
    workload_rel: str

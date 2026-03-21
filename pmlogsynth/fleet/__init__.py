"""Fleet mode — multi-host archive generation from a single fleet profile.

All public symbols are re-exported here for backwards compatibility.
Import from submodules directly for tighter coupling:

    from pmlogsynth.fleet.loader import load_fleet_profile
    from pmlogsynth.fleet.assignment import assign_hosts
"""

from pmlogsynth.fleet.assignment import assign_hosts
from pmlogsynth.fleet.display import print_dry_run
from pmlogsynth.fleet.loader import load_fleet_profile
from pmlogsynth.fleet.manifest import write_manifest
from pmlogsynth.fleet.models import (
    BadActorsConfig,
    FleetMeta,
    FleetProfile,
    HostAssignment,
    HostsConfig,
    InlineProfile,
)
from pmlogsynth.fleet.orchestrator import generate_fleet
from pmlogsynth.fleet.warnings import check_override_warnings

__all__ = [
    "assign_hosts",
    "BadActorsConfig",
    "check_override_warnings",
    "FleetMeta",
    "FleetProfile",
    "generate_fleet",
    "HostAssignment",
    "HostsConfig",
    "InlineProfile",
    "load_fleet_profile",
    "print_dry_run",
    "write_manifest",
]

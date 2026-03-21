"""Dry-run display — print host assignment table without generating archives."""

from typing import List, Optional

from pmlogsynth.fleet.models import FleetProfile, HostAssignment


def print_dry_run(
    fleet: FleetProfile,
    assignments: List[HostAssignment],
    seed: Optional[int],
) -> None:
    """Print host assignment table without generating archives."""
    seed_str = str(seed) if seed is not None else "none"
    print("Fleet: {} ({} hosts, seed={})".format(
        fleet.meta.name, len(assignments), seed_str,
    ))
    print()
    for a in assignments:
        role_label = "BAD      " if a.role == "bad_actor" else "baseline "
        print("  {}  {}  {}  (jitter: x{:.2f})".format(
            a.hostname, role_label, a.workload_rel, a.jitter_factor,
        ))

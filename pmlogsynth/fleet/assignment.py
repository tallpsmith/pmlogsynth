"""Host assignment — role selection, jitter factors, and stable seeding."""

import hashlib
import random
from typing import List, Optional

from pmlogsynth.fleet.models import FleetProfile, HostAssignment


def _stable_host_seed(fleet_name: str, hostname: str, seed: int) -> int:
    """Derive a deterministic per-host seed using SHA-256.

    Python's hash() is not stable across runs. SHA-256 gives us
    repeatable results for any given (fleet_name, hostname, seed) tuple.
    """
    digest = hashlib.sha256(
        "{}:{}:{}".format(fleet_name, hostname, seed).encode()
    ).hexdigest()
    return int(digest[:16], 16)


def assign_hosts(
    fleet: FleetProfile,
    seed: Optional[int] = None,
) -> List[HostAssignment]:
    """Assign hostnames, roles, and jitter factors to each host.

    Uses a seeded RNG for deterministic bad-actor selection and jitter
    factor generation. If seed is None, a random seed is chosen.
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    rng = random.Random(seed)
    count = fleet.hosts.count
    pad_width = max(2, len(str(count)))

    # Pick which host indices are bad actors
    bad_actor_indices = set(rng.sample(range(count), fleet.bad_actors.count))

    assignments: List[HostAssignment] = []
    for i in range(count):
        hostname = "{}-{}".format(
            fleet.meta.hostname_prefix,
            str(i + 1).zfill(pad_width),
        )
        is_bad = i in bad_actor_indices

        if is_bad:
            role = "bad_actor"
            jitter_stddev = fleet.bad_actors.jitter
            # Pick a profile from the bad-actor pool
            profile_idx = rng.randrange(len(fleet.bad_actors.profiles))
            workload_path = fleet.bad_actors.profile_paths[profile_idx]
            workload_rel = fleet.bad_actors.profiles[profile_idx]
        else:
            role = "baseline"
            jitter_stddev = fleet.hosts.jitter
            workload_path = fleet.hosts.baseline_path
            workload_rel = fleet.hosts.baseline

        # Generate a stable, deterministic jitter factor per host
        host_seed = _stable_host_seed(fleet.meta.name, hostname, seed)
        host_rng = random.Random(host_seed)
        jitter_factor = host_rng.gauss(1.0, jitter_stddev)

        assignments.append(
            HostAssignment(
                hostname=hostname,
                role=role,
                jitter_factor=jitter_factor,
                workload_path=workload_path,
                workload_rel=workload_rel,
            )
        )

    return assignments

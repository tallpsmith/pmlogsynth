"""Fleet profile loading, validation, and host assignment."""

import hashlib
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pmlogsynth.profile import ValidationError, parse_duration

logger = logging.getLogger(__name__)


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


def _parse_fleet_meta(raw: Dict[str, Any]) -> FleetMeta:
    """Parse and validate the meta section of a fleet profile."""
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        raise ValidationError("fleet profile missing 'meta' section")

    name = meta.get("name")
    if not name:
        raise ValidationError("fleet profile missing 'meta.name'")

    duration_raw = meta.get("duration")
    if duration_raw is None:
        raise ValidationError("fleet profile missing 'meta.duration'")
    duration = parse_duration(duration_raw)

    interval_raw = meta.get("interval")
    if interval_raw is None:
        raise ValidationError("fleet profile missing 'meta.interval'")
    interval = parse_duration(interval_raw)

    hostname_prefix = meta.get("hostname_prefix")
    if not hostname_prefix:
        raise ValidationError("fleet profile missing 'meta.hostname_prefix'")

    hardware = meta.get("hardware")
    if not hardware:
        raise ValidationError("fleet profile missing 'meta.hardware'")

    return FleetMeta(
        name=str(name),
        duration=duration,
        interval=interval,
        hostname_prefix=str(hostname_prefix),
        hardware=str(hardware),
    )


def _parse_hosts(raw: Dict[str, Any], fleet_dir: Path) -> HostsConfig:
    """Parse and validate the hosts section of a fleet profile."""
    hosts = raw.get("hosts")
    if not isinstance(hosts, dict):
        raise ValidationError("fleet profile missing 'hosts' section")

    count = hosts.get("count")
    if not isinstance(count, int) or count < 1:
        raise ValidationError("hosts.count must be a positive integer")

    baseline = hosts.get("baseline")
    if not baseline:
        raise ValidationError("hosts.baseline is required")

    jitter = float(hosts.get("jitter", 0.0))
    baseline_path = fleet_dir / str(baseline)

    return HostsConfig(
        count=count,
        baseline=str(baseline),
        baseline_path=baseline_path,
        jitter=jitter,
    )


def _parse_bad_actors(
    raw: Dict[str, Any],
    hosts_config: HostsConfig,
    fleet_dir: Path,
) -> BadActorsConfig:
    """Parse and validate the bad_actors section of a fleet profile."""
    section = raw.get("bad_actors")
    if section is None:
        return BadActorsConfig()

    if not isinstance(section, dict):
        raise ValidationError("bad_actors must be a mapping")

    count = int(section.get("count", 0))
    if count > hosts_config.count:
        raise ValidationError(
            "bad_actors.count ({}) exceeds hosts.count ({})".format(
                count, hosts_config.count
            )
        )

    # Default bad_actors jitter to hosts jitter if not specified
    jitter_raw = section.get("jitter")
    if jitter_raw is not None:
        jitter = float(jitter_raw)
    else:
        jitter = hosts_config.jitter

    profiles_raw = section.get("profiles", [])
    profiles = [str(p) for p in profiles_raw]
    profile_paths = [fleet_dir / p for p in profiles]

    return BadActorsConfig(
        count=count,
        jitter=jitter,
        profiles=profiles,
        profile_paths=profile_paths,
    )


def load_fleet_profile(path: Path) -> FleetProfile:
    """Load and validate a fleet profile YAML file.

    Workload paths (baseline, bad-actor profiles) are resolved relative
    to the directory containing the fleet YAML file.
    """
    text = path.read_text()
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValidationError("fleet profile must be a YAML mapping")

    fleet_dir = path.parent

    meta = _parse_fleet_meta(raw)
    hosts = _parse_hosts(raw, fleet_dir)
    bad_actors = _parse_bad_actors(raw, hosts, fleet_dir)

    return FleetProfile(meta=meta, hosts=hosts, bad_actors=bad_actors)


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


def write_manifest(
    path: Path,
    fleet: FleetProfile,
    assignments: List[HostAssignment],
    seed: Optional[int],
) -> None:
    """Write fleet.manifest YAML file recording all host assignments."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = {
        "meta": {
            "name": fleet.meta.name,
            "generated": now,
            "pmlogsynth_version": "1.0",
            "seed": seed,
            "duration": fleet.meta.duration,
            "interval": fleet.meta.interval,
            "hardware": fleet.meta.hardware,
            "host_count": len(assignments),
        },
        "archives": [
            {
                "hostname": a.hostname,
                "profile": a.workload_rel,
                "role": a.role,
                "jitter_factor": round(a.jitter_factor, 6),
            }
            for a in assignments
        ],
    }

    path.write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def check_override_warnings(fleet: FleetProfile) -> None:
    """Emit warnings for workload profile values that fleet settings override."""
    seen = {}  # type: Dict[Path, bool]

    all_paths = [fleet.hosts.baseline_path]
    all_rels = [fleet.hosts.baseline]
    for idx in range(len(fleet.bad_actors.profiles)):
        all_paths.append(fleet.bad_actors.profile_paths[idx])
        all_rels.append(fleet.bad_actors.profiles[idx])

    for wpath, wrel in zip(all_paths, all_rels):
        if wpath in seen:
            continue
        seen[wpath] = True

        try:
            raw = yaml.safe_load(wpath.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue

        if not isinstance(raw, dict):
            continue

        meta = raw.get("meta", {})
        if not isinstance(meta, dict):
            continue

        if "duration" in meta:
            profile_duration = parse_duration(meta["duration"])
            if profile_duration != fleet.meta.duration:
                logger.warning(
                    "workload profile '%s' defines duration=%s "
                    "— overridden by fleet setting duration=%s",
                    wrel, profile_duration, fleet.meta.duration,
                )

        if "interval" in meta:
            profile_interval = parse_duration(meta["interval"])
            if profile_interval != fleet.meta.interval:
                logger.warning(
                    "workload profile '%s' defines interval=%s "
                    "— overridden by fleet setting interval=%s",
                    wrel, profile_interval, fleet.meta.interval,
                )

        host = raw.get("host", {})
        if isinstance(host, dict) and "profile" in host:
            profile_hw = str(host["profile"])
            if profile_hw != fleet.meta.hardware:
                logger.warning(
                    "workload profile '%s' defines hardware=%s "
                    "— overridden by fleet setting hardware=%s",
                    wrel, profile_hw, fleet.meta.hardware,
                )

"""Fleet profile YAML parsing and validation."""

from pathlib import Path
from typing import Any, Dict

import yaml

from pmlogsynth.fleet.models import (
    BadActorsConfig,
    FleetMeta,
    FleetProfile,
    HostsConfig,
)
from pmlogsynth.profile import ValidationError, parse_duration


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

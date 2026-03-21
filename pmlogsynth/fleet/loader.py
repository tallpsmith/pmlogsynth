"""Fleet profile YAML parsing and validation."""

from pathlib import Path
from typing import Any, Dict

import yaml

from pmlogsynth.fleet.models import (
    BadActorsConfig,
    FleetMeta,
    FleetProfile,
    HostsConfig,
    InlineProfile,
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


def _parse_profiles(raw: Dict[str, Any]) -> Dict[str, InlineProfile]:
    """Parse and validate the profiles section of a fleet profile."""
    section = raw.get("profiles")
    if not isinstance(section, dict):
        raise ValidationError("fleet profile missing 'profiles' section")

    profiles = {}  # type: Dict[str, InlineProfile]
    for name, body in section.items():
        if not isinstance(body, dict):
            raise ValidationError(
                "profile '{}' must be a mapping".format(name)
            )
        phases = body.get("phases")
        if not isinstance(phases, list) or len(phases) == 0:
            raise ValidationError(
                "profile '{}' phases must be a non-empty list".format(name)
            )
        profiles[str(name)] = InlineProfile(phases=phases)

    return profiles


def _parse_hosts(
    raw: Dict[str, Any],
    profiles: Dict[str, InlineProfile],
) -> HostsConfig:
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
    baseline = str(baseline)

    if baseline not in profiles:
        raise ValidationError(
            "hosts.baseline '{}' not found in profiles".format(baseline)
        )

    jitter = float(hosts.get("jitter", 0.0))

    return HostsConfig(
        count=count,
        baseline=baseline,
        jitter=jitter,
    )


def _parse_bad_actors(
    raw: Dict[str, Any],
    hosts_config: HostsConfig,
    profiles: Dict[str, InlineProfile],
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
    profile_names = [str(p) for p in profiles_raw]

    for name in profile_names:
        if name not in profiles:
            raise ValidationError(
                "bad_actors profile '{}' not found in profiles".format(name)
            )

    return BadActorsConfig(
        count=count,
        jitter=jitter,
        profiles=profile_names,
    )


def load_fleet_profile(path: Path) -> FleetProfile:
    """Load and validate a fleet profile YAML file.

    All workload profiles are defined inline in the 'profiles' section.
    References in hosts.baseline and bad_actors.profiles are validated
    against profile names.
    """
    text = path.read_text()
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValidationError("fleet profile must be a YAML mapping")

    meta = _parse_fleet_meta(raw)
    profiles = _parse_profiles(raw)
    hosts = _parse_hosts(raw, profiles)
    bad_actors = _parse_bad_actors(raw, hosts, profiles)

    return FleetProfile(
        meta=meta, hosts=hosts, bad_actors=bad_actors, profiles=profiles,
    )

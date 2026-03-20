"""Override warning checks for fleet vs workload profile conflicts."""

import logging

import yaml

from pmlogsynth.fleet.models import FleetProfile
from pmlogsynth.profile import parse_duration

logger = logging.getLogger(__name__)


def check_override_warnings(fleet: FleetProfile) -> None:
    """Emit warnings for workload profile values that fleet settings override."""
    seen = set()

    all_paths = [fleet.hosts.baseline_path]
    all_rels = [fleet.hosts.baseline]
    for idx in range(len(fleet.bad_actors.profiles)):
        all_paths.append(fleet.bad_actors.profile_paths[idx])
        all_rels.append(fleet.bad_actors.profiles[idx])

    for wpath, wrel in zip(all_paths, all_rels):
        if wpath in seen:
            continue
        seen.add(wpath)

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

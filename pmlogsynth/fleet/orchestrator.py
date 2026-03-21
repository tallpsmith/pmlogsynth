"""Fleet archive generation orchestrator."""

import importlib
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from pmlogsynth.fleet.manifest import write_manifest
from pmlogsynth.fleet.models import FleetProfile, HostAssignment


def _build_workload_yaml(
    fleet: FleetProfile,
    assignment: HostAssignment,
) -> str:
    """Build a standalone workload profile YAML string from inline data.

    Constructs a complete workload profile dict with fleet-level meta
    overrides, then serialises to YAML for WorkloadProfile.from_string().
    """
    inline = fleet.profiles[assignment.workload_rel]

    workload = {
        "meta": {
            "hostname": assignment.hostname,
            "duration": fleet.meta.duration,
            "interval": fleet.meta.interval,
        },
        "host": {
            "profile": fleet.meta.hardware,
        },
        "phases": inline.phases,
    }

    return yaml.dump(workload, default_flow_style=False, sort_keys=False)


def generate_fleet(
    fleet: FleetProfile,
    assignments: List[HostAssignment],
    output_dir: Path,
    seed: Optional[int],
    force: bool = False,
    start: Optional[datetime] = None,
    verbose: bool = False,
    config_dir: Optional[Path] = None,
) -> None:
    """Generate one PCP archive per host, then write fleet.manifest.

    Archives are generated sequentially — PCP's pmiLogImport C library
    is not thread-safe (see https://github.com/tallpsmith/pmlogsynth/issues/16).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Lazy import writer module (avoid PCP dependency at parse time)
    _writer_mod = importlib.import_module("pmlogsynth.writer")
    ArchiveWriter = _writer_mod.ArchiveWriter

    from pmlogsynth.jitter import apply_jitter
    from pmlogsynth.profile import ProfileResolver, WorkloadProfile
    from pmlogsynth.sampler import ValueSampler
    from pmlogsynth.timeline import TimelineSequencer

    # Resolve hardware profile once (shared across all hosts)
    resolver = ProfileResolver(config_dir=config_dir)
    hardware = resolver.resolve(fleet.meta.hardware)

    for assignment in assignments:
        workload_yaml = _build_workload_yaml(fleet, assignment)
        profile = WorkloadProfile.from_string(
            workload_yaml, config_dir=config_dir,
        )

        profile = apply_jitter(profile, assignment.jitter_factor)

        timeline = TimelineSequencer(profile).expand(start_time=start)
        sampler = ValueSampler(noise=profile.meta.noise)

        output_path = str(output_dir / assignment.hostname)
        writer = ArchiveWriter(
            output_path=output_path,
            profile=profile,
            hardware=hardware,
            force=force,
        )
        writer.write(timeline=timeline, sampler=sampler)

        if verbose:
            print(
                "  generated: {} ({})".format(
                    assignment.hostname, assignment.role,
                ),
                file=sys.stderr,
            )

    # Write manifest
    write_manifest(
        output_dir / "fleet.manifest", fleet, assignments, seed=seed,
    )

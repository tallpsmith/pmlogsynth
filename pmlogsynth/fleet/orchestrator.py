"""Fleet archive generation orchestrator."""

import importlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    }  # type: Dict[str, Any]

    return yaml.dump(workload, default_flow_style=False, sort_keys=False)


def generate_fleet(
    fleet: FleetProfile,
    assignments: List[HostAssignment],
    output_dir: Path,
    seed: Optional[int],
    jobs: int = 1,
    force: bool = False,
    start: Optional[datetime] = None,
    verbose: bool = False,
    config_dir: Optional[Path] = None,
) -> None:
    """Generate one PCP archive per host, then write fleet.manifest."""
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

    def _generate_one(assignment: HostAssignment) -> None:
        """Generate a single host archive."""
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

    # Generate archives — sequential by default.
    # NOTE: PCP's pmiLogImport C library is not thread-safe.
    # See https://github.com/tallpsmith/pmlogsynth/issues/16
    if jobs <= 1:
        for assignment in assignments:
            _generate_one(assignment)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(_generate_one, a): a for a in assignments
            }
            for future in as_completed(futures):
                future.result()

    # Write manifest
    write_manifest(
        output_dir / "fleet.manifest", fleet, assignments, seed=seed,
    )

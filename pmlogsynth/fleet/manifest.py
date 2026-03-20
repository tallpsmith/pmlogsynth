"""Fleet manifest writer — records host assignments to YAML."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import yaml

from pmlogsynth.fleet.models import FleetProfile, HostAssignment


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

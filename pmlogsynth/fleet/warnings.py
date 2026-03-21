"""Override warning checks — retained as no-op for API compatibility.

With inline profiles, fleet-level meta is the only source of truth for
duration/interval/hardware. There are no external files to conflict with.
"""

from pmlogsynth.fleet.models import FleetProfile


def check_override_warnings(fleet: FleetProfile) -> None:
    """No-op — inline profiles cannot conflict with fleet meta."""
    pass

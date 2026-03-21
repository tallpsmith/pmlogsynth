"""Per-host stressor jitter — pure function, no mutation."""

from dataclasses import fields, replace
from typing import Any, Dict, List, Optional, TypeVar

from pmlogsynth.profile import (
    Phase,
    WorkloadProfile,
)

# Fields that represent ratios — clamped to [0.0, 1.0]
# Only fields that actually exist in stressor dataclasses belong here.
_RATIO_FIELDS = frozenset({
    "utilization", "user_ratio", "sys_ratio", "iowait_ratio",
    "used_ratio", "cache_ratio", "noise", "error_rate",
})

_T = TypeVar("_T")


def _clamp(value: float, field_name: str) -> float:
    """Clamp a jittered value to its valid range."""
    if field_name in _RATIO_FIELDS:
        return max(0.0, min(1.0, value))
    return max(0.0, value)


def _jitter_dataclass(stressor: _T, factor: float) -> _T:
    """Apply jitter factor to all numeric Optional fields on a dataclass."""
    updates: Dict[str, Any] = {}
    for f in fields(stressor):  # type: ignore[arg-type]
        val = getattr(stressor, f.name)
        if val is not None and isinstance(val, (int, float)):
            jittered = val * factor
            clamped = _clamp(jittered, f.name)
            # Preserve int type for int fields
            if isinstance(val, int):
                updates[f.name] = int(clamped)
            else:
                updates[f.name] = clamped
    return replace(stressor, **updates)  # type: ignore[type-var]


def _jitter_optional(stressor: Optional[_T], factor: float) -> Optional[_T]:
    """Apply jitter to an optional stressor, returning None if input is None."""
    if stressor is None:
        return None
    return _jitter_dataclass(stressor, factor)


def _jitter_phase(phase: Phase, factor: float) -> Phase:
    """Apply jitter to all stressors in a phase."""
    return replace(
        phase,
        cpu=_jitter_optional(phase.cpu, factor),
        memory=_jitter_optional(phase.memory, factor),
        disk=_jitter_optional(phase.disk, factor),
        network=_jitter_optional(phase.network, factor),
    )


def apply_jitter(profile: WorkloadProfile, factor: float) -> WorkloadProfile:
    """Apply a multiplicative jitter factor to all stressor values in a profile.

    Returns a new WorkloadProfile — the original is not mutated.
    Ratio fields are clamped to [0.0, 1.0]; throughput fields to >= 0.
    """
    jittered_phases: List[Phase] = [
        _jitter_phase(p, factor) for p in profile.phases
    ]
    return replace(profile, phases=jittered_phases)

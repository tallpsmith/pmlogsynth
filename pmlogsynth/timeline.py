"""Timeline sequencer: expand phases into a flat list of SamplePoints."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pmlogsynth.profile import (
    CpuStressor,
    DiskStressor,
    MemoryStressor,
    NetworkStressor,
    Phase,
    ProfileMeta,
    WorkloadProfile,
)


@dataclass
class SamplePoint:
    """One sample — effective stressor values at a single timestamp."""

    timestamp_sec: int
    phase_name: str
    cpu: CpuStressor
    memory: MemoryStressor
    disk: DiskStressor
    network: NetworkStressor


@dataclass
class ExpandedTimeline:
    """A flat, ordered list of SamplePoints after repeat/interpolation expansion."""

    samples: List[SamplePoint]
    start_time: datetime


class TimelineSequencer:
    """Expands a WorkloadProfile into an ExpandedTimeline."""

    def __init__(self, profile: WorkloadProfile) -> None:
        self._profile = profile

    def expand(
        self,
        start_time: Optional[datetime] = None,
    ) -> ExpandedTimeline:
        """Expand phases into SamplePoints.

        Args:
            start_time: Override start time. Defaults to now - meta.duration.

        Returns:
            ExpandedTimeline with one SamplePoint per interval tick.

        Raises:
            ValidationError: If expanded timeline is inconsistent.
        """
        from pmlogsynth.profile import ValidationError

        meta = self._profile.meta
        phases = self._expand_repeats(self._profile.phases, meta)

        # Validate expanded duration
        total = sum(p.duration for p in phases)
        if total != meta.duration:
            raise ValidationError(
                f"Expanded timeline duration ({total}s) does not equal "
                f"meta.duration ({meta.duration}s)"
            )

        if start_time is None:
            start_time = datetime.now(tz=timezone.utc) - timedelta(seconds=meta.duration)

        samples = self._generate_samples(phases, meta, start_time)
        return ExpandedTimeline(samples=samples, start_time=start_time)

    def _expand_repeats(
        self, phases: List[Phase], meta: ProfileMeta
    ) -> List[Phase]:
        """Expand repeat: daily and repeat: N into concrete phase lists."""
        from pmlogsynth.profile import ValidationError

        expanded: List[Phase] = []
        for i, phase in enumerate(phases):
            if phase.repeat is None:
                expanded.append(phase)
            elif phase.repeat == "daily":
                # Insert baseline fills between daily repetitions
                seconds_per_day = 86400
                if phase.duration > seconds_per_day:
                    raise ValidationError(
                        f"phases[{i}] ({phase.name}): repeat:daily phase duration "
                        f"({phase.duration}s) exceeds 86400s (FR-031)"
                    )
                fill_duration = seconds_per_day - phase.duration
                repetitions = meta.duration // seconds_per_day
                remainder = meta.duration % seconds_per_day
                if repetitions == 0:
                    raise ValidationError(
                        f"phases[{i}] ({phase.name}): meta.duration ({meta.duration}s) "
                        f"is less than one day (86400s); repeat:daily cannot fit"
                    )
                for rep in range(repetitions):
                    expanded.append(Phase(
                        name=f"{phase.name}-rep{rep + 1}",
                        duration=phase.duration,
                        transition=phase.transition if rep > 0 else None,
                        cpu=phase.cpu,
                        memory=phase.memory,
                        disk=phase.disk,
                        network=phase.network,
                    ))
                    if rep < repetitions - 1 or remainder > 0:
                        last_fill = fill_duration + remainder
                        fill_dur = fill_duration if rep < repetitions - 1 else last_fill
                        expanded.append(Phase(
                            name=f"baseline-fill-{rep + 1}",
                            duration=fill_dur,
                        ))
                    elif fill_duration > 0:
                        expanded.append(Phase(
                            name=f"baseline-fill-{rep + 1}",
                            duration=fill_duration,
                        ))
            elif isinstance(phase.repeat, int):
                for rep in range(phase.repeat):
                    expanded.append(Phase(
                        name=f"{phase.name}-rep{rep + 1}",
                        duration=phase.duration,
                        transition=phase.transition if rep > 0 else None,
                        cpu=phase.cpu,
                        memory=phase.memory,
                        disk=phase.disk,
                        network=phase.network,
                    ))
            else:
                raise ValidationError(
                    f"phases[{i}].repeat must be 'daily' or an integer, "
                    f"got {phase.repeat!r}"
                )
        return expanded

    def _generate_samples(
        self,
        phases: List[Phase],
        meta: ProfileMeta,
        start_time: datetime,
    ) -> List[SamplePoint]:
        """Generate one SamplePoint per interval tick across all phases."""
        from pmlogsynth.profile import ValidationError

        samples: List[SamplePoint] = []
        current_ts = int(start_time.timestamp())
        prev_cpu = CpuStressor()
        prev_memory = MemoryStressor()
        prev_disk = DiskStressor()
        prev_network = NetworkStressor()

        for i, phase in enumerate(phases):
            if phase.transition == "linear" and i == 0:
                raise ValidationError(
                    "First phase cannot use 'transition: linear' (FR-055)"
                )

            ticks = max(1, phase.duration // meta.interval)
            target_cpu = phase.cpu or CpuStressor()
            target_memory = phase.memory or MemoryStressor()
            target_disk = phase.disk or DiskStressor()
            target_network = phase.network or NetworkStressor()

            for t in range(ticks):
                if phase.transition == "linear":
                    frac = (t + 1) / ticks
                    cpu = _lerp_cpu(prev_cpu, target_cpu, frac)
                    memory = _lerp_memory(prev_memory, target_memory, frac)
                    disk = _lerp_disk(prev_disk, target_disk, frac)
                    network = _lerp_network(prev_network, target_network, frac)
                else:
                    cpu = target_cpu
                    memory = target_memory
                    disk = target_disk
                    network = target_network

                samples.append(SamplePoint(
                    timestamp_sec=current_ts,
                    phase_name=phase.name,
                    cpu=cpu,
                    memory=memory,
                    disk=disk,
                    network=network,
                ))
                current_ts += meta.interval

            # Save last values for next phase interpolation
            prev_cpu = target_cpu
            prev_memory = target_memory
            prev_disk = target_disk
            prev_network = target_network

        return samples


# ---------------------------------------------------------------------------
# Linear interpolation helpers
# ---------------------------------------------------------------------------


def _lerp_opt(a: Optional[float], b: Optional[float], frac: float) -> Optional[float]:
    """Interpolate between two Optional floats; None treated as 0.0."""
    a_val = a if a is not None else 0.0
    b_val = b if b is not None else 0.0
    return a_val + (b_val - a_val) * frac


def _lerp_cpu(prev: CpuStressor, target: CpuStressor, frac: float) -> CpuStressor:
    return CpuStressor(
        utilization=_lerp_opt(prev.utilization, target.utilization, frac),
        user_ratio=_lerp_opt(prev.user_ratio, target.user_ratio, frac),
        sys_ratio=_lerp_opt(prev.sys_ratio, target.sys_ratio, frac),
        iowait_ratio=_lerp_opt(prev.iowait_ratio, target.iowait_ratio, frac),
        noise=target.noise,
    )


def _lerp_memory(prev: MemoryStressor, target: MemoryStressor, frac: float) -> MemoryStressor:
    return MemoryStressor(
        used_ratio=_lerp_opt(prev.used_ratio, target.used_ratio, frac),
        cache_ratio=_lerp_opt(prev.cache_ratio, target.cache_ratio, frac),
        noise=target.noise,
    )


def _lerp_disk(prev: DiskStressor, target: DiskStressor, frac: float) -> DiskStressor:
    return DiskStressor(
        read_mbps=_lerp_opt(prev.read_mbps, target.read_mbps, frac),
        write_mbps=_lerp_opt(prev.write_mbps, target.write_mbps, frac),
        noise=target.noise,
    )


def _lerp_network(
    prev: NetworkStressor, target: NetworkStressor, frac: float
) -> NetworkStressor:
    return NetworkStressor(
        rx_mbps=_lerp_opt(prev.rx_mbps, target.rx_mbps, frac),
        tx_mbps=_lerp_opt(prev.tx_mbps, target.tx_mbps, frac),
        noise=target.noise,
    )

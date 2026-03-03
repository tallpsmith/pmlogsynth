"""Profile loading, validation, and hardware profile resolution."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ValidationError(Exception):
    """Raised when a workload or hardware profile fails validation."""


_DURATION_SUFFIXES = {"s": 1, "m": 60, "h": 3600}


def parse_duration(raw: Any) -> int:
    """Parse a duration value to seconds.

    Accepts plain integers (seconds) or strings like '30s', '10m', '24h'.
    Raises ValidationError for invalid formats or non-positive results.
    """
    if isinstance(raw, int):
        seconds = raw
    elif isinstance(raw, str) and raw and raw[-1] in _DURATION_SUFFIXES:
        multiplier = _DURATION_SUFFIXES[raw[-1]]
        body = raw[:-1]
        try:
            seconds = int(body) * multiplier
        except ValueError:
            raise ValidationError(f"invalid duration {raw!r}: non-integer body")
    else:
        raise ValidationError(
            f"invalid duration {raw!r}: use a positive integer (seconds) or a string "
            f"like '30s', '10m', '24h'"
        )
    if seconds <= 0:
        raise ValidationError(f"invalid duration {raw!r}: must be positive")
    return seconds


# ---------------------------------------------------------------------------
# Hardware profile entities
# ---------------------------------------------------------------------------


@dataclass
class DiskDevice:
    name: str
    type: Optional[str] = None  # "nvme", "ssd", "hdd" — informational


@dataclass
class NetworkInterface:
    name: str
    speed_mbps: Optional[int] = None


@dataclass
class HardwareProfile:
    name: str
    cpus: int
    memory_kb: int
    disks: List[DiskDevice] = field(default_factory=list)
    interfaces: List[NetworkInterface] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Workload stressor entities (all fields Optional — defaults at compute time)
# ---------------------------------------------------------------------------


@dataclass
class CpuStressor:
    utilization: Optional[float] = None
    user_ratio: Optional[float] = None
    sys_ratio: Optional[float] = None
    iowait_ratio: Optional[float] = None
    noise: Optional[float] = None


@dataclass
class MemoryStressor:
    used_ratio: Optional[float] = None
    cache_ratio: Optional[float] = None
    noise: Optional[float] = None


@dataclass
class DiskStressor:
    read_mbps: Optional[float] = None
    write_mbps: Optional[float] = None
    iops_read: Optional[int] = None
    iops_write: Optional[int] = None
    noise: Optional[float] = None


@dataclass
class NetworkStressor:
    rx_mbps: Optional[float] = None
    tx_mbps: Optional[float] = None
    noise: Optional[float] = None


# ---------------------------------------------------------------------------
# Workload profile entities
# ---------------------------------------------------------------------------


@dataclass
class ProfileMeta:
    duration: int
    hostname: str = "synthetic-host"
    timezone: str = "UTC"
    interval: int = 60
    noise: float = 0.0
    mean_packet_bytes: int = 1400


@dataclass
class HostConfig:
    profile: Optional[str] = None
    overrides: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    cpus: Optional[int] = None
    memory_kb: Optional[int] = None
    disks: Optional[List[DiskDevice]] = None
    interfaces: Optional[List[NetworkInterface]] = None


@dataclass
class Phase:
    name: str
    duration: int
    transition: Optional[str] = None   # "instant" | "linear"
    repeat: Optional[Any] = None       # "daily" | int
    cpu: Optional[CpuStressor] = None
    memory: Optional[MemoryStressor] = None
    disk: Optional[DiskStressor] = None
    network: Optional[NetworkStressor] = None


@dataclass
class WorkloadProfile:
    meta: ProfileMeta
    host: HostConfig
    phases: List[Phase]
    # Resolved hardware profile — set by ProfileLoader after resolution
    hardware: Optional[HardwareProfile] = None

    @classmethod
    def from_file(cls, path: "Path") -> "WorkloadProfile":
        """Load profile from file — delegates to from_string."""
        return cls.from_string(Path(path).read_text(encoding="utf-8"), config_dir=None)

    @classmethod
    def from_string(
        cls,
        yaml_text: str,
        config_dir: Optional[Path] = None,
    ) -> "WorkloadProfile":
        """Parse and validate a YAML workload profile string."""
        try:
            raw = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise ValidationError(f"YAML parse error: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValidationError("Profile must be a YAML mapping")

        meta = _parse_meta(raw.get("meta", {}))
        host_config = _parse_host(raw.get("host", {}))
        phases = _parse_phases(raw.get("phases", []))

        # Resolve hardware profile
        resolver = ProfileResolver(config_dir=config_dir)
        hardware = resolver.resolve_host(host_config)

        profile = cls(meta=meta, host=host_config, phases=phases, hardware=hardware)
        _validate_profile(profile)
        return profile


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_meta(raw: Any) -> ProfileMeta:
    if not isinstance(raw, dict):
        raise ValidationError("meta must be a mapping")
    try:
        duration = parse_duration(raw.get("duration", 86400))
    except ValidationError:
        raise ValidationError("meta.duration must be a positive integer or duration string (e.g. '24h', '30m')")
    interval = raw.get("interval", 60)
    if not isinstance(interval, int) or interval <= 0:
        raise ValidationError("meta.interval must be a positive integer (FR-030)")
    noise = float(raw.get("noise", 0.0))
    if not (0.0 <= noise <= 1.0):
        raise ValidationError(f"meta.noise must be in [0.0, 1.0], got {noise} (FR-029)")
    return ProfileMeta(
        duration=duration,
        hostname=str(raw.get("hostname", "synthetic-host")),
        timezone=str(raw.get("timezone", "UTC")),
        interval=interval,
        noise=noise,
        mean_packet_bytes=int(raw.get("mean_packet_bytes", 1400)),
    )


def _parse_host(raw: Any) -> HostConfig:
    if not isinstance(raw, dict):
        raise ValidationError("host must be a mapping")

    has_profile = "profile" in raw
    has_overrides = "overrides" in raw
    inline_keys = {"name", "cpus", "memory_kb", "disks", "interfaces"}
    has_inline = bool(inline_keys.intersection(raw.keys()))

    # FR-015a: profile + bare inline fields (without overrides:) is a validation error
    if has_profile and has_inline and not has_overrides:
        raise ValidationError(
            "host.profile and inline host fields cannot be mixed without an 'overrides:' "
            "key. Use 'host.overrides:' to override specific fields from the named profile."
        )

    def _parse_disks(raw_disks: Any) -> List[DiskDevice]:
        if not isinstance(raw_disks, list):
            raise ValidationError("host.disks must be a list")
        result = []
        for d in raw_disks:
            if not isinstance(d, dict) or "name" not in d:
                raise ValidationError("Each disk must have a 'name' field")
            result.append(DiskDevice(name=str(d["name"]), type=d.get("type")))
        return result

    def _parse_interfaces(raw_ifaces: Any) -> List[NetworkInterface]:
        if not isinstance(raw_ifaces, list):
            raise ValidationError("host.interfaces must be a list")
        result = []
        for i in raw_ifaces:
            if not isinstance(i, dict) or "name" not in i:
                raise ValidationError("Each interface must have a 'name' field")
            result.append(NetworkInterface(
                name=str(i["name"]),
                speed_mbps=i.get("speed_mbps"),
            ))
        return result

    overrides: Optional[Dict[str, Any]] = None
    if has_overrides:
        overrides = dict(raw["overrides"])

    disks = _parse_disks(raw["disks"]) if "disks" in raw else None
    interfaces = _parse_interfaces(raw["interfaces"]) if "interfaces" in raw else None

    return HostConfig(
        profile=str(raw["profile"]) if has_profile else None,
        overrides=overrides,
        name=str(raw["name"]) if "name" in raw else None,
        cpus=int(raw["cpus"]) if "cpus" in raw else None,
        memory_kb=int(raw["memory_kb"]) if "memory_kb" in raw else None,
        disks=disks,
        interfaces=interfaces,
    )


def _parse_cpu_stressor(raw: Any) -> CpuStressor:
    if not isinstance(raw, dict):
        raise ValidationError("cpu stressor must be a mapping")
    noise = raw.get("noise")
    if noise is not None:
        noise = float(noise)
        if not (0.0 <= noise <= 1.0):
            raise ValidationError(f"cpu.noise must be in [0.0, 1.0], got {noise}")
    return CpuStressor(
        utilization=float(raw["utilization"]) if "utilization" in raw else None,
        user_ratio=float(raw["user_ratio"]) if "user_ratio" in raw else None,
        sys_ratio=float(raw["sys_ratio"]) if "sys_ratio" in raw else None,
        iowait_ratio=float(raw["iowait_ratio"]) if "iowait_ratio" in raw else None,
        noise=noise,
    )


def _parse_memory_stressor(raw: Any) -> MemoryStressor:
    if not isinstance(raw, dict):
        raise ValidationError("memory stressor must be a mapping")
    noise = raw.get("noise")
    if noise is not None:
        noise = float(noise)
        if not (0.0 <= noise <= 1.0):
            raise ValidationError(f"memory.noise must be in [0.0, 1.0], got {noise}")
    return MemoryStressor(
        used_ratio=float(raw["used_ratio"]) if "used_ratio" in raw else None,
        cache_ratio=float(raw["cache_ratio"]) if "cache_ratio" in raw else None,
        noise=noise,
    )


def _parse_disk_stressor(raw: Any) -> DiskStressor:
    if not isinstance(raw, dict):
        raise ValidationError("disk stressor must be a mapping")
    noise = raw.get("noise")
    if noise is not None:
        noise = float(noise)
        if not (0.0 <= noise <= 1.0):
            raise ValidationError(f"disk.noise must be in [0.0, 1.0], got {noise}")
    return DiskStressor(
        read_mbps=float(raw["read_mbps"]) if "read_mbps" in raw else None,
        write_mbps=float(raw["write_mbps"]) if "write_mbps" in raw else None,
        iops_read=int(raw["iops_read"]) if "iops_read" in raw else None,
        iops_write=int(raw["iops_write"]) if "iops_write" in raw else None,
        noise=noise,
    )


def _parse_network_stressor(raw: Any) -> NetworkStressor:
    if not isinstance(raw, dict):
        raise ValidationError("network stressor must be a mapping")
    noise = raw.get("noise")
    if noise is not None:
        noise = float(noise)
        if not (0.0 <= noise <= 1.0):
            raise ValidationError(f"network.noise must be in [0.0, 1.0], got {noise}")
    return NetworkStressor(
        rx_mbps=float(raw["rx_mbps"]) if "rx_mbps" in raw else None,
        tx_mbps=float(raw["tx_mbps"]) if "tx_mbps" in raw else None,
        noise=noise,
    )


def _parse_phases(raw: Any) -> List[Phase]:
    if not isinstance(raw, list) or len(raw) == 0:
        raise ValidationError("phases must be a non-empty list")
    phases = []
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            raise ValidationError(f"phases[{i}] must be a mapping")
        name = p.get("name")
        if not name:
            raise ValidationError(f"phases[{i}].name is required")
        try:
            duration = parse_duration(p.get("duration"))
        except ValidationError:
            raise ValidationError(f"phases[{i}].duration must be a positive integer or duration string (e.g. '1h', '30m')")
        transition = p.get("transition")
        if transition is not None and transition not in ("instant", "linear"):
            raise ValidationError(
                f"phases[{i}].transition must be 'instant' or 'linear', got {transition!r}"
            )
        repeat = p.get("repeat")  # "daily" or int — validated later
        phases.append(Phase(
            name=str(name),
            duration=duration,
            transition=transition,
            repeat=repeat,
            cpu=_parse_cpu_stressor(p["cpu"]) if "cpu" in p else None,
            memory=_parse_memory_stressor(p["memory"]) if "memory" in p else None,
            disk=_parse_disk_stressor(p["disk"]) if "disk" in p else None,
            network=_parse_network_stressor(p["network"]) if "network" in p else None,
        ))
    return phases


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_profile(profile: "WorkloadProfile") -> None:
    """Cross-field validation after parsing."""
    phases = profile.phases
    meta = profile.meta

    # repeat:daily expansion auto-fills each day to exactly 86400s, leaving no room
    # for other explicit phases — the expanded total would exceed meta.duration.
    daily_phases = [p for p in phases if p.repeat == "daily"]
    if daily_phases and len(phases) > 1:
        raise ValidationError(
            f"A phase with repeat:daily must be the only phase in the profile "
            f"(found {len(phases)} phases). Other phases cause duration overflow "
            f"because repeat:daily auto-fills the remainder of each day."
        )

    # FR-055: first phase cannot use transition: linear
    if phases[0].transition == "linear":
        raise ValidationError(
            "phases[0]: first phase cannot use 'transition: linear' — "
            "no prior phase exists to interpolate from (FR-055)"
        )

    # Validate per-phase constraints
    has_repeat = False
    for i, phase in enumerate(phases):
        # FR-026: cpu ratios
        if phase.cpu is not None:
            ur = phase.cpu.user_ratio or 0.0
            sr = phase.cpu.sys_ratio or 0.0
            iw = phase.cpu.iowait_ratio or 0.0
            if ur + sr + iw > 1.0 + 1e-9:
                raise ValidationError(
                    f"phases[{i}] ({phase.name}): user_ratio + sys_ratio + iowait_ratio "
                    f"= {ur + sr + iw:.4f} > 1.0 (FR-026)"
                )
        # FR-031: repeat daily must fit
        if phase.repeat == "daily":
            has_repeat = True
            if phase.duration > meta.duration:
                raise ValidationError(
                    f"phases[{i}] ({phase.name}): repeat:daily phase duration "
                    f"({phase.duration}s) exceeds meta.duration ({meta.duration}s) (FR-031)"
                )
        elif isinstance(phase.repeat, int):
            has_repeat = True

    # FR-027: duration sum check when no repeat keys present
    if not has_repeat:
        total = sum(p.duration for p in phases)
        if total != meta.duration:
            raise ValidationError(
                f"Sum of phase durations ({total}s) does not equal "
                f"meta.duration ({meta.duration}s) (FR-027)"
            )


# ---------------------------------------------------------------------------
# Hardware profile resolution
# ---------------------------------------------------------------------------


@dataclass
class ProfileEntry:
    name: str
    source: str  # "bundled" | "user" | "config-dir"
    path: Path


class ProfileResolver:
    """Resolves hardware profile names using the 3-level precedence chain."""

    BUNDLED_DIR: Path = Path(__file__).parent / "profiles"
    USER_DIR: Path = Path.home() / ".pcp" / "pmlogsynth" / "profiles"

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        self.config_dir = config_dir

    def resolve(self, name: str) -> HardwareProfile:
        """Resolve a named hardware profile. Raises ValidationError if not found."""
        for entry in self.list_all():
            if entry.name == name:
                return _load_hardware_profile(entry.path)
        raise ValidationError(
            f"Hardware profile '{name}' not found. "
            f"Available profiles: {[e.name for e in self.list_all()]}. "
            f"Use --list-profiles to see all sources."
        )

    def resolve_host(self, host: HostConfig) -> HardwareProfile:
        """Resolve HostConfig to a HardwareProfile."""
        if host.profile is not None:
            base = self.resolve(host.profile)
            if host.overrides:
                base = _apply_overrides(base, host.overrides)
            return base
        # Fully inline form
        if host.cpus is None or host.memory_kb is None:
            raise ValidationError(
                "Inline host specification requires at least 'cpus' and 'memory_kb'"
            )
        return HardwareProfile(
            name=host.name or "inline",
            cpus=host.cpus,
            memory_kb=host.memory_kb,
            disks=host.disks or [],
            interfaces=host.interfaces or [],
        )

    def list_all(self) -> List[ProfileEntry]:
        """Return all available profiles with source labels, highest precedence first."""
        seen: Dict[str, ProfileEntry] = {}
        # Highest precedence: -C directory
        if self.config_dir and self.config_dir.is_dir():
            for f in sorted(self.config_dir.glob("*.yaml")):
                name = f.stem
                if name not in seen:
                    seen[name] = ProfileEntry(name=name, source="config-dir", path=f)
        # User directory
        if self.USER_DIR.is_dir():
            for f in sorted(self.USER_DIR.glob("*.yaml")):
                name = f.stem
                if name not in seen:
                    seen[name] = ProfileEntry(name=name, source="user", path=f)
        # Bundled
        if self.BUNDLED_DIR.is_dir():
            for f in sorted(self.BUNDLED_DIR.glob("*.yaml")):
                name = f.stem
                if name not in seen:
                    seen[name] = ProfileEntry(name=name, source="bundled", path=f)
        return list(seen.values())


def _load_hardware_profile(path: Path) -> HardwareProfile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Hardware profile YAML error in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValidationError(f"Hardware profile {path} must be a YAML mapping")
    name = str(raw.get("name", path.stem))
    cpus = raw.get("cpus")
    if not isinstance(cpus, int) or cpus <= 0:
        raise ValidationError(f"Hardware profile {name}: 'cpus' must be a positive integer")
    memory_kb = raw.get("memory_kb")
    if not isinstance(memory_kb, int) or memory_kb <= 0:
        raise ValidationError(f"Hardware profile {name}: 'memory_kb' must be a positive integer")
    disks = []
    for d in raw.get("disks", []):
        disks.append(DiskDevice(name=str(d["name"]), type=d.get("type")))
    interfaces = []
    for i in raw.get("interfaces", []):
        interfaces.append(NetworkInterface(name=str(i["name"]), speed_mbps=i.get("speed_mbps")))
    return HardwareProfile(
        name=name,
        cpus=cpus,
        memory_kb=memory_kb,
        disks=disks,
        interfaces=interfaces,
    )


def _apply_overrides(base: HardwareProfile, overrides: Dict[str, Any]) -> HardwareProfile:
    """Apply override dict on top of a base HardwareProfile."""
    cpus = overrides.get("cpus", base.cpus)
    memory_kb = overrides.get("memory_kb", base.memory_kb)
    name = overrides.get("name", base.name)
    disks = base.disks
    interfaces = base.interfaces
    if "disks" in overrides:
        disks = [DiskDevice(name=str(d["name"]), type=d.get("type")) for d in overrides["disks"]]
    if "interfaces" in overrides:
        interfaces = [
            NetworkInterface(name=str(i["name"]), speed_mbps=i.get("speed_mbps"))
            for i in overrides["interfaces"]
        ]
    return HardwareProfile(
        name=name,
        cpus=int(cpus),
        memory_kb=int(memory_kb),
        disks=disks,
        interfaces=interfaces,
    )

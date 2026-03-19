# OS Metadata Metrics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Tier 1 PCP metadata metrics (`kernel.uname.*`, `hinv.*`) to synthetic archives so tools can determine OS identity and hardware topology from the archive data itself.

**Architecture:** New `OsProfile` dataclass embedded in `HardwareProfile`, parsed from an optional `os:` section in hardware profile YAML. New `MetadataMetricModel` domain model emits all metadata as discrete (write-once) metrics using the existing `is_discrete` infrastructure. First use of `PM_TYPE_STRING` in the codebase.

**Tech Stack:** Python 3.8+, PyYAML, PCP `pcp.pmi` / `cpmapi`

---

## Chunk 1: Foundation — OsProfile and PM_TYPE_STRING

### Task 1: Add PM_TYPE_STRING to pcp_constants

**Files:**
- Modify: `pmlogsynth/pcp_constants.py:18-22`
- Test: `tests/unit/test_pcp_constants.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_pcp_constants.py`:

```python
"""Tier 1 unit tests for pcp_constants — verify PM_TYPE_STRING is exported."""

from pmlogsynth.pcp_constants import PM_TYPE_STRING


def test_pm_type_string_is_integer() -> None:
    """PM_TYPE_STRING must be an integer constant."""
    assert isinstance(PM_TYPE_STRING, int)


def test_pm_type_string_value() -> None:
    """PM_TYPE_STRING is 6 per PCP's cpmapi."""
    assert PM_TYPE_STRING == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pcp_constants.py -v`
Expected: FAIL with `ImportError: cannot import name 'PM_TYPE_STRING'`

- [ ] **Step 3: Write minimal implementation**

Add to `pmlogsynth/pcp_constants.py` after line 22 (`PM_TYPE_DOUBLE`):

```python
PM_TYPE_STRING: int = _c.PM_TYPE_STRING
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_pcp_constants.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/pcp_constants.py tests/unit/test_pcp_constants.py
git commit -m "Add PM_TYPE_STRING constant for string-typed metadata metrics"
```

---

### Task 2: Add OsProfile dataclass to profile.py

**Files:**
- Modify: `pmlogsynth/profile.py:64-88`
- Test: `tests/unit/test_os_profile.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_os_profile.py`:

```python
"""Tier 1 unit tests for OsProfile dataclass and defaults."""

from pmlogsynth.profile import OsProfile


def test_os_profile_all_defaults() -> None:
    """OsProfile with no args uses sensible Linux defaults."""
    os = OsProfile()
    assert os.sysname == "Linux"
    assert os.release == "5.15.0-91-generic"
    assert os.version == "#1 SMP PREEMPT_DYNAMIC"
    assert os.machine == "x86_64"
    assert os.distro == "Ubuntu 22.04.3 LTS"
    assert os.pagesize == 4096
    # nodename defaults to None — resolved later from meta.hostname
    assert os.nodename is None


def test_os_profile_custom_fields() -> None:
    """OsProfile accepts custom values for all fields."""
    os = OsProfile(
        sysname="Linux",
        nodename="prod-web-03",
        release="6.1.0-generic",
        version="#2 SMP",
        machine="aarch64",
        distro="Red Hat Enterprise Linux 9.2",
        pagesize=65536,
    )
    assert os.nodename == "prod-web-03"
    assert os.machine == "aarch64"
    assert os.pagesize == 65536


def test_os_profile_partial_override() -> None:
    """OsProfile with only some fields set keeps defaults for the rest."""
    os = OsProfile(nodename="myhost", distro="Debian 12")
    assert os.sysname == "Linux"
    assert os.nodename == "myhost"
    assert os.distro == "Debian 12"
    assert os.pagesize == 4096
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_os_profile.py -v`
Expected: FAIL with `ImportError: cannot import name 'OsProfile'`

- [ ] **Step 3: Write minimal implementation**

Add to `pmlogsynth/profile.py` after line 78 (`NetworkInterface` class), before `HardwareProfile`:

```python
@dataclass
class OsProfile:
    """OS identity metadata — embedded in hardware profiles."""
    sysname: str = "Linux"
    nodename: Optional[str] = None  # defaults to meta.hostname at resolve time
    release: str = "5.15.0-91-generic"
    version: str = "#1 SMP PREEMPT_DYNAMIC"
    machine: str = "x86_64"
    distro: str = "Ubuntu 22.04.3 LTS"
    pagesize: int = 4096
```

Add `os_profile` field to `HardwareProfile` (line 82-88):

```python
@dataclass
class HardwareProfile:
    name: str
    cpus: int
    memory_kb: int
    disks: List[DiskDevice] = field(default_factory=list)
    interfaces: List[NetworkInterface] = field(default_factory=list)
    os_profile: OsProfile = field(default_factory=OsProfile)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_os_profile.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run: `pytest tests/unit/ tests/integration/ -v`
Expected: All existing tests PASS — `HardwareProfile` gains `os_profile` with a default, so no existing constructor calls break.

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/profile.py tests/unit/test_os_profile.py
git commit -m "Add OsProfile dataclass with sensible Linux defaults

Embedded in HardwareProfile as os_profile field. All fields optional
with defaults so existing profiles work without changes."
```

---

### Task 3: Parse os: section from hardware profile YAML

**Files:**
- Modify: `pmlogsynth/profile.py:540-566` (`_load_hardware_profile`)
- Modify: `pmlogsynth/profile.py:569-589` (`_apply_overrides`)
- Test: `tests/unit/test_os_profile.py` (extend)

- [ ] **Step 1: Write failing tests for YAML parsing**

Add to `tests/unit/test_os_profile.py`:

```python
import textwrap
from pathlib import Path

from pmlogsynth.profile import HardwareProfile, OsProfile, ValidationError


def test_load_hardware_profile_with_os_section(tmp_path: Path) -> None:
    """Hardware profile YAML with os: section populates os_profile."""
    hw_yaml = tmp_path / "test.yaml"
    hw_yaml.write_text(textwrap.dedent("""\
        name: test-os
        cpus: 4
        memory_kb: 16777216
        os:
          sysname: Linux
          nodename: test-server
          release: "6.1.0-generic"
          machine: aarch64
          distro: "Debian 12"
          pagesize: 65536
        disks:
          - name: sda
        interfaces:
          - name: eth0
    """))
    from pmlogsynth.profile import _load_hardware_profile
    hw = _load_hardware_profile(hw_yaml)
    assert hw.os_profile.sysname == "Linux"
    assert hw.os_profile.nodename == "test-server"
    assert hw.os_profile.release == "6.1.0-generic"
    assert hw.os_profile.machine == "aarch64"
    assert hw.os_profile.distro == "Debian 12"
    assert hw.os_profile.pagesize == 65536


def test_load_hardware_profile_without_os_section(tmp_path: Path) -> None:
    """Hardware profile YAML without os: section uses defaults."""
    hw_yaml = tmp_path / "test.yaml"
    hw_yaml.write_text(textwrap.dedent("""\
        name: test-no-os
        cpus: 2
        memory_kb: 8388608
        disks:
          - name: nvme0n1
    """))
    from pmlogsynth.profile import _load_hardware_profile
    hw = _load_hardware_profile(hw_yaml)
    assert hw.os_profile.sysname == "Linux"
    assert hw.os_profile.nodename is None
    assert hw.os_profile.pagesize == 4096


def test_load_hardware_profile_partial_os(tmp_path: Path) -> None:
    """Hardware profile with partial os: section keeps defaults for omitted fields."""
    hw_yaml = tmp_path / "test.yaml"
    hw_yaml.write_text(textwrap.dedent("""\
        name: test-partial
        cpus: 2
        memory_kb: 8388608
        os:
          nodename: custom-host
        disks:
          - name: sda
    """))
    from pmlogsynth.profile import _load_hardware_profile
    hw = _load_hardware_profile(hw_yaml)
    assert hw.os_profile.nodename == "custom-host"
    assert hw.os_profile.sysname == "Linux"
    assert hw.os_profile.pagesize == 4096
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_os_profile.py::test_load_hardware_profile_with_os_section -v`
Expected: FAIL — `_load_hardware_profile` doesn't parse `os:` section yet

- [ ] **Step 3: Implement os: parsing in _load_hardware_profile**

Modify `_load_hardware_profile` in `pmlogsynth/profile.py` (around line 540-566). Add parsing of the `os:` section before the `return` statement:

```python
def _load_hardware_profile(path: Path) -> HardwareProfile:
    # ... existing code for cpus, memory_kb, disks, interfaces ...

    # Parse optional os: section
    os_profile = OsProfile()
    raw_os = raw.get("os")
    if raw_os is not None:
        if not isinstance(raw_os, dict):
            raise ValidationError(
                f"Hardware profile {name}: 'os' must be a mapping"
            )
        os_profile = OsProfile(
            sysname=str(raw_os.get("sysname", os_profile.sysname)),
            nodename=str(raw_os["nodename"]) if "nodename" in raw_os else None,
            release=str(raw_os.get("release", os_profile.release)),
            version=str(raw_os.get("version", os_profile.version)),
            machine=str(raw_os.get("machine", os_profile.machine)),
            distro=str(raw_os.get("distro", os_profile.distro)),
            pagesize=int(raw_os.get("pagesize", os_profile.pagesize)),
        )

    return HardwareProfile(
        name=name,
        cpus=cpus,
        memory_kb=memory_kb,
        disks=disks,
        interfaces=interfaces,
        os_profile=os_profile,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_os_profile.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/profile.py tests/unit/test_os_profile.py
git commit -m "Parse os: section from hardware profile YAML

Optional section with all-default fallbacks. Existing profiles
without os: get OsProfile defaults automatically."
```

---

### Task 4: Wire os: overrides into _apply_overrides

**Files:**
- Modify: `pmlogsynth/profile.py:569-589` (`_apply_overrides`)
- Test: `tests/unit/test_os_profile.py` (extend)

- [ ] **Step 1: Write failing tests for override merging**

Add to `tests/unit/test_os_profile.py`:

```python
from pmlogsynth.profile import (
    DiskDevice,
    NetworkInterface,
    _apply_overrides,
)


def test_apply_overrides_os_partial() -> None:
    """Overriding os: with partial fields keeps base defaults for the rest."""
    base = HardwareProfile(
        name="base",
        cpus=4,
        memory_kb=16777216,
        os_profile=OsProfile(
            nodename="base-host",
            distro="Ubuntu 22.04.3 LTS",
        ),
    )
    overrides = {
        "os": {
            "nodename": "override-host",
            "distro": "Red Hat Enterprise Linux 9.2",
        }
    }
    result = _apply_overrides(base, overrides)
    assert result.os_profile.nodename == "override-host"
    assert result.os_profile.distro == "Red Hat Enterprise Linux 9.2"
    # Non-overridden fields come from base
    assert result.os_profile.sysname == "Linux"
    assert result.os_profile.pagesize == 4096


def test_apply_overrides_no_os_keeps_base() -> None:
    """Overrides without os: key preserve the base os_profile entirely."""
    base = HardwareProfile(
        name="base",
        cpus=4,
        memory_kb=16777216,
        os_profile=OsProfile(nodename="base-host"),
    )
    overrides = {"cpus": 8}
    result = _apply_overrides(base, overrides)
    assert result.os_profile.nodename == "base-host"
    assert result.cpus == 8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_os_profile.py::test_apply_overrides_os_partial -v`
Expected: FAIL — `_apply_overrides` doesn't handle `os` key

- [ ] **Step 3: Implement os override merging**

Modify `_apply_overrides` in `pmlogsynth/profile.py` (around line 569-589):

```python
def _apply_overrides(base: HardwareProfile, overrides: Dict[str, Any]) -> HardwareProfile:
    """Apply override dict on top of a base HardwareProfile."""
    cpus = overrides.get("cpus", base.cpus)
    memory_kb = overrides.get("memory_kb", base.memory_kb)
    name = overrides.get("name", base.name)
    disks = base.disks
    interfaces = base.interfaces
    os_profile = base.os_profile
    if "disks" in overrides:
        disks = [DiskDevice(name=str(d["name"]), type=d.get("type")) for d in overrides["disks"]]
    if "interfaces" in overrides:
        interfaces = [
            NetworkInterface(name=str(i["name"]), speed_mbps=i.get("speed_mbps"))
            for i in overrides["interfaces"]
        ]
    if "os" in overrides:
        raw_os = overrides["os"]
        os_profile = OsProfile(
            sysname=str(raw_os.get("sysname", base.os_profile.sysname)),
            nodename=str(raw_os["nodename"]) if "nodename" in raw_os else base.os_profile.nodename,
            release=str(raw_os.get("release", base.os_profile.release)),
            version=str(raw_os.get("version", base.os_profile.version)),
            machine=str(raw_os.get("machine", base.os_profile.machine)),
            distro=str(raw_os.get("distro", base.os_profile.distro)),
            pagesize=int(raw_os.get("pagesize", base.os_profile.pagesize)),
        )
    return HardwareProfile(
        name=name,
        cpus=int(cpus),
        memory_kb=int(memory_kb),
        disks=disks,
        interfaces=interfaces,
        os_profile=os_profile,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_os_profile.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run: `pytest tests/unit/ tests/integration/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/profile.py tests/unit/test_os_profile.py
git commit -m "Support os: overrides in hardware profile resolution

Partial os: overrides merge field-by-field with the base profile,
following the same pattern as disks/interfaces overrides."
```

---

### Task 5: Add os: section to all 7 bundled hardware profiles

**Files:**
- Modify: `pmlogsynth/profiles/generic-small.yaml`
- Modify: `pmlogsynth/profiles/generic-medium.yaml`
- Modify: `pmlogsynth/profiles/generic-large.yaml`
- Modify: `pmlogsynth/profiles/generic-xlarge.yaml`
- Modify: `pmlogsynth/profiles/compute-optimized.yaml`
- Modify: `pmlogsynth/profiles/memory-optimized.yaml`
- Modify: `pmlogsynth/profiles/storage-optimized.yaml`

- [ ] **Step 1: Add os: section to each bundled profile**

Each profile gets the same `os:` block (inserted after `memory_kb:`, before `disks:`), with `nodename` matching the profile name:

```yaml
os:
  sysname: Linux
  nodename: <profile-name>
  release: "5.15.0-91-generic"
  version: "#1 SMP PREEMPT_DYNAMIC"
  machine: x86_64
  distro: "Ubuntu 22.04.3 LTS"
  pagesize: 4096
```

Where `<profile-name>` is: `generic-small`, `generic-medium`, `generic-large`, `generic-xlarge`, `compute-optimized`, `memory-optimized`, `storage-optimized`.

- [ ] **Step 2: Verify profiles still load correctly**

Run: `pytest tests/unit/ tests/integration/ -v`
Expected: All PASS (existing tests use tmp_path profiles, not bundled)

Additionally verify manually:
```bash
python -c "from pmlogsynth.profile import ProfileResolver; r = ProfileResolver(); [print(r.resolve(e.name).os_profile) for e in r.list_all()]"
```

- [ ] **Step 3: Commit**

```bash
git add pmlogsynth/profiles/
git commit -m "Add os: metadata to all bundled hardware profiles

Each profile now includes kernel.uname identity for Linux/x86_64
with nodename matching the profile name."
```

---

## Chunk 2: MetadataMetricModel and Writer Integration

### Task 6: Create MetadataMetricModel domain model

**Files:**
- Create: `pmlogsynth/domains/metadata.py`
- Test: `tests/unit/test_domain_metadata.py` (create)

- [ ] **Step 1: Write failing tests for metric descriptors**

Create `tests/unit/test_domain_metadata.py`:

```python
"""Tier 1 unit tests for MetadataMetricModel — no PCP imports."""

from pmlogsynth.domains.metadata import MetadataMetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_DISCRETE,
    PM_TYPE_STRING,
    PM_TYPE_U32,
    PM_TYPE_U64,
    UNITS_NONE,
)
from pmlogsynth.profile import (
    DiskDevice,
    HardwareProfile,
    NetworkInterface,
    OsProfile,
)
from pmlogsynth.sampler import ValueSampler

def _make_hw() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=4,
        memory_kb=16777216,
        disks=[DiskDevice(name="sda"), DiskDevice(name="sdb")],
        interfaces=[NetworkInterface(name="eth0"), NetworkInterface(name="eth1")],
        os_profile=OsProfile(
            sysname="Linux",
            nodename="test-server",
            release="6.1.0-generic",
            version="#2 SMP",
            machine="aarch64",
            distro="Debian 12",
            pagesize=65536,
        ),
    )


def _make_sampler() -> ValueSampler:
    return ValueSampler(noise=0.0, seed=42)


# --- Descriptor tests ---


def test_descriptor_count() -> None:
    """MetadataMetricModel returns exactly 10 descriptors."""
    model = MetadataMetricModel()
    hw = _make_hw()
    assert len(model.metric_descriptors(hw)) == 10


def test_all_descriptors_are_discrete() -> None:
    """Every metadata metric must have is_discrete=True."""
    model = MetadataMetricModel()
    hw = _make_hw()
    for desc in model.metric_descriptors(hw):
        assert desc.is_discrete, f"{desc.name} must be is_discrete=True"


def test_all_descriptors_sem_discrete() -> None:
    """Every metadata metric must have PM_SEM_DISCRETE semantics."""
    model = MetadataMetricModel()
    hw = _make_hw()
    for desc in model.metric_descriptors(hw):
        assert desc.sem == PM_SEM_DISCRETE, f"{desc.name} must be PM_SEM_DISCRETE"


def test_string_metrics_type_code() -> None:
    """kernel.uname.* metrics must have PM_TYPE_STRING type code."""
    model = MetadataMetricModel()
    hw = _make_hw()
    string_names = {
        "kernel.uname.sysname",
        "kernel.uname.nodename",
        "kernel.uname.release",
        "kernel.uname.version",
        "kernel.uname.machine",
        "kernel.uname.distro",
    }
    descs = {d.name: d for d in model.metric_descriptors(hw)}
    for name in string_names:
        assert name in descs, f"Missing descriptor for {name}"
        assert descs[name].type_code == PM_TYPE_STRING, f"{name} must be PM_TYPE_STRING"


def test_integer_metrics_type_codes() -> None:
    """hinv.* integer metrics have correct type codes."""
    model = MetadataMetricModel()
    hw = _make_hw()
    descs = {d.name: d for d in model.metric_descriptors(hw)}
    assert descs["hinv.ndisk"].type_code == PM_TYPE_U32
    assert descs["hinv.physmem"].type_code == PM_TYPE_U64
    assert descs["hinv.pagesize"].type_code == PM_TYPE_U32
    assert descs["hinv.ninterface"].type_code == PM_TYPE_U32


def test_all_descriptors_no_indom() -> None:
    """All metadata metrics are singletons (no instance domain)."""
    model = MetadataMetricModel()
    hw = _make_hw()
    for desc in model.metric_descriptors(hw):
        assert desc.indom is None, f"{desc.name} must have indom=None"


def test_no_duplicate_pmids() -> None:
    """All PMIDs must be unique across descriptors."""
    model = MetadataMetricModel()
    hw = _make_hw()
    pmids = [d.pmid for d in model.metric_descriptors(hw)]
    assert len(pmids) == len(set(pmids)), "Duplicate PMIDs found"


def test_metric_names() -> None:
    """All expected metric names are present."""
    model = MetadataMetricModel()
    hw = _make_hw()
    names = {d.name for d in model.metric_descriptors(hw)}
    expected = {
        "kernel.uname.sysname",
        "kernel.uname.nodename",
        "kernel.uname.release",
        "kernel.uname.version",
        "kernel.uname.machine",
        "kernel.uname.distro",
        "hinv.ndisk",
        "hinv.physmem",
        "hinv.pagesize",
        "hinv.ninterface",
    }
    assert names == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_domain_metadata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pmlogsynth.domains.metadata'`

- [ ] **Step 3: Create MetadataMetricModel — descriptors only**

Create `pmlogsynth/domains/metadata.py`:

```python
"""Metadata domain metric model — OS identity and hardware inventory.

All metrics are discrete (is_discrete=True): written once at archive
creation time, never in the per-sample loop. This matches PCP's
'log mandatory on once' pmlogger configuration group (platform/hinv).
"""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_DISCRETE,
    PM_TYPE_STRING,
    PM_TYPE_U32,
    PM_TYPE_U64,
    UNITS_BYTES,
    UNITS_NONE,
)
from pmlogsynth.profile import HardwareProfile
from pmlogsynth.sampler import ValueSampler

# Units: megabytes — (dimSpace=1, dimTime=0, dimCount=0, scaleSpace=PM_SPACE_MBYTE, 0, 0)
_UNITS_MBYTE = (1, 0, 0, 2, 0, 0)

# PMID cluster 9 — kernel.uname.* in the linux PMDA uses cluster 9
# Item numbers match real linux PMDA for recognisability, though
# exact PMIDs don't need to match (see CLAUDE.md PCP PMID notes).
_UNAME_CLUSTER = 9


class MetadataMetricModel(MetricModel):
    """Generates kernel.uname.* and hinv.* discrete metadata metrics."""

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            # --- kernel.uname.* (string, discrete) ---
            MetricDescriptor(
                name="kernel.uname.sysname",
                pmid=(60, _UNAME_CLUSTER, 0),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.nodename",
                pmid=(60, _UNAME_CLUSTER, 1),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.release",
                pmid=(60, _UNAME_CLUSTER, 2),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.version",
                pmid=(60, _UNAME_CLUSTER, 3),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.machine",
                pmid=(60, _UNAME_CLUSTER, 4),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.distro",
                pmid=(60, _UNAME_CLUSTER, 5),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            # --- hinv.* (integer, discrete) ---
            MetricDescriptor(
                name="hinv.ndisk",
                pmid=(60, 0, 33),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="hinv.physmem",
                pmid=(60, 0, 36),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=_UNITS_MBYTE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="hinv.pagesize",
                pmid=(60, 0, 37),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_BYTES,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="hinv.ninterface",
                pmid=(60, 0, 38),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
        ]

    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: ValueSampler,
    ) -> Dict[str, Dict[Optional[str], Any]]:
        os = hardware.os_profile
        nodename = os.nodename if os.nodename is not None else "synthetic-host"
        return {
            "kernel.uname.sysname": {None: os.sysname},
            "kernel.uname.nodename": {None: nodename},
            "kernel.uname.release": {None: os.release},
            "kernel.uname.version": {None: os.version},
            "kernel.uname.machine": {None: os.machine},
            "kernel.uname.distro": {None: os.distro},
            "hinv.ndisk": {None: len(hardware.disks)},
            "hinv.physmem": {None: hardware.memory_kb // 1024},
            "hinv.pagesize": {None: os.pagesize},
            "hinv.ninterface": {None: len(hardware.interfaces)},
        }
```

- [ ] **Step 4: Run descriptor tests to verify they pass**

Run: `pytest tests/unit/test_domain_metadata.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/domains/metadata.py tests/unit/test_domain_metadata.py
git commit -m "Add MetadataMetricModel with kernel.uname.* and hinv.* metrics

10 discrete metrics: 6 string (OS identity) + 4 integer (hardware
inventory). All is_discrete=True for write-once archive semantics."
```

---

### Task 7: Add compute() tests for MetadataMetricModel

**Files:**
- Test: `tests/unit/test_domain_metadata.py` (extend)

- [ ] **Step 1: Write compute() tests**

Add to `tests/unit/test_domain_metadata.py`:

```python
# --- Compute tests ---


def test_compute_string_values() -> None:
    """compute() returns correct string values from OsProfile."""
    model = MetadataMetricModel()
    hw = _make_hw()
    sampler = _make_sampler()
    values = model.compute(None, hw, 60, sampler)
    assert values["kernel.uname.sysname"][None] == "Linux"
    assert values["kernel.uname.nodename"][None] == "test-server"
    assert values["kernel.uname.release"][None] == "6.1.0-generic"
    assert values["kernel.uname.version"][None] == "#2 SMP"
    assert values["kernel.uname.machine"][None] == "aarch64"
    assert values["kernel.uname.distro"][None] == "Debian 12"


def test_compute_integer_values() -> None:
    """compute() returns correct computed integer values from hardware."""
    model = MetadataMetricModel()
    hw = _make_hw()  # 2 disks, 16GB, 2 NICs, pagesize=65536
    sampler = _make_sampler()
    values = model.compute(None, hw, 60, sampler)
    assert values["hinv.ndisk"][None] == 2
    assert values["hinv.physmem"][None] == 16777216 // 1024  # 16384 MB
    assert values["hinv.pagesize"][None] == 65536
    assert values["hinv.ninterface"][None] == 2


def test_compute_nodename_fallback() -> None:
    """When os_profile.nodename is None, compute() uses 'synthetic-host'."""
    model = MetadataMetricModel()
    hw = HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=8388608,
        os_profile=OsProfile(),  # nodename=None
    )
    sampler = _make_sampler()
    values = model.compute(None, hw, 60, sampler)
    assert values["kernel.uname.nodename"][None] == "synthetic-host"


def test_compute_no_disks_no_interfaces() -> None:
    """compute() handles zero disks and zero interfaces."""
    model = MetadataMetricModel()
    hw = HardwareProfile(
        name="bare",
        cpus=1,
        memory_kb=4194304,
        disks=[],
        interfaces=[],
    )
    sampler = _make_sampler()
    values = model.compute(None, hw, 60, sampler)
    assert values["hinv.ndisk"][None] == 0
    assert values["hinv.ninterface"][None] == 0


def test_compute_returns_all_10_metrics() -> None:
    """compute() returns exactly 10 metric entries."""
    model = MetadataMetricModel()
    hw = _make_hw()
    sampler = _make_sampler()
    values = model.compute(None, hw, 60, sampler)
    assert len(values) == 10
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_domain_metadata.py -v`
Expected: PASS (implementation already done in Task 6)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_domain_metadata.py
git commit -m "Add compute() tests for MetadataMetricModel

Validates string values from OsProfile, computed integer values,
nodename fallback, and edge cases (no disks/interfaces)."
```

---

### Task 8: Register MetadataMetricModel in the writer

**Files:**
- Modify: `pmlogsynth/writer.py:1-17` (imports), `pmlogsynth/writer.py:56-64` (model list)
- Test: `tests/integration/test_writer.py` (extend)

- [ ] **Step 1: Write failing integration test**

Add to `tests/integration/test_writer.py`:

```python
@pytest.mark.integration
def test_writer_metadata_metrics_written_once(tmp_path: Path) -> None:
    """Metadata metrics (kernel.uname.*, hinv.*) are written exactly once as discrete."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    output = str(tmp_path / "out")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        writer.write(timeline=timeline, sampler=sampler)

    # All metadata metrics must appear exactly once in pmiPutValue
    metadata_names = {
        "kernel.uname.sysname",
        "kernel.uname.nodename",
        "kernel.uname.release",
        "kernel.uname.version",
        "kernel.uname.machine",
        "kernel.uname.distro",
        "hinv.ndisk",
        "hinv.physmem",
        "hinv.pagesize",
        "hinv.ninterface",
    }
    put_calls = mock_log.pmiPutValue.call_args_list
    for name in metadata_names:
        calls = [c for c in put_calls if c.args[0] == name]
        assert len(calls) == 1, f"{name} emitted {len(calls)} times; expected 1"


@pytest.mark.integration
def test_writer_metadata_string_values(tmp_path: Path) -> None:
    """String metadata metrics pass string values to pmiPutValue."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    output = str(tmp_path / "out")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        writer.write(timeline=timeline, sampler=sampler)

    # Verify sysname value was passed as a string
    sysname_calls = [
        c for c in mock_log.pmiPutValue.call_args_list
        if c.args[0] == "kernel.uname.sysname"
    ]
    assert len(sysname_calls) == 1
    assert sysname_calls[0].args[2] == "Linux"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_writer.py::test_writer_metadata_metrics_written_once -v`
Expected: FAIL — `kernel.uname.sysname` not found in pmiPutValue calls

- [ ] **Step 3: Register MetadataMetricModel in writer**

Add import to `pmlogsynth/writer.py` (after line 16):

```python
from pmlogsynth.domains.metadata import MetadataMetricModel
```

Add to `self._models` list in `__init__` (after line 63, `SystemMetricModel()`):

```python
            MetadataMetricModel(),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_writer.py::test_writer_metadata_metrics_written_once tests/integration/test_writer.py::test_writer_metadata_string_values -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/unit/ tests/integration/ -v`
Expected: All PASS. Note: the existing `test_writer_discrete_sample_written_once` test checks `pmiWrite.call_count == expected_samples + 1` — this should still pass because there's still exactly 1 discrete write call (all discrete metrics are batched into one `pmiWrite`).

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/writer.py tests/integration/test_writer.py
git commit -m "Register MetadataMetricModel in ArchiveWriter

Metadata metrics are now written as discrete samples alongside
hinv.ncpu. No changes to writer control flow needed."
```

---

## Chunk 3: CLI, Documentation, and Final Validation

### Task 9: Update CLI metric names list

**Files:**
- Modify: `pmlogsynth/cli.py:14-68` (`_ALL_METRIC_NAMES`)
- Test: `tests/unit/test_cli.py` (if exists, or verify via `--list-metrics`)

- [ ] **Step 1: Add new metric names to _ALL_METRIC_NAMES**

Insert the following names into `_ALL_METRIC_NAMES` in lexicographic order:

```python
    "hinv.ncpu",          # already exists
    "hinv.ndisk",         # NEW — after hinv.ncpu
    "hinv.ninterface",    # NEW
    "hinv.pagesize",      # NEW
    "hinv.physmem",       # NEW
    ...
    "kernel.all.blocked",  # existing
    ...
    "kernel.all.load",     # existing
    "kernel.all.pswitch",  # existing
    "kernel.all.running",  # existing
    "kernel.percpu.cpu.idle",  # existing
    ...
    "kernel.uname.distro",    # NEW — after kernel.percpu.cpu.user
    "kernel.uname.machine",   # NEW
    "kernel.uname.nodename",  # NEW
    "kernel.uname.release",   # NEW
    "kernel.uname.sysname",   # NEW
    "kernel.uname.version",   # NEW
```

- [ ] **Step 2: Verify the list is sorted and complete**

Run: `python -c "from pmlogsynth.cli import _ALL_METRIC_NAMES; assert _ALL_METRIC_NAMES == sorted(_ALL_METRIC_NAMES), 'Not sorted'; print(f'{len(_ALL_METRIC_NAMES)} metrics')"`
Expected: `63 metrics` (was 53, +10 new)

- [ ] **Step 3: Commit**

```bash
git add pmlogsynth/cli.py
git commit -m "Add 10 metadata metric names to --list-metrics output"
```

---

### Task 10: Update documentation

**Files:**
- Modify: `docs/profile-format.md` — add `os:` section schema
- Modify: `man/pmlogsynth.1` — update metric count
- Modify: `README.md` — update metric count

- [ ] **Step 1: Update docs/profile-format.md**

Add an `os:` section to the hardware profile schema documentation, documenting all 7 fields, their types, defaults, and that the section is optional.

- [ ] **Step 2: Update man/pmlogsynth.1**

Update the metric count from 53 to 63. Add a brief mention of OS metadata metrics in the DESCRIPTION or METRICS section.

- [ ] **Step 3: Update README.md**

Update the metric count reference to match `len(_ALL_METRIC_NAMES)`.

- [ ] **Step 4: Commit**

```bash
git add docs/profile-format.md man/pmlogsynth.1 README.md
git commit -m "Document os: profile section and update metric counts

profile-format.md: full os: field schema with types and defaults
man page + README: metric count updated to 63"
```

---

### Task 11: Run full quality gate

**Files:** None (validation only)

- [ ] **Step 1: Run pre-commit.sh**

Run: `./pre-commit.sh`
Expected: All checks green — ruff, mypy, unit tests, integration tests

- [ ] **Step 2: Fix any issues**

If ruff or mypy flag issues in the new code, fix them and re-run.

- [ ] **Step 3: Final commit if needed**

If fixes were required, commit them:
```bash
git commit -m "Fix lint/type issues from quality gate"
```

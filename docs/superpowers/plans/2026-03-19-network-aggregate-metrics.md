# Network Aggregate & Error Metrics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `network.all.*` aggregate metrics, per-interface error metrics, and fix existing per-interface PMIDs to match real Linux PMDA assignments.

**Architecture:** Extend `NetworkMetricModel` with 8 new metric descriptors and fix 4 existing PMIDs. Add `error_rate` field to `NetworkStressor` with parser validation. Compute flow: totals first (including errors), accumulate aggregates, then subdivide to per-interface — same pattern as `DiskMetricModel`.

**Tech Stack:** Python 3.8+, pytest, pcp.pmi (via writer.py only)

**Spec:** `docs/superpowers/specs/2026-03-19-network-aggregate-metrics-design.md`

---

## Chunk 1: Core Implementation (Stressor + Model + CLI)

> **Note:** Tasks 2-4 are interdependent — after Task 2 adds new descriptors, `test_domain_descriptors_match_cli_metric_names` will fail until Task 4 updates `cli.py`. Do NOT run `./pre-commit.sh` or push until all of Tasks 1-4 are complete.

### Task 1: Add `error_rate` to NetworkStressor and parser

**Files:**
- Modify: `pmlogsynth/profile.py:133-138` (NetworkStressor dataclass)
- Modify: `pmlogsynth/profile.py:366-378` (`_parse_network_stressor`)
- Create: `tests/unit/test_network_stressor_parsing.py`

- [ ] **Step 1: Write failing tests for error_rate parsing**

Create `tests/unit/test_network_stressor_parsing.py`:

```python
"""Tier 1 tests for NetworkStressor error_rate parsing."""

import pytest

from pmlogsynth.profile import NetworkStressor, ValidationError


def _parse(raw: dict) -> NetworkStressor:
    from pmlogsynth.profile import _parse_network_stressor
    return _parse_network_stressor(raw)


def test_error_rate_parsed_from_yaml() -> None:
    result = _parse({"rx_mbps": 10.0, "error_rate": 0.001})
    assert result.error_rate == 0.001


def test_error_rate_missing_defaults_to_none() -> None:
    result = _parse({"rx_mbps": 10.0})
    assert result.error_rate is None


def test_error_rate_zero_is_valid() -> None:
    result = _parse({"error_rate": 0.0})
    assert result.error_rate == 0.0


def test_error_rate_one_is_valid() -> None:
    result = _parse({"error_rate": 1.0})
    assert result.error_rate == 1.0


def test_error_rate_negative_raises() -> None:
    with pytest.raises(ValidationError, match="error_rate"):
        _parse({"error_rate": -0.1})


def test_error_rate_above_one_raises() -> None:
    with pytest.raises(ValidationError, match="error_rate"):
        _parse({"error_rate": 1.5})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_network_stressor_parsing.py -v`
Expected: FAIL — `NetworkStressor` has no `error_rate` field yet.

- [ ] **Step 3: Add `error_rate` field to NetworkStressor dataclass**

In `pmlogsynth/profile.py`, modify the `NetworkStressor` dataclass (line ~134):

```python
@dataclass
class NetworkStressor:
    rx_mbps: Optional[float] = None
    tx_mbps: Optional[float] = None
    noise: Optional[float] = None
    error_rate: Optional[float] = None
```

- [ ] **Step 4: Update `_parse_network_stressor()` to parse and validate error_rate**

In `pmlogsynth/profile.py`, modify `_parse_network_stressor` (line ~366):

```python
def _parse_network_stressor(raw: Any) -> NetworkStressor:
    if not isinstance(raw, dict):
        raise ValidationError("network stressor must be a mapping")
    noise = raw.get("noise")
    if noise is not None:
        noise = float(noise)
        if not (0.0 <= noise <= 1.0):
            raise ValidationError(f"network.noise must be in [0.0, 1.0], got {noise}")
    error_rate = raw.get("error_rate")
    if error_rate is not None:
        error_rate = float(error_rate)
        if not (0.0 <= error_rate <= 1.0):
            raise ValidationError(
                f"network.error_rate must be in [0.0, 1.0], got {error_rate}"
            )
    return NetworkStressor(
        rx_mbps=float(raw["rx_mbps"]) if "rx_mbps" in raw else None,
        tx_mbps=float(raw["tx_mbps"]) if "tx_mbps" in raw else None,
        noise=noise,
        error_rate=error_rate,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_network_stressor_parsing.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/profile.py tests/unit/test_network_stressor_parsing.py
git commit -m "Add error_rate field to NetworkStressor with validation

Support optional error injection for network metrics.
Validated 0.0-1.0, same pattern as noise field."
```

---

### Task 2: Fix existing PMIDs and add new metric descriptors

**Files:**
- Modify: `pmlogsynth/domains/network.py:24-57` (metric_descriptors method)
- Modify: `tests/unit/test_domain_network.py:37-51` (descriptor tests)

- [ ] **Step 1: Write failing tests for corrected PMIDs and new descriptors**

Add to `tests/unit/test_domain_network.py`, replacing the existing descriptor count/name tests and adding PMID verification. Update the imports at line 4 to include `DiskDevice`:

First, update existing `test_metric_descriptors_count` (line 37-41):

```python
def test_metric_descriptors_count() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    descriptors = model.metric_descriptors(hw)
    assert len(descriptors) == 12
```

Then add new tests after line 51:

```python
# ---------------------------------------------------------------------------
# T021-1b: Corrected PMIDs match real Linux PMDA
# ---------------------------------------------------------------------------


def test_per_interface_pmids_match_linux_pmda() -> None:
    """Per-interface PMIDs use CLUSTER_NET_DEV=3 with Linux item numbers."""
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    by_name = {d.name: d for d in model.metric_descriptors(hw)}

    # ifInOctets=0, ifInUcastPkts=1, ifOutOctets=8, ifOutUcastPkts=9
    assert by_name["network.interface.in.bytes"].pmid == (60, 3, 0)
    assert by_name["network.interface.in.packets"].pmid == (60, 3, 1)
    assert by_name["network.interface.out.bytes"].pmid == (60, 3, 8)
    assert by_name["network.interface.out.packets"].pmid == (60, 3, 9)


def test_per_interface_error_pmids() -> None:
    """Error descriptors use ifInErrors=2, ifOutErrors=10."""
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    by_name = {d.name: d for d in model.metric_descriptors(hw)}

    assert by_name["network.interface.in.errors"].pmid == (60, 3, 2)
    assert by_name["network.interface.out.errors"].pmid == (60, 3, 10)


def test_per_interface_error_descriptors_have_indom() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    by_name = {d.name: d for d in model.metric_descriptors(hw)}

    assert by_name["network.interface.in.errors"].indom == (60, 2)
    assert by_name["network.interface.out.errors"].indom == (60, 2)


def test_aggregate_pmids_use_cluster_90() -> None:
    """Aggregate PMIDs use CLUSTER_NET_ALL=90."""
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    by_name = {d.name: d for d in model.metric_descriptors(hw)}

    assert by_name["network.all.in.bytes"].pmid == (60, 90, 0)
    assert by_name["network.all.in.packets"].pmid == (60, 90, 1)
    assert by_name["network.all.in.errors"].pmid == (60, 90, 2)
    assert by_name["network.all.out.bytes"].pmid == (60, 90, 4)
    assert by_name["network.all.out.packets"].pmid == (60, 90, 5)
    assert by_name["network.all.out.errors"].pmid == (60, 90, 6)


def test_aggregate_descriptors_have_no_indom() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    by_name = {d.name: d for d in model.metric_descriptors(hw)}

    for name in [
        "network.all.in.bytes",
        "network.all.out.bytes",
        "network.all.in.packets",
        "network.all.out.packets",
        "network.all.in.errors",
        "network.all.out.errors",
    ]:
        assert by_name[name].indom is None, f"{name} should have indom=None"


def test_descriptor_names_complete() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    names = {d.name for d in model.metric_descriptors(hw)}
    expected = {
        "network.interface.in.bytes",
        "network.interface.out.bytes",
        "network.interface.in.packets",
        "network.interface.out.packets",
        "network.interface.in.errors",
        "network.interface.out.errors",
        "network.all.in.bytes",
        "network.all.out.bytes",
        "network.all.in.packets",
        "network.all.out.packets",
        "network.all.in.errors",
        "network.all.out.errors",
    }
    assert names == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_domain_network.py::test_metric_descriptors_count tests/unit/test_domain_network.py::test_per_interface_pmids_match_linux_pmda tests/unit/test_domain_network.py::test_aggregate_pmids_use_cluster_90 -v`
Expected: FAIL — count is 4, PMIDs are old values, aggregate names don't exist.

- [ ] **Step 3: Implement corrected and new metric descriptors**

Replace the `metric_descriptors` method in `pmlogsynth/domains/network.py` (lines 23-57):

```python
    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            # Aggregate metrics (network.all.*) — CLUSTER_NET_ALL=90
            MetricDescriptor(
                name="network.all.in.bytes",
                pmid=(60, 90, 0),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_BYTES,
            ),
            MetricDescriptor(
                name="network.all.in.packets",
                pmid=(60, 90, 1),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="network.all.in.errors",
                pmid=(60, 90, 2),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="network.all.out.bytes",
                pmid=(60, 90, 4),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_BYTES,
            ),
            MetricDescriptor(
                name="network.all.out.packets",
                pmid=(60, 90, 5),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="network.all.out.errors",
                pmid=(60, 90, 6),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            # Per-interface metrics — CLUSTER_NET_DEV=3, Linux PMDA item numbers
            MetricDescriptor(
                name="network.interface.in.bytes",
                pmid=(60, 3, 0),
                type_code=PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_BYTES,
            ),
            MetricDescriptor(
                name="network.interface.in.packets",
                pmid=(60, 3, 1),
                type_code=PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="network.interface.in.errors",
                pmid=(60, 3, 2),
                type_code=PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="network.interface.out.bytes",
                pmid=(60, 3, 8),
                type_code=PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_BYTES,
            ),
            MetricDescriptor(
                name="network.interface.out.packets",
                pmid=(60, 3, 9),
                type_code=PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="network.interface.out.errors",
                pmid=(60, 3, 10),
                type_code=PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
        ]
```

- [ ] **Step 4: Run descriptor tests to verify they pass**

Run: `pytest tests/unit/test_domain_network.py -k "descriptor or pmid or aggregate or complete" -v`
Expected: All new descriptor tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/domains/network.py tests/unit/test_domain_network.py
git commit -m "Fix per-interface PMIDs and add network aggregate descriptors

Correct CLUSTER_NET_DEV item numbers to match Linux PMDA.
Add 6 network.all.* aggregate + 2 per-interface error descriptors."
```

---

### Task 3: Implement compute() for aggregates and errors

**Files:**
- Modify: `pmlogsynth/domains/network.py:59-115` (compute method)
- Modify: `tests/unit/test_domain_network.py` (add compute tests)

- [ ] **Step 1: Write failing tests for aggregate compute behavior**

Add to `tests/unit/test_domain_network.py`:

```python
# ---------------------------------------------------------------------------
# T021-9: Aggregate metrics accumulate correctly
# ---------------------------------------------------------------------------


def test_aggregate_bytes_accumulate() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=5.0)

    result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
    result2 = model.compute(stressor, hw, interval=60, sampler=sampler)

    assert result1["network.all.in.bytes"][None] > 0
    assert result2["network.all.in.bytes"][None] > result1["network.all.in.bytes"][None]
    assert result1["network.all.out.bytes"][None] > 0
    assert result2["network.all.out.bytes"][None] > result1["network.all.out.bytes"][None]


def test_aggregate_packets_accumulate() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=5.0)

    result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
    result2 = model.compute(stressor, hw, interval=60, sampler=sampler)

    assert result1["network.all.in.packets"][None] > 0
    assert result2["network.all.in.packets"][None] > result1["network.all.in.packets"][None]


# ---------------------------------------------------------------------------
# T021-10: Sum of per-interface == aggregate (exact match)
# ---------------------------------------------------------------------------


def test_sum_per_interface_equals_aggregate_bytes() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=20.0, tx_mbps=10.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    per_iface_in = sum(result["network.interface.in.bytes"].values())
    per_iface_out = sum(result["network.interface.out.bytes"].values())

    assert per_iface_in == result["network.all.in.bytes"][None]
    assert per_iface_out == result["network.all.out.bytes"][None]


def test_sum_per_interface_equals_aggregate_packets() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=20.0, tx_mbps=10.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    per_iface_in = sum(result["network.interface.in.packets"].values())
    per_iface_out = sum(result["network.interface.out.packets"].values())

    assert per_iface_in == result["network.all.in.packets"][None]
    assert per_iface_out == result["network.all.out.packets"][None]


def test_sum_per_interface_equals_aggregate_errors() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=20.0, tx_mbps=10.0, error_rate=0.01)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    per_iface_in = sum(result["network.interface.in.errors"].values())
    per_iface_out = sum(result["network.interface.out.errors"].values())

    assert per_iface_in == result["network.all.in.errors"][None]
    assert per_iface_out == result["network.all.out.errors"][None]


# ---------------------------------------------------------------------------
# T021-11: Error metrics behavior
# ---------------------------------------------------------------------------


def test_error_rate_none_produces_zero_errors() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=5.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    assert result["network.all.in.errors"][None] == 0
    assert result["network.all.out.errors"][None] == 0
    assert result["network.interface.in.errors"]["eth0"] == 0
    assert result["network.interface.out.errors"]["eth0"] == 0


def test_error_rate_zero_produces_zero_errors() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=5.0, error_rate=0.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    assert result["network.all.in.errors"][None] == 0
    assert result["network.all.out.errors"][None] == 0


def test_error_rate_produces_proportional_errors() -> None:
    model = NetworkMetricModel(mean_packet_bytes=1400)
    hw = _hw_one_iface()
    sampler = _sampler()
    error_rate = 0.01
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=0.0, error_rate=error_rate)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    # 10 * 1024 * 1024 * 60 / 1400 = 449389.7... packets
    # 449389.7 * 0.01 = 4493.897... errors → int(4493.897) = 4493
    expected_packets = 10 * 1024 * 1024 * 60 / 1400
    expected_errors = int(expected_packets * error_rate)
    assert result["network.all.in.errors"][None] == expected_errors


def test_errors_split_evenly_across_interfaces() -> None:
    model = NetworkMetricModel(mean_packet_bytes=1400)
    hw = _hw_two_ifaces()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=20.0, error_rate=0.01)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    eth0_err = result["network.interface.in.errors"]["eth0"]
    eth1_err = result["network.interface.in.errors"]["eth1"]
    assert eth0_err == eth1_err, "Errors should split evenly"
    assert eth0_err > 0


# ---------------------------------------------------------------------------
# T021-12: Edge cases with aggregates
# ---------------------------------------------------------------------------


def _hw_no_ifaces() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=8388608,
        disks=[],
        interfaces=[],
    )


def test_zero_interfaces_aggregates_still_computed() -> None:
    model = NetworkMetricModel()
    hw = _hw_no_ifaces()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=5.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    # Aggregates should still have values
    assert "network.all.in.bytes" in result
    assert result["network.all.in.bytes"][None] > 0
    # Per-interface dicts should be empty
    assert result["network.interface.in.bytes"] == {}


def test_zero_traffic_produces_all_zero_counters() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=0.0, tx_mbps=0.0, error_rate=0.01)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    assert result["network.all.in.bytes"][None] == 0
    assert result["network.all.out.bytes"][None] == 0
    assert result["network.all.in.errors"][None] == 0
    assert result["network.all.out.errors"][None] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_domain_network.py -k "aggregate or error or zero_interfaces or zero_traffic_produces_all" -v`
Expected: FAIL — `network.all.*` keys not in result dict.

- [ ] **Step 2b: Update existing test that iterates all metric keys**

The existing `test_instance_names_match_hardware_interfaces` (line 59-72) iterates `for metric_name in result` and asserts all keys have `{"eth0", "eth1"}` instances. After adding `network.all.*` keys (which have `{None}` instances), this test will break. Update it to only check per-interface metrics:

In `tests/unit/test_domain_network.py`, replace `test_instance_names_match_hardware_interfaces`:

```python
def test_instance_names_match_hardware_interfaces() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=5.0)
    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    for metric_name in result:
        if metric_name.startswith("network.all."):
            # Aggregate metrics have no instances
            assert set(result[metric_name].keys()) == {None}
            continue
        instance_keys = set(result[metric_name].keys())
        assert instance_keys == {"eth0", "eth1"}, (
            "Expected instances {{eth0, eth1}}, got {} for {}".format(
                instance_keys, metric_name
            )
        )
```

- [ ] **Step 3: Implement updated compute() method**

Replace the `compute` method in `pmlogsynth/domains/network.py` (lines 59-115):

```python
    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: ValueSampler,
    ) -> Dict[str, Dict[Optional[str], Any]]:
        net = stressor if isinstance(stressor, NetworkStressor) else NetworkStressor()

        rx_mbps = net.rx_mbps if net.rx_mbps is not None else _DEFAULT_RX_MBPS
        tx_mbps = net.tx_mbps if net.tx_mbps is not None else _DEFAULT_TX_MBPS
        error_rate = net.error_rate if net.error_rate is not None else _DEFAULT_ERROR_RATE
        noise = net.noise

        noisy_rx = sampler.apply_noise(rx_mbps, noise)
        noisy_tx = sampler.apply_noise(tx_mbps, noise)

        in_bytes = noisy_rx * 1024 * 1024 * interval
        out_bytes = noisy_tx * 1024 * 1024 * interval
        in_packets = (
            in_bytes / self._mean_packet_bytes if self._mean_packet_bytes > 0 else 0.0
        )
        out_packets = (
            out_bytes / self._mean_packet_bytes if self._mean_packet_bytes > 0 else 0.0
        )
        in_errors = in_packets * error_rate
        out_errors = out_packets * error_rate

        # Accumulate aggregates (scalar, no indom)
        result: Dict[str, Dict[Optional[str], Any]] = {
            "network.all.in.bytes": {
                None: sampler.accumulate("network.all.in.bytes", in_bytes)
            },
            "network.all.out.bytes": {
                None: sampler.accumulate("network.all.out.bytes", out_bytes)
            },
            "network.all.in.packets": {
                None: sampler.accumulate("network.all.in.packets", in_packets)
            },
            "network.all.out.packets": {
                None: sampler.accumulate("network.all.out.packets", out_packets)
            },
            "network.all.in.errors": {
                None: sampler.accumulate("network.all.in.errors", in_errors)
            },
            "network.all.out.errors": {
                None: sampler.accumulate("network.all.out.errors", out_errors)
            },
        }

        # Per-interface split
        num_ifaces = len(hardware.interfaces)
        in_b: Dict[Optional[str], Any] = {}
        out_b: Dict[Optional[str], Any] = {}
        in_p: Dict[Optional[str], Any] = {}
        out_p: Dict[Optional[str], Any] = {}
        in_e: Dict[Optional[str], Any] = {}
        out_e: Dict[Optional[str], Any] = {}

        if num_ifaces > 0:
            per_in_bytes = in_bytes / num_ifaces
            per_out_bytes = out_bytes / num_ifaces
            per_in_pkt = in_packets / num_ifaces
            per_out_pkt = out_packets / num_ifaces
            per_in_err = in_errors / num_ifaces
            per_out_err = out_errors / num_ifaces
            for iface in hardware.interfaces:
                name = iface.name
                in_b[name] = sampler.accumulate(
                    "net.in.bytes.{}".format(name), per_in_bytes
                )
                out_b[name] = sampler.accumulate(
                    "net.out.bytes.{}".format(name), per_out_bytes
                )
                in_p[name] = sampler.accumulate(
                    "net.in.pkts.{}".format(name), per_in_pkt
                )
                out_p[name] = sampler.accumulate(
                    "net.out.pkts.{}".format(name), per_out_pkt
                )
                in_e[name] = sampler.accumulate(
                    "net.in.errs.{}".format(name), per_in_err
                )
                out_e[name] = sampler.accumulate(
                    "net.out.errs.{}".format(name), per_out_err
                )

        result["network.interface.in.bytes"] = in_b
        result["network.interface.out.bytes"] = out_b
        result["network.interface.in.packets"] = in_p
        result["network.interface.out.packets"] = out_p
        result["network.interface.in.errors"] = in_e
        result["network.interface.out.errors"] = out_e

        return result
```

Also add the default constant near the top of the file (after line 13):

```python
_DEFAULT_ERROR_RATE = 0.0
```

- [ ] **Step 4: Run all network domain tests**

Run: `pytest tests/unit/test_domain_network.py -v`
Expected: All tests PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/domains/network.py tests/unit/test_domain_network.py
git commit -m "Implement network aggregate compute and error metrics

Totals-first pattern matching disk domain. Errors driven
by optional error_rate stressor field, default 0."
```

---

### Task 4: Update CLI metric list

**Files:**
- Modify: `pmlogsynth/cli.py:14-78` (`_ALL_METRIC_NAMES`)
- Modify: `tests/unit/test_list_metrics.py:9-80` (`EXPECTED_METRICS`)

- [ ] **Step 1: Update test expectations first (TDD)**

In `tests/unit/test_list_metrics.py`:

Update the comment on line 9:
```python
# Expected 71 metric names (63 previous + 8 network aggregate/error)
```

Add 8 new metric names to the `EXPECTED_METRICS` set (after line 35, the existing network metrics):
```python
    # New network aggregate + error metrics
    "network.all.in.bytes",
    "network.all.in.errors",
    "network.all.in.packets",
    "network.all.out.bytes",
    "network.all.out.errors",
    "network.all.out.packets",
    "network.interface.in.errors",
    "network.interface.out.errors",
```

Update `test_list_metrics_contains_53_names` (line 98-101):
```python
@pytest.mark.unit
def test_list_metrics_contains_53_names() -> None:
    """--list-metrics output contains exactly 71 metric names."""
    lines = _capture_list_metrics()
    assert len(lines) == 71, f"Expected 71 metrics, got {len(lines)}: {lines}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_list_metrics.py::test_list_metrics_contains_53_names -v`
Expected: FAIL — still 63 metrics.

- [ ] **Step 3: Replace network entries in `_ALL_METRIC_NAMES` in cli.py**

In `pmlogsynth/cli.py`, **delete** the existing 4 `network.interface.*` entries (lines 71-74):
```python
    # DELETE these 4 lines:
    "network.interface.in.bytes",
    "network.interface.in.packets",
    "network.interface.out.bytes",
    "network.interface.out.packets",
```

Then insert these 12 entries in their place (sorted order):
```python
    "network.all.in.bytes",
    "network.all.in.errors",
    "network.all.in.packets",
    "network.all.out.bytes",
    "network.all.out.errors",
    "network.all.out.packets",
    "network.interface.in.bytes",
    "network.interface.in.errors",
    "network.interface.in.packets",
    "network.interface.out.bytes",
    "network.interface.out.errors",
    "network.interface.out.packets",
```

Net change: remove 4, add 12 = +8 new metrics (63 → 71 total).

- [ ] **Step 4: Run all list-metrics tests**

Run: `pytest tests/unit/test_list_metrics.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/cli.py tests/unit/test_list_metrics.py
git commit -m "Add 8 network metrics to --list-metrics output

Total metric count: 63 -> 71."
```

---

## Chunk 2: Documentation Updates

### Task 5: Update docs/profile-format.md

**Files:**
- Modify: `docs/profile-format.md` (network stressor section)

- [ ] **Step 1: Add `error_rate` field to the network stressor documentation**

Find the network stressor YAML example in `docs/profile-format.md` and add `error_rate`:

```yaml
network:
  rx_mbps: 500.0        # receive throughput MB/s, default 0.0
  tx_mbps: 100.0        # transmit throughput MB/s, default 0.0
  noise: 0.03           # per-domain noise override
  error_rate: 0.001     # fraction of packets that are errors [0.0-1.0], default 0.0
```

If there is a field table, add a row:

| Field | Type | Default | Constraint | Description |
|-------|------|---------|------------|-------------|
| `error_rate` | float | `0.0` | `[0.0, 1.0]` | Fraction of packets that are errors |

- [ ] **Step 2: Commit**

```bash
git add docs/profile-format.md
git commit -m "Document network error_rate field in profile format"
```

---

### Task 6: Update man page

**Files:**
- Modify: `man/pmlogsynth.1` (network metrics section, around line 429)

- [ ] **Step 1: Update the Network metrics section**

Find the `Network (network domain)` section and update it to include all 12 metrics:

```nroff
.SS Network (network domain)
.TP
.BR network.all.in.bytes ", " network.all.out.bytes
Aggregate receive/transmit bytes across all interfaces (cumulative counter).
.TP
.BR network.all.in.packets ", " network.all.out.packets
Aggregate receive/transmit packet counts across all interfaces (cumulative counter).
.TP
.BR network.all.in.errors ", " network.all.out.errors
Aggregate receive/transmit error counts across all interfaces (cumulative counter).
Driven by optional
.B error_rate
stressor field; defaults to zero.
.TP
.BR network.interface.in.bytes ", " network.interface.out.bytes
Per-interface receive/transmit bytes (cumulative counter).
.TP
.BR network.interface.in.packets ", " network.interface.out.packets
Per-interface receive/transmit packet counts (cumulative counter).
.TP
.BR network.interface.in.errors ", " network.interface.out.errors
Per-interface receive/transmit error counts (cumulative counter).
.PP
All per-interface instance names match
.I interface.name
fields in the hardware profile.
```

- [ ] **Step 2: Commit**

```bash
git add man/pmlogsynth.1
git commit -m "Update man page with network aggregate and error metrics"
```

---

### Task 7: Update README.md metric count

**Files:**
- Modify: `README.md` (line 181, metric count)

- [ ] **Step 1: Update the metric count**

Change line 181 from:
```
63 PCP metrics — `pmlogsynth --list-metrics` or `man pmlogsynth`.
```
To:
```
71 PCP metrics — `pmlogsynth --list-metrics` or `man pmlogsynth`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Update README metric count 63 -> 71"
```

---

### Task 8: Run full quality gate

- [ ] **Step 1: Run pre-commit.sh**

```bash
./pre-commit.sh
```

Expected: All checks pass — ruff, mypy, unit tests, integration tests.

- [ ] **Step 2: Fix any issues found**

If ruff or mypy flag anything, fix and re-run.

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -u
git commit -m "Fix lint/type issues from quality gate"
```

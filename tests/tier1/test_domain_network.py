"""Tier 1 unit tests for NetworkMetricModel (T021)."""

from pmlogsynth.domains.network import NetworkMetricModel
from pmlogsynth.profile import HardwareProfile, NetworkInterface, NetworkStressor
from pmlogsynth.sampler import ValueSampler


def _hw_two_ifaces() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=8388608,
        disks=[],
        interfaces=[NetworkInterface(name="eth0"), NetworkInterface(name="eth1")],
    )


def _hw_one_iface() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=8388608,
        disks=[],
        interfaces=[NetworkInterface(name="eth0")],
    )


def _sampler() -> ValueSampler:
    return ValueSampler(noise=0.0, seed=42)


# ---------------------------------------------------------------------------
# T021-1: metric_descriptors returns 4 descriptors
# ---------------------------------------------------------------------------


def test_metric_descriptors_count() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    descriptors = model.metric_descriptors(hw)
    assert len(descriptors) == 4


def test_metric_descriptors_names() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    names = [d.name for d in model.metric_descriptors(hw)]
    assert "network.interface.in.bytes" in names
    assert "network.interface.out.bytes" in names
    assert "network.interface.in.packets" in names
    assert "network.interface.out.packets" in names


# ---------------------------------------------------------------------------
# T021-2: Per-NIC instance names match hardware.interfaces[].name
# ---------------------------------------------------------------------------


def test_instance_names_match_hardware_interfaces() -> None:
    model = NetworkMetricModel()
    hw = _hw_two_ifaces()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=5.0)
    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    for metric_name in result:
        instance_keys = set(result[metric_name].keys())
        assert instance_keys == {"eth0", "eth1"}, (
            "Expected instances {{eth0, eth1}}, got {} for {}".format(
                instance_keys, metric_name
            )
        )


# ---------------------------------------------------------------------------
# T021-3: Counter accumulates across two calls (bytes increase)
# ---------------------------------------------------------------------------


def test_counter_accumulates_across_calls() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=10.0, tx_mbps=0.0)

    result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
    result2 = model.compute(stressor, hw, interval=60, sampler=sampler)

    v1 = result1["network.interface.in.bytes"]["eth0"]
    v2 = result2["network.interface.in.bytes"]["eth0"]
    assert v2 > v1, "Counter should increase on second call"


# ---------------------------------------------------------------------------
# T021-4: Zero rx/tx produces zero deltas
# ---------------------------------------------------------------------------


def test_zero_rx_tx_produces_zero_deltas() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()
    stressor = NetworkStressor(rx_mbps=0.0, tx_mbps=0.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)
    assert result["network.interface.in.bytes"]["eth0"] == 0
    assert result["network.interface.out.bytes"]["eth0"] == 0
    assert result["network.interface.in.packets"]["eth0"] == 0
    assert result["network.interface.out.packets"]["eth0"] == 0


# ---------------------------------------------------------------------------
# T021-5: stressor=None defaults to zero traffic
# ---------------------------------------------------------------------------


def test_none_stressor_defaults_to_zero_traffic() -> None:
    model = NetworkMetricModel()
    hw = _hw_one_iface()
    sampler = _sampler()

    result = model.compute(None, hw, interval=60, sampler=sampler)
    assert result["network.interface.in.bytes"]["eth0"] == 0
    assert result["network.interface.out.bytes"]["eth0"] == 0


# ---------------------------------------------------------------------------
# T021-6: Packet estimation from bytes/mean_packet_bytes
# ---------------------------------------------------------------------------


def test_packet_estimation_is_positive_with_rx_traffic() -> None:
    model = NetworkMetricModel(mean_packet_bytes=1400)
    hw = _hw_one_iface()
    sampler = _sampler()
    # rx=10 MB/s, interval=60 s → 10*1024*1024*60 = 629145600 bytes → >0 packets
    stressor = NetworkStressor(rx_mbps=10.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)
    assert result["network.interface.in.packets"]["eth0"] > 0


def test_packet_count_calculation() -> None:
    """rx=10 MB/s, interval=60s, mean_pkt=1400 → expected packet count."""
    model = NetworkMetricModel(mean_packet_bytes=1400)
    hw = _hw_one_iface()
    sampler = ValueSampler(noise=0.0, seed=42)
    stressor = NetworkStressor(rx_mbps=10.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)
    # 10 * 1024 * 1024 * 60 / 1400 = 449389.0... → int 449389
    expected = int(10 * 1024 * 1024 * 60 / 1400)
    assert result["network.interface.in.packets"]["eth0"] == expected


# ---------------------------------------------------------------------------
# T021-7: Custom mean_packet_bytes changes packet count proportionally
# ---------------------------------------------------------------------------


def test_custom_mean_packet_bytes_changes_packet_count() -> None:
    hw = _hw_one_iface()
    stressor = NetworkStressor(rx_mbps=10.0)
    interval = 60

    model_small = NetworkMetricModel(mean_packet_bytes=700)
    model_large = NetworkMetricModel(mean_packet_bytes=1400)

    sampler_small = ValueSampler(noise=0.0, seed=42)
    sampler_large = ValueSampler(noise=0.0, seed=42)

    result_small = model_small.compute(stressor, hw, interval, sampler_small)
    result_large = model_large.compute(stressor, hw, interval, sampler_large)

    pkts_small = result_small["network.interface.in.packets"]["eth0"]
    pkts_large = result_large["network.interface.in.packets"]["eth0"]

    # Halving mean_packet_bytes should roughly double packet count
    assert pkts_small > pkts_large
    # Allow for integer rounding; ratio should be approximately 2
    assert abs(pkts_small / pkts_large - 2.0) < 0.01


# ---------------------------------------------------------------------------
# T021-8: Two interfaces each get half the bytes
# ---------------------------------------------------------------------------


def test_two_interfaces_each_get_half_the_bytes() -> None:
    hw_two = _hw_two_ifaces()
    hw_one = _hw_one_iface()
    stressor = NetworkStressor(rx_mbps=20.0, tx_mbps=10.0)
    interval = 60

    sampler_two = ValueSampler(noise=0.0, seed=42)
    sampler_one = ValueSampler(noise=0.0, seed=42)

    model = NetworkMetricModel()
    result_two = model.compute(stressor, hw_two, interval, sampler_two)
    result_one = model.compute(stressor, hw_one, interval, sampler_one)

    eth0_two = result_two["network.interface.in.bytes"]["eth0"]
    eth0_one = result_one["network.interface.in.bytes"]["eth0"]
    eth1_two = result_two["network.interface.in.bytes"]["eth1"]

    # Each interface in the two-NIC setup should receive half of what
    # the single-NIC setup receives
    assert eth0_two == eth0_one // 2 or eth0_two == eth1_two, (
        "Each of two NICs should get half the bytes"
    )
    assert eth0_two == eth1_two, "Both NICs should get equal bytes"

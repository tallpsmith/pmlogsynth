"""Network domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.profile import HardwareProfile, NetworkStressor
from pmlogsynth.sampler import ValueSampler

_PM_TYPE_U64 = 3
_PM_SEM_COUNTER = 1
_UNITS_BYTES = (1, 0, 0, 0, 0, 0)
_UNITS_COUNT = (0, 0, 1, 0, 0, 0)
_NET_INDOM = (60, 2)

_DEFAULT_RX_MBPS = 0.0
_DEFAULT_TX_MBPS = 0.0
_DEFAULT_MEAN_PACKET_BYTES = 1400


class NetworkMetricModel(MetricModel):
    """Metric model for network interface throughput counters."""

    def __init__(self, mean_packet_bytes: int = _DEFAULT_MEAN_PACKET_BYTES) -> None:
        self._mean_packet_bytes = mean_packet_bytes

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            MetricDescriptor(
                name="network.interface.in.bytes",
                pmid=(60, 3, 3),
                type_code=_PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_BYTES,
            ),
            MetricDescriptor(
                name="network.interface.out.bytes",
                pmid=(60, 3, 11),
                type_code=_PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_BYTES,
            ),
            MetricDescriptor(
                name="network.interface.in.packets",
                pmid=(60, 3, 0),
                type_code=_PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_COUNT,
            ),
            MetricDescriptor(
                name="network.interface.out.packets",
                pmid=(60, 3, 8),
                type_code=_PM_TYPE_U64,
                indom=_NET_INDOM,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_COUNT,
            ),
        ]

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

        num_ifaces = len(hardware.interfaces)
        in_b: Dict[Optional[str], Any] = {}
        out_b: Dict[Optional[str], Any] = {}
        in_p: Dict[Optional[str], Any] = {}
        out_p: Dict[Optional[str], Any] = {}

        if num_ifaces > 0:
            per_in_bytes = in_bytes / num_ifaces
            per_out_bytes = out_bytes / num_ifaces
            per_in_pkt = in_packets / num_ifaces
            per_out_pkt = out_packets / num_ifaces
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

        return {
            "network.interface.in.bytes": in_b,
            "network.interface.out.bytes": out_b,
            "network.interface.in.packets": in_p,
            "network.interface.out.packets": out_p,
        }

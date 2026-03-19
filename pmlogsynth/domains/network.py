"""Network domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.pcp_constants import PM_SEM_COUNTER, PM_TYPE_U64, UNITS_BYTES, UNITS_COUNT
from pmlogsynth.profile import HardwareProfile, NetworkStressor
from pmlogsynth.sampler import ValueSampler

_NET_INDOM = (60, 2)

_DEFAULT_RX_MBPS = 0.0
_DEFAULT_TX_MBPS = 0.0
_DEFAULT_MEAN_PACKET_BYTES = 1400
_DEFAULT_ERROR_RATE = 0.0


class NetworkMetricModel(MetricModel):
    """Metric model for network interface throughput counters."""

    def __init__(self, mean_packet_bytes: int = _DEFAULT_MEAN_PACKET_BYTES) -> None:
        self._mean_packet_bytes = mean_packet_bytes

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

        # Per-interface split — computed first so aggregates can sum from ints
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

        # Aggregates are the exact sum of per-interface int values to avoid
        # truncation drift between independently-accumulated counters.
        # When there are no interfaces, accumulate the full float directly.
        if num_ifaces > 0:
            agg_in_bytes = sum(in_b.values())
            agg_out_bytes = sum(out_b.values())
            agg_in_pkt = sum(in_p.values())
            agg_out_pkt = sum(out_p.values())
            agg_in_err = sum(in_e.values())
            agg_out_err = sum(out_e.values())
        else:
            agg_in_bytes = sampler.accumulate("network.all.in.bytes", in_bytes)
            agg_out_bytes = sampler.accumulate("network.all.out.bytes", out_bytes)
            agg_in_pkt = sampler.accumulate("network.all.in.packets", in_packets)
            agg_out_pkt = sampler.accumulate("network.all.out.packets", out_packets)
            agg_in_err = sampler.accumulate("network.all.in.errors", in_errors)
            agg_out_err = sampler.accumulate("network.all.out.errors", out_errors)

        return {
            "network.all.in.bytes": {None: agg_in_bytes},
            "network.all.out.bytes": {None: agg_out_bytes},
            "network.all.in.packets": {None: agg_in_pkt},
            "network.all.out.packets": {None: agg_out_pkt},
            "network.all.in.errors": {None: agg_in_err},
            "network.all.out.errors": {None: agg_out_err},
            "network.interface.in.bytes": in_b,
            "network.interface.out.bytes": out_b,
            "network.interface.in.packets": in_p,
            "network.interface.out.packets": out_p,
            "network.interface.in.errors": in_e,
            "network.interface.out.errors": out_e,
        }

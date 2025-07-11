# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for esxi ping."""

import logging
import re
from typing import TYPE_CHECKING

from mfd_common_libs import add_logging_level, log_levels

from mfd_ping import PingResult, LinuxPing
from mfd_ping.base import IPv4_ICMP_HEADER, IPv6_ICMP_HEADER
from mfd_ping.exceptions import PingException

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address
    from netaddr import IPAddress

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class EsxiPing(LinuxPing):
    """Class responsible for handling ping method on ESXi OS."""

    def _prepare_arguments(  # noqa C901
        self,
        *,
        dst_ip: "IPv4Address | IPv6Address | IPAddress",
        mtu: int | None,
        count: int | None,
        packet_size: int | None,
        src_ip: "IPv4Address | IPv6Address | IPAddress | None",
        timeout: int | None,
        frag: bool | None,
        ttl: int | None,
        broadcast: bool | None,
        args: str | None,
    ) -> str:
        """Get prepared arguments to ping, as string from passed parameters."""
        arguments = []
        is_ipv6 = dst_ip.version == 6
        if is_ipv6:
            arguments.append("-6")
        if count:
            arguments.append(f"-c {count}")
        if src_ip:
            from mfd_esxi.host import ESXiHypervisor

            # ESXi requires specifying source interface rather than IP address
            host = ESXiHypervisor(self._connection)
            host.initialize_vmknic()
            interface = host.find_vmknic(ip=src_ip).name
            arguments.append(f"-I {interface}")
        if timeout:
            arguments.append(f"-W {timeout}")
        if frag is False:
            arguments.append("-d")
        if mtu:
            value = IPv6_ICMP_HEADER if is_ipv6 else IPv4_ICMP_HEADER
            arguments.append(f"-s {mtu-value}")
        if packet_size:
            if not mtu:
                arguments.append(f"-s {packet_size}")
            else:
                logger.log(level=log_levels.MODULE_DEBUG, msg="Not using packet_size, because passed MTU.")
        if ttl:
            arguments.append(f"-t {ttl}")
        if broadcast:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Broadcast is not supported with ESXi, skipping argument.")
        if args:
            arguments.append(args)
        arguments.append(str(dst_ip))
        return " ".join(arguments)

    def _parse_output(self, result: str) -> "PingResult":
        """
        Read ping statistics from output.

        2 flows are supported. With summary of ping and without.

        :param result: Output from ping tool
        :return: DataClass PingResult with pass_count and fail_count of ping requests.
        """
        ping_tries = len(result.strip().splitlines()) - 1  # remove header of ping
        # flow with summary in output
        if "ping statistics" in result:
            count_regex = (
                r"^(?P<transmitted_count>\d+)\spackets transmitted,"
                r"\s(?P<received_count>\d+)\spackets received,"
                r"(\s\+(?P<packets_duplicates>\d+)\sduplicates,)?"
                r"\s(?P<packet_loss>\d+\.?\d*)% packet loss"
                r"(\n^round-trip min/avg/max = "
                r"(?P<rtt_min>\d+\.\d+)/(?P<rtt_avg>\d+\.\d+)/(?P<rtt_max>\d+\.\d+)\sms)?"
            )
            count_match = re.search(count_regex, result, re.M)
            if count_match:
                transmitted = int(count_match.group("transmitted_count"))
                received = int(count_match.group("received_count"))
                packet_loss = int(count_match.group("packet_loss"))
                rtt_min = float(count_match.group("rtt_min")) if count_match.group("rtt_min") else None
                rtt_avg = float(count_match.group("rtt_avg")) if count_match.group("rtt_avg") else None
                rtt_max = float(count_match.group("rtt_max")) if count_match.group("rtt_max") else None
                packets_duplicates = (
                    int(count_match.group("packets_duplicates")) if count_match.group("packets_duplicates") else None
                )
                return PingResult(
                    pass_count=received,
                    fail_count=transmitted - received,
                    packets_transmitted=transmitted,
                    packets_received=received,
                    packets_duplicates=packets_duplicates,
                    packet_loss=packet_loss,
                    rtt_min=rtt_min,
                    rtt_avg=rtt_avg,
                    rtt_max=rtt_max,
                )
        elif ping_tries > 0:
            # 64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.101 ms
            # 64 bytes from ::1: icmp_seq=0 time=0.156 ms
            reply_regex = r"icmp_seq=(?P<icmp_seq_val>\d+) "
            reply_matches = re.findall(reply_regex, result)
            if reply_matches:
                pass_count = len(reply_matches)
                fail_count = abs(pass_count - (int(reply_matches[-1]) + 1))
                return PingResult(pass_count, fail_count)
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Ping output:\n{result}")
        raise PingException("Cannot parse output from ping")

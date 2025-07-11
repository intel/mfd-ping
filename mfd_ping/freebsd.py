# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for FreeBSD ping."""

import logging
import re
from typing import TYPE_CHECKING

from mfd_common_libs import add_logging_level, log_levels

from mfd_ping import PingResult, LinuxPing
from .base import IPv4_ICMP_HEADER, IPv6_ICMP_HEADER
from .exceptions import PingException

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address
    from netaddr import IPAddress


logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class FreeBSDPing(LinuxPing):
    """Class responsible for handling ping method on FreeBSD OS."""

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
        if mtu:
            value = IPv6_ICMP_HEADER if is_ipv6 else IPv4_ICMP_HEADER
            arguments.append(f"-s {mtu-value}")
        if count:
            arguments.append(f"-c {count}")
        if packet_size:
            if not mtu:
                arguments.append(f"-s {packet_size}")
                if dst_ip.version == 6 and packet_size > 8192:
                    arguments.append(f"-b {packet_size * 2}")
            else:
                logger.log(level=log_levels.MODULE_DEBUG, msg="Not using packet_size, because passed MTU.")
        if src_ip:
            arguments.append(f"-S {src_ip}")
        if timeout:
            arguments.append(f"-t {timeout}")
        if frag is False:
            arguments.append("-D")
        if ttl:
            arguments.append(f"-T {ttl}")
        if broadcast:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Broadcast option is not supported on FreeBSD OS!")
        if args:
            arguments.append(args)
        arguments.append(str(dst_ip))
        return " ".join(arguments)

    def _parse_output(self, result: str) -> "PingResult":
        """
        Read ping statistics from output.

        2 flows are supported. With summary of ping and without.

        :param result: Output from ping tool
        :return: DataClass PingResult with pass_count and fail_count of ping requests
        """
        ping_tries = len(result.strip().splitlines()) - 1  # remove header of ping
        # flow with summary in output
        if re.search(r"ping[6]? statistics", result, re.MULTILINE) is not None:
            regex = (
                r"^(?P<packets_transmitted>\d+) packets transmitted, "
                r"(?P<packets_received>\d+) packets received, "
                r"(\+(?P<packets_duplicates>\d+) duplicates, )?"
                r"(?P<packet_loss>\d+\.\d+)% packet loss"
                r"(\n^round-trip min/avg/max/std-?dev = "
                r"(?P<rtt_min>\d+\.\d+)/(?P<rtt_avg>\d+\.\d+)/(?P<rtt_max>\d+\.\d+)/(?P<rtt_stddev>\d+\.\d+) ms)?"
            )
            match = re.search(regex, result, re.MULTILINE)
            if match:
                return PingResult(
                    pass_count=int(match.group("packets_received")),
                    fail_count=int(match.group("packets_transmitted")) - int(match.group("packets_received")),
                    packets_transmitted=int(match.group("packets_transmitted")),
                    packets_received=int(match.group("packets_received")),
                    packets_duplicates=int(match.group("packets_duplicates"))
                    if match.group("packets_duplicates")
                    else None,
                    packet_loss=float(match.group("packet_loss")),
                    rtt_min=float(match.group("rtt_min")) if match.group("rtt_min") else None,
                    rtt_avg=float(match.group("rtt_avg")) if match.group("rtt_avg") else None,
                    rtt_max=float(match.group("rtt_max")) if match.group("rtt_max") else None,
                )

        elif ping_tries > 0:
            # 64 bytes from 127.0.0.1: icmp_seq=0 ttl=64 time=0.043 ms
            # 64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.041 ms
            reply_regex = r"icmp_seq=(?P<icmp_seq_val>\d+) "
            reply_matches = re.findall(reply_regex, result)
            if reply_matches:
                pass_count = len(reply_matches)
                fail_count = abs(pass_count - (int(reply_matches[-1]) + 1))
                return PingResult(pass_count, fail_count)
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Ping output:\n{result}")
        raise PingException("Cannot parse output from ping")

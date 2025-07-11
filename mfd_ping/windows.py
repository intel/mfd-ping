# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for Windows ping."""

import logging
import re
from typing import TYPE_CHECKING

from mfd_common_libs import add_logging_level, log_levels, TimeoutCounter

from mfd_ping import Ping, PingResult
from mfd_ping.base import IPv4_ICMP_HEADER, IPv6_ICMP_HEADER
from mfd_ping.exceptions import PingException

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address
    from netaddr import IPAddress

    from mfd_connect.process import RemoteProcess

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class WindowsPing(Ping):
    """Class responsible for handling ping method on Windows OS."""

    def start(
        self,
        *,
        dst_ip: "IPv4Address | IPv6Address | IPAddress | str",
        mtu: int | None = None,
        count: int | None = None,
        packet_size: int | None = None,
        src_ip: "IPv4Address | IPv6Address | IPAddress | str | None" = None,
        timeout: int | None = None,
        frag: bool | None = None,
        ttl: int | None = None,
        broadcast: bool | None = None,
        args: str | None = None,
        output_file: str | None = None,
        **kwargs,
    ) -> "RemoteProcess":
        """
        Start pinging destination machine.

        :param dst_ip: Destination IP address to perform ping
        :param mtu: Value of maximum transmission unit. Overriding usage of packet_size
        :param count: Number of echo requests to send
        :param packet_size: Size of ping packet in bytes. Not compatible with mtu. MTU size will be used instead.
        :param src_ip: Source IP address to use ping
        :param timeout: Program execution timeout, in seconds
        :param frag: Enable fragmentation
        :param ttl: Time-To-Live value
        :param broadcast: Broadcast ping
        :param args: Additional arguments to ping method
        :param output_file: path to file where log will be saved
        :return: OS process with ping.
        :raises PingException:  if addresses are incorrect.
                                if ping command fails on execution
                                if passed incorrect args
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg="Starting ping.")

        dst_ip, src_ip = self._parse_ip_addresses(dst_ip=dst_ip, src_ip=src_ip)

        if src_ip and src_ip.version != dst_ip.version:
            raise PingException("Source IP address is not in the same version as destination IP")
        arguments = self._prepare_arguments(
            dst_ip=dst_ip,
            mtu=mtu,
            count=count,
            packet_size=packet_size,
            src_ip=src_ip,
            timeout=timeout,
            ttl=ttl,
            broadcast=broadcast,
            frag=frag,
            args=args,
        )
        command = f"ping {arguments}"
        try:
            ping_process = self._connection.start_process(command, output_file=output_file)
        except Exception as e:
            raise PingException("Problem with execution of ping command") from e
        # waiting for eventually bad arguments, output available after end of process
        timeout = TimeoutCounter(1)
        while not timeout:
            if not ping_process.running and "Bad option" in ping_process.stdout_text:
                raise PingException("Passed unsupported option as args")
        logger.log(level=log_levels.MODULE_DEBUG, msg="Started ping.")
        return ping_process

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
        else:
            arguments.append("-4")
        if count:
            arguments.append(f"-n {count}")
        if src_ip:
            arguments.append(f"-S {src_ip}")
        if timeout:
            arguments.append(f"-w {timeout}")
        if frag is False:
            if is_ipv6:
                logger.log(level=log_levels.MODULE_DEBUG, msg="Fragment flag is for IPv4 only.")
            else:
                arguments.append("-f")
        if mtu is not None:
            value = IPv6_ICMP_HEADER if is_ipv6 else IPv4_ICMP_HEADER
            arguments.append(f"-l {mtu-value}")
        if packet_size is not None:
            if not mtu:
                arguments.append(f"-l {packet_size}")
            else:
                logger.log(level=log_levels.MODULE_DEBUG, msg="Not using packet_size, because passed MTU.")
        if ttl:
            arguments.append(f"-i {ttl}")
        if broadcast:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Broadcast is not supported with Windows, skipping argument.")
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

        if "General failure" in result:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Ping output:\n{result}")
            raise PingException('Cannot ping host due to "General failure" error')

        # flow with summary in output
        if "Ping statistics" in result:
            count_regex = (
                r"^\s+Packets: Sent = (?P<transmitted_count>\d+), "
                r"Received = (?P<received_count>\d+), "
                r"Lost = \d+ \((?P<packet_loss>\d+\.?\d*)% loss\),"
                r"(?:(\r\n|\n).+(?:\r\n|\n)"
                r"^\s+Minimum = (?P<rtt_min>\d+\.?\d*)ms, "
                r"Maximum = (?P<rtt_max>\d+\.?\d*)ms, "
                r"Average = (?P<rtt_avg>\d+\.?\d*)ms)?"
            )
            count_match = re.search(count_regex, result, re.M)
            if count_match:
                transmitted = int(count_match.group("transmitted_count"))
                received = int(count_match.group("received_count"))
                received -= len(re.findall("Destination host unreachable.", result))
                packet_loss = 100 - (float(received) / transmitted * 100)
                rtt_min = float(count_match.group("rtt_min")) if count_match.group("rtt_min") else None
                rtt_avg = float(count_match.group("rtt_avg")) if count_match.group("rtt_avg") else None
                rtt_max = float(count_match.group("rtt_max")) if count_match.group("rtt_max") else None
                return PingResult(
                    pass_count=received,
                    fail_count=transmitted - received,
                    packets_transmitted=transmitted,
                    packets_received=received,
                    packet_loss=packet_loss,
                    rtt_min=rtt_min,
                    rtt_avg=rtt_avg,
                    rtt_max=rtt_max,
                )

        # flow with pings without summary
        elif ping_tries:
            # Reply from 127.0.0.1: bytes=32 time<1ms TTL=128 #ipv4
            # Reply from ::1: time<1ms # ipv6
            reply_regex = r"Reply from .*:.+time.[0-9ms]+"
            reply_matches = re.findall(reply_regex, result)
            pass_count = len(reply_matches)
            fail_count = ping_tries - pass_count
            return PingResult(pass_count, fail_count)
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Ping output:\n{result}")
        raise PingException("Cannot parse output from ping")

    def stop(self, process: "RemoteProcess") -> "PingResult":
        """
        Kill pinging process and report result.

        :param process: OS process with ping.
        :return: DataClass PingResult with pass_count and fail_count of ping requests.
        """
        if process.running:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Stopping ping process.")
            process.stop(1)

        if process.log_path:
            result = self._connection.path(process.log_path).read_text().strip()
        else:
            result = process.stdout_text
        return self._parse_output(result)

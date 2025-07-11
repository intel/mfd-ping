# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for linux ping."""

import logging
import re
from typing import TYPE_CHECKING

from mfd_common_libs import add_logging_level, log_levels, TimeoutCounter
from mfd_kernel_namespace import add_namespace_call_command

from mfd_ping import Ping, PingResult
from mfd_ping.base import IPv4_ICMP_HEADER, IPv6_ICMP_HEADER
from mfd_ping.exceptions import PingException

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address
    from netaddr import IPAddress

    from mfd_connect.process import RemoteProcess

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class LinuxPing(Ping):
    """Class responsible for handling ping method on Linux OS."""

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
        namespace: str | None = None,
        output_file: str | None = None,
    ) -> "RemoteProcess":
        """
        Start pinging destination machine.

        :param dst_ip: Destination IP address to perform ping
        :param mtu: Value of maximum transmission unit. Overriding usage of packet_size
        :param count: Number of echo requests to send
        :param packet_size: Size of ping packet in bytes
        :param src_ip: Source IP address to use ping
        :param timeout: Program execution timeout, in seconds
        :param frag: Enable fragmentation
        :param ttl: Time-To-Live value
        :param broadcast: Broadcast ping
        :param args: Additional arguments to ping method
        :param namespace: Namespace in which command should be executed
        :param output_file: path to file where log will be saved
        :return: OS process with ping.
        :raises PingException:  if addresses are incorrect.
                                if ping command fails on execution
                                if passed incorrect args
                                if passed incomplete args
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
            frag=frag,
            ttl=ttl,
            broadcast=broadcast,
            args=args,
        )
        command = f"ping {arguments}"
        try:
            ping_process = self._connection.start_process(
                add_namespace_call_command(command, namespace=namespace), output_file=output_file
            )
        except Exception as e:
            raise PingException("Problem with execution of ping command") from e
        # waiting for eventually bad arguments, output available after end of process

        timeout = TimeoutCounter(1)
        while not timeout:
            if not ping_process.running and "invalid" in ping_process.stderr_text:
                raise PingException("Passed unsupported option as args")
            elif not ping_process.running and "option requires an argument" in ping_process.stderr_text:
                raise PingException("Passed uncompleted option in args")
            elif not ping_process.running and ping_process.stderr_text:
                raise PingException(f"Process did not start due to error:\n{ping_process.stderr_text}")
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
        if count:
            arguments.append(f"-c {count}")
        if src_ip:
            arguments.append(f"-I {src_ip}")
        if timeout:
            arguments.append(f"-W {timeout}")
        if mtu:
            value = IPv6_ICMP_HEADER if is_ipv6 else IPv4_ICMP_HEADER
            arguments.append(f"-s {mtu-value}")
        if packet_size:
            if not mtu:
                arguments.append(f"-s {packet_size}")
            else:
                logger.log(level=log_levels.MODULE_DEBUG, msg="Not using packet_size, because passed MTU.")
        if frag is False:
            arguments.append("-M do")
        if ttl:
            arguments.append(f"-t {ttl}")
        if broadcast:
            arguments.append("-b")
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
            regex = (
                r"^(?P<packets_transmitted>\d+) packets transmitted, "
                r"(?P<packets_received>\d+) received, "
                r"(\+(?P<packets_duplicates>\d+) duplicates, )?"
                r"(\+(?P<errors>\d+) errors, )?"
                r"(?P<packet_loss>\d+\.?\d*)% packet loss, "
                r"time \d+ms"
                r"(\n^rtt min/avg/max/mdev = "
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
                    errors=int(match.group("errors")) if match.group("errors") else None,
                    packet_loss=float(match.group("packet_loss")),
                    rtt_min=float(match.group("rtt_min")) if match.group("rtt_min") else None,
                    rtt_avg=float(match.group("rtt_avg")) if match.group("rtt_avg") else None,
                    rtt_max=float(match.group("rtt_max")) if match.group("rtt_max") else None,
                )
        elif ping_tries > 0:
            # 64 bytes from 127.0.0.1: icmp_seq=3 ttl=64 time=0.035 ms
            # 64 bytes from ::1: icmp_seq=3 ttl=64 time=0.008 ms
            reply_regex = r"icmp_seq=(?P<icmp_seq_val>\d+) "
            reply_matches = re.findall(reply_regex, result)
            if reply_matches:
                pass_count = len(reply_matches)
                fail_count = int(reply_matches[-1]) - pass_count
                return PingResult(pass_count, fail_count)
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Ping output:\n{result}")
        raise PingException("Cannot parse output from ping")

    def _stop_ping(self, process: "RemoteProcess") -> None:
        process.stop(1)
        timeout = TimeoutCounter(5)
        while not timeout:
            if not process.running:
                return

    def _kill_ping(self, process: "RemoteProcess") -> None:
        process.kill(1)
        timeout = TimeoutCounter(5)
        while not timeout:
            if not process.running:
                return

    def stop(self, process: "RemoteProcess") -> "PingResult":
        """
        Stop pinging process and report result. Kill pinging process if after timeout is still running.

        :param process: OS process with ping.
        :return: DataClass PingResult with pass_count and fail_count of ping requests.
        :raises PingException: If process after stop and kill is still running.
        """
        if process.running:
            logger.log(level=log_levels.MODULE_DEBUG, msg="Stopping ping process.")
            self._stop_ping(process)
            # if process is still running, kill forcefully.
            if process.running:
                logger.log(level=log_levels.MODULE_DEBUG, msg="Killing ping process.")
                self._kill_ping(process)
                if process.running:
                    raise PingException("Problem with kill of ping process")

        if process.log_path:
            result = self._connection.path(process.log_path).read_text().strip()
        else:
            result = process.stdout_text
        return self._parse_output(result)

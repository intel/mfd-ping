# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for Mellanox Ping."""

import logging
from typing import TYPE_CHECKING

from mfd_common_libs import log_levels, TimeoutCounter

from mfd_ping import LinuxPing
from mfd_ping.exceptions import PingException

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address  # noqa
    from netaddr import IPAddress  # noqa
    from mfd_connect.process import RemoteProcess

logger = logging.getLogger(__name__)


class MellanoxPing(LinuxPing):
    """Class for ping Mellanox OS."""

    def start(
        self,
        *,
        dst_ip: "IPv4Address | IPv6Address | IPAddress | str",
        count: int | None = None,
        src_ip: "IPv4Address | IPv6Address | IPAddress | str | None" = None,
        timeout: int | None = None,
        args: str | None = None,
    ) -> "RemoteProcess":
        """
        Start pinging destination machine.

        :param dst_ip: Destination IP address to perform ping
        :param count: Number of echo requests to send
        :param src_ip: Source IP address to use ping
        :param timeout: Program execution timeout, in seconds
        :param args: Additional arguments to ping method
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
            count=count,
            timeout=timeout,
            args=args,
        )
        command = f"ping {arguments}"
        try:
            ping_process = self._connection.start_process(command)
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

    def _prepare_arguments(
        self,
        *,
        dst_ip: "IPv4Address | IPv6Address | IPAddress",
        count: int | None,
        timeout: int | None,
        args: str | None,
    ) -> str:
        """Get prepared arguments to ping, as string from passed parameters."""
        arguments = []
        if count:
            arguments.append(f"-c {count}")
        if args:
            arguments.append(args)
        arguments.append(str(dst_ip))
        return " ".join(arguments)

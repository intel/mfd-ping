# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Ping client traffic."""

import logging
from time import sleep
from typing import TYPE_CHECKING, Callable, Any

from mfd_common_libs import TimeoutCounter, log_levels, add_logging_level
from mfd_traffic_manager.base import Traffic

from mfd_ping.base import Ping
from mfd_ping.exceptions import PingException

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address
    from netaddr import IPAddress

    from mfd_connect.process import RemoteProcess
    from mfd_connect import Connection


logger = logging.getLogger(__name__)
add_logging_level("MODULE_DEBUG", log_levels.MODULE_DEBUG)


class PingClientTraffic(Traffic):
    """Class for Ping client traffic."""

    _process: "RemoteProcess"

    def __init__(
        self,
        connection: "Connection",
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
        namespace: str | None = None,
    ):
        """
        Initialize Ping traffic.

        :param connection: Connection object
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
        :param namespace: Namespace in which command should be executed
        """
        self._ping = Ping(connection=connection)
        self.dst_ip = dst_ip
        self.mtu = mtu
        self.count = count
        self.packet_size = packet_size
        self.src_ip = src_ip
        self.timeout = timeout
        self.frag = frag
        self.ttl = ttl
        self.broadcast = broadcast
        self.args = args
        self.output_file = output_file
        self.namespace = namespace

    def start(self) -> None:
        """Start ping traffic."""
        self._process = self._ping.start(
            dst_ip=self.dst_ip,
            mtu=self.mtu,
            count=self.count,
            packet_size=self.packet_size,
            src_ip=self.src_ip,
            timeout=self.timeout,
            args=self.args,
            output_file=self.output_file,
            frag=self.frag,
            ttl=self.ttl,
            broadcast=self.broadcast,
            namespace=self.namespace,
        )

    def stop(self) -> None:
        """Stop ping traffic."""
        if not self._process.running:
            return
        self._process.stop(1)
        timeout = TimeoutCounter(5)
        while not timeout:
            if not self._process.running:
                break
        else:
            self._process.kill(1)
            timeout = TimeoutCounter(5)
            while not timeout:
                if not self._process.running:
                    break
            else:
                raise PingException("Failed to stop ping process in 10 seconds")

    def run(self, duration: int) -> None:
        """
        Run ping traffic for specified duration.

        :param duration: duration of traffic in seconds
        """
        timeout = TimeoutCounter(duration)
        self.start()
        while not timeout:
            if not self._process.running:
                break
            sleep(1)
        else:
            self.stop()

    def validate(
        self,
        validation_criteria: dict[Callable, dict[str, Any]] | None = None,
    ) -> bool:
        """
        Validate ping traffic by specified criteria.

        :param validation_criteria: criteria by which traffic should be validated
        :return: True if traffic is correct according to criteria, otherwise False
        """
        if self._process.log_path:
            result = self._ping._connection.path(self._process.log_path).read_text().strip()
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Removing {self._process.log_path} log file")
            p = self._ping._connection.path(self._process.log_path)
            p.unlink()
        else:
            result = self._process.stdout_text
        interval_results = self._ping._parse_output(result)
        return self._validate(
            interval_results,
            validation_criteria,
        )

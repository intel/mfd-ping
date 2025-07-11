# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for MFD Ping implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from ipaddress import ip_address, AddressValueError, NetmaskValueError
from typing import TYPE_CHECKING

from mfd_typing.os_values import OSName

from .exceptions import PingConnectedOSNotSupported, PingException

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address
    from netaddr import IPAddress

    from mfd_connect import AsyncConnection
    from mfd_connect.process import RemoteProcess


@dataclass(frozen=True)
class PingResult:
    """Dataclass with ping results returned after ping_stop."""

    pass_count: int
    fail_count: int
    packets_transmitted: int = None
    packets_received: int = None
    packets_duplicates: int = None
    errors: int = None
    packet_loss: float = None
    rtt_min: float = None
    rtt_avg: float = None
    rtt_max: float = None


IPv4_ICMP_HEADER = 28
IPv6_ICMP_HEADER = 48


class Ping(ABC):
    """Class responsible for handling ping method."""

    def __new__(cls, connection: "AsyncConnection"):
        """
        Choose Ping subclass based on connected OS.

        :param connection: Connection object of host on which ping operations will be executed.
        :return: Instance of Ping subclass.
        :raises PingConnectedOSNotSupportedException: when connected OS is not supported by Ping.
        """
        if cls == Ping:
            from .linux import LinuxPing
            from .windows import WindowsPing
            from .esxi import EsxiPing
            from .freebsd import FreeBSDPing
            from .mellanox import MellanoxPing

            os_name = connection.get_os_name()
            os_name_to_class = {
                OSName.WINDOWS: WindowsPing,
                OSName.LINUX: LinuxPing,
                OSName.ESXI: EsxiPing,
                OSName.FREEBSD: FreeBSDPing,
                OSName.MELLANOX: MellanoxPing,
            }

            if os_name not in os_name_to_class.keys():
                raise PingConnectedOSNotSupported("OS of connected client not supported")

            ping_class = os_name_to_class.get(os_name)
            return super(Ping, cls).__new__(ping_class)
        else:
            return super(Ping, cls).__new__(cls)

    def __init__(self, connection: "AsyncConnection"):
        """
        Initialize Ping object.

        :param connection: Connection object of host on which ping operations will be executed.
        """
        self._connection = connection

    @abstractmethod
    def start(
        self,
        *,
        dst_ip: "IPv4Address | IPv6Address | IPAddress | str",
        mtu: int | None = None,
        count: int | None = None,
        packet_size: int | None = None,
        src_ip: "IPv4Address | IPv6Address | IPAddress | str | None" = None,
        timeout: int | None = None,
        args: str | None = None,
        output_file: str | None = None,
    ) -> "RemoteProcess":
        """
        Start pinging destination machine.

        :param dst_ip: Destination IP address to perform ping
        :param mtu: Value of maximum transmission unit
        :param count: Number of echo requests to send
        :param packet_size: Size of ping packet in bytes
        :param src_ip: Source IP address to use ping
        :param timeout: Program execution timeout, in seconds
        :param args: Additional arguments to ping method
        :param output_file: path to file where log will be saved
        :return: OS process with ping.
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self, process: "RemoteProcess") -> "PingResult":
        """
        Stop pinging process and report result.

        :param process: OS process with ping.
        :return: DataClass PingResult with pass_count and fail_count of ping requests.
        """
        raise NotImplementedError

    def _parse_ip_addresses(
        self,
        *,
        dst_ip: "IPv4Address | IPv6Address | IPAddress | str",
        src_ip: "IPv4Address | IPv6Address | IPAddress | str | None" = None,
    ) -> tuple["IPv4Address | IPv6Address", "IPv4Address | IPv6Address | None"]:
        """
        Parse IP to IPAddress type.

        :param dst_ip: Destination IP to perform ping
        :param src_ip: Source IP to use ping
        :return: Tuple with destination and source IP in proper IPAddress type
        :raises PingException: if IP address is in unexpected format
        """
        try:
            if isinstance(dst_ip, str):
                dst_ip = ip_address(dst_ip)
            if isinstance(src_ip, str):
                src_ip = ip_address(src_ip)
            return dst_ip, src_ip
        except (AddressValueError, NetmaskValueError, ValueError) as e:
            raise PingException(f"Address is in unexpected format.\n{e}")

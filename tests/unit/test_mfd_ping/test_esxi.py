# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Tests for `mfd_ping` package."""

import sys
from textwrap import dedent

import pytest
from mfd_common_libs import log_levels
from mfd_connect.process import RemoteProcess
from ipaddress import IPv4Address, IPv6Address

from mfd_ping import EsxiPing, PingResult
from mfd_connect import AsyncConnection

from mfd_ping.exceptions import PingException


class TestMfdEsxiPing:
    @pytest.fixture()
    def ping_tool(self, mocker):
        ping_tool = EsxiPing(connection=mocker.create_autospec(AsyncConnection))
        mocker.stopall()
        return ping_tool

    @pytest.fixture()
    def process_mock(self, mocker):
        return mocker.create_autospec(RemoteProcess)

    def test_ping(self, ping_tool, mocker):
        mocker.patch("mfd_ping.linux.TimeoutCounter")
        ping_tool.start(dst_ip="127.0.0.1", mtu=1234)
        ping_tool._connection.start_process.assert_called_once_with("ping -s 1206 127.0.0.1", output_file=None)

    def test__prepare_arguments(self, mocker, ping_tool):
        expected_output = "-c 10 -I eth1 -W 11 -s 1206 -t 12 -a -4 10.10.10.11"
        vmknic = mocker.MagicMock()
        vmknic.name = "eth1"
        host_mock = mocker.MagicMock()
        host_mock.ESXiHypervisor.return_value.find_vmknic.return_value = vmknic
        sys.modules["mfd_esxi.host"] = host_mock
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv4Address("10.10.10.11"),
                src_ip=IPv4Address("10.10.10.10"),
                count=10,
                packet_size=32,
                timeout=11,
                mtu=1234,
                args="-a -4",
                frag=None,
                ttl=12,
                broadcast=None,
            )
            == expected_output
        )

    def test__prepare_arguments_v6(self, mocker, ping_tool):
        expected_output = "-6 -c 10 -I eth1 -W 11 -d -s 1186 -a ::1"
        vmknic = mocker.MagicMock()
        vmknic.name = "eth1"
        host_mock = mocker.MagicMock()
        host_mock.ESXiHypervisor.return_value.find_vmknic.return_value = vmknic
        sys.modules["mfd_esxi.host"] = host_mock
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv6Address("::1"),
                src_ip=IPv6Address("::2"),
                count=10,
                packet_size=32,
                timeout=11,
                mtu=1234,
                args="-a",
                frag=False,
                ttl=None,
                broadcast=None,
            )
            == expected_output
        )

    def test__parse_output_with_summary(self, ping_tool):
        ping_output = dedent(
            """\
        PING ::1 (::1): 56 data bytes
        64 bytes from ::1: icmp_seq=0 time=0.190 ms
        64 bytes from ::1: icmp_seq=1 time=0.175 ms
        64 bytes from ::1: icmp_seq=2 time=0.122 ms
        64 bytes from ::1: icmp_seq=3 time=0.177 ms
        64 bytes from ::1: icmp_seq=4 time=0.184 ms
        64 bytes from ::1: icmp_seq=5 time=0.177 ms
        64 bytes from ::1: icmp_seq=6 time=0.176 ms
        64 bytes from ::1: icmp_seq=7 time=0.174 ms
        64 bytes from ::1: icmp_seq=8 time=0.165 ms
        --- ::1 ping statistics ---
        10 packets transmitted, 9 packets received, 10% packet loss
        round-trip min/avg/max = 0.122/0.171/0.190 ms"""
        )
        expected_output = PingResult(
            pass_count=9,
            fail_count=1,
            packets_transmitted=10,
            packets_received=9,
            packets_duplicates=None,
            errors=None,
            packet_loss=10,
            rtt_min=0.122,
            rtt_avg=0.171,
            rtt_max=0.19,
        )
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_with_summary_and_duplicates(self, ping_tool):
        ping_output = dedent(
            """\
        PING ff02::1 (ff02::1): 56 data bytes
        64 bytes from fe80::250:56ff:fe68:4a84: icmp_seq=0 time=0.384 ms
        64 bytes from fe80::250:56ff:fe99:2042: icmp_seq=0 time=0.860 ms (DUP!)
        64 bytes from fe80::250:56ff:fe99:2adb: icmp_seq=0 time=0.874 ms (DUP!)
        64 bytes from fe80::250:56ff:fe68:4a84: icmp_seq=1 time=0.428 ms
        64 bytes from fe80::250:56ff:fe99:2042: icmp_seq=1 time=0.843 ms (DUP!)
        64 bytes from fe80::250:56ff:fe99:2adb: icmp_seq=1 time=0.874 ms (DUP!)
        64 bytes from fe80::250:56ff:fe68:4a84: icmp_seq=2 time=0.436 ms
        64 bytes from fe80::250:56ff:fe99:2adb: icmp_seq=2 time=0.798 ms (DUP!)
        64 bytes from fe80::250:56ff:fe99:2042: icmp_seq=2 time=0.829 ms (DUP!)
        64 bytes from fe80::250:56ff:fe68:4a84: icmp_seq=3 time=0.521 ms
        — ff02::1 ping statistics —
        4 packets transmitted, 4 packets received, +6 duplicates, 0% packet loss
        round-trip min/avg/max = 0.384/1.712/0.874 ms"""
        )
        expected_output = PingResult(
            pass_count=4,
            fail_count=0,
            packets_transmitted=4,
            packets_received=4,
            packets_duplicates=6,
            errors=None,
            packet_loss=0,
            rtt_min=0.384,
            rtt_avg=1.712,
            rtt_max=0.874,
        )
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary(self, ping_tool):
        ping_output = dedent(
            """\
        PING ::1 (::1): 56 data bytes
        64 bytes from ::1: icmp_seq=0 time=0.156 ms
        64 bytes from ::1: icmp_seq=1 time=0.184 ms"""
        )
        expected_output = PingResult(pass_count=2, fail_count=0)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary_with_fails(self, ping_tool):
        ping_output = dedent(
            """\
        PING ::1 (::1): 56 data bytes
        64 bytes from ::1: icmp_seq=0 time=0.156 ms
        64 bytes from ::1: icmp_seq=1 time=0.156 ms
        64 bytes from ::1: icmp_seq=2 time=0.156 ms
        64 bytes from ::1: icmp_seq=9 time=0.156 ms"""
        )
        expected_output = PingResult(pass_count=4, fail_count=6)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_broken_output(self, ping_tool, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        ping_output = dedent(
            """\
        Pinging 127.0.0.1 with 32 bytes of data:"""
        )
        with pytest.raises(PingException, match="Cannot parse output from ping"):
            ping_tool._parse_output(ping_output)
        assert ping_output in caplog.text

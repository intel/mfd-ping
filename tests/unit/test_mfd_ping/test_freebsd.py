# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Tests for `mfd_ping` package."""

from textwrap import dedent

import pytest
from mfd_common_libs import log_levels
from mfd_connect import AsyncConnection
from mfd_connect.process import RemoteProcess
from ipaddress import IPv4Address, IPv6Address

from mfd_ping import FreeBSDPing, PingResult
from mfd_ping.exceptions import PingException


class TestFreeBSDPing:
    @pytest.fixture()
    def ping_tool(self, mocker):
        ping_tool = FreeBSDPing(connection=mocker.create_autospec(AsyncConnection))
        mocker.stopall()
        return ping_tool

    @pytest.fixture()
    def process_mock(self, mocker):
        return mocker.create_autospec(RemoteProcess)

    def test_ping(self, ping_tool, mocker):
        mocker.patch("mfd_ping.linux.TimeoutCounter")
        ping_tool.start(dst_ip="127.0.0.1", mtu=1234)
        ping_tool._connection.start_process.assert_called_once_with("ping -s 1206 127.0.0.1", output_file=None)

    def test__prepare_arguments(self, ping_tool):
        expected_output = "-s 1206 -c 10 -S 10.10.10.10 -t 11 -T 12 -a -4 10.10.10.11"
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

    def test__prepare_arguments_v6(self, ping_tool):
        expected_output = "-6 -s 1186 -c 10 -S ::2 -t 11 -D -a ::1"
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
        PING localhost (127.0.0.1): 56 data bytes
        64 bytes from 127.0.0.1: icmp_seq=0 ttl=64 time=0.049 ms
        64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.038 ms
        64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.037 ms
        64 bytes from 127.0.0.1: icmp_seq=3 ttl=64 time=0.038 ms
        64 bytes from 127.0.0.1: icmp_seq=4 ttl=64 time=0.035 ms
        64 bytes from 127.0.0.1: icmp_seq=5 ttl=64 time=0.036 ms
        64 bytes from 127.0.0.1: icmp_seq=6 ttl=64 time=0.035 ms
        64 bytes from 127.0.0.1: icmp_seq=7 ttl=64 time=0.038 ms
        64 bytes from 127.0.0.1: icmp_seq=8 ttl=64 time=0.040 ms

        --- localhost ping statistics ---
        10 packets transmitted, 9 packets received, 10.0% packet loss
        round-trip min/avg/max/stddev = 0.035/0.039/0.049/0.004 ms"""
        )
        expected_output = PingResult(
            pass_count=9,
            fail_count=1,
            packets_transmitted=10,
            packets_received=9,
            packets_duplicates=None,
            errors=None,
            packet_loss=10,
            rtt_min=0.035,
            rtt_avg=0.039,
            rtt_max=0.049,
        )
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_with_summary_ipv6(self, ping_tool):
        ping_output = dedent(
            """\
        PING6(56=40+8+8 bytes) fe80::b696:91ff:feaa:d790%ice0 --> fe80::b696:91ff:feaa:d790%ice0
        16 bytes from fe80::b696:91ff:feaa:d790%ice0, icmp_seq=0 hlim=64 time=0.093 ms
        16 bytes from fe80::b696:91ff:feaa:d790%ice0, icmp_seq=1 hlim=64 time=0.062 ms
        16 bytes from fe80::b696:91ff:feaa:d790%ice0, icmp_seq=2 hlim=64 time=0.043 ms
        16 bytes from fe80::b696:91ff:feaa:d790%ice0, icmp_seq=3 hlim=64 time=0.050 ms

        --- fe80::b696:91ff:feaa:d790%ice0 ping6 statistics ---
        5 packets transmitted, 4 packets received, 2.0% packet loss
        round-trip min/avg/max/std-dev = 0.042/0.058/0.093/0.019 ms"""
        )
        expected_output = PingResult(
            pass_count=4,
            fail_count=1,
            packets_transmitted=5,
            packets_received=4,
            packets_duplicates=None,
            errors=None,
            packet_loss=2,
            rtt_min=0.042,
            rtt_avg=0.058,
            rtt_max=0.093,
        )
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary(self, ping_tool):
        ping_output = dedent(
            """\
        PING 127.0.0.1 (127.0.0.1): 56 data bytes
        64 bytes from 127.0.0.1: icmp_seq=0 ttl=64 time=0.043 ms
        64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.041 ms"""
        )
        expected_output = PingResult(pass_count=2, fail_count=0)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary_with_fails(self, ping_tool):
        ping_output = dedent(
            """\
        PING 127.0.0.1 (127.0.0.1): 56 data bytes
        64 bytes from 127.0.0.1: icmp_seq=0 ttl=64 time=0.043 ms
        64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.041 ms
        64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.040 ms
        64 bytes from 127.0.0.1: icmp_seq=10 ttl=64 time=0.037 ms"""
        )
        expected_output = PingResult(pass_count=4, fail_count=7)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_broken_output(self, ping_tool, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        ping_output = dedent(
            """\
        PING 127.0.0.1 (127.0.0.1): 56 data bytes"""
        )
        with pytest.raises(PingException, match="Cannot parse output from ping"):
            ping_tool._parse_output(ping_output)
        assert ping_output in caplog.text

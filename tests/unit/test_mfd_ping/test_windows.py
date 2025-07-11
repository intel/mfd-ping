# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Tests for `mfd_ping` package."""

from textwrap import dedent

import pytest
from mfd_common_libs import log_levels
from mfd_connect.process import RemoteProcess
from ipaddress import IPv4Address, IPv6Address

from mfd_ping import WindowsPing, PingResult
from mfd_connect import AsyncConnection

from mfd_ping.exceptions import PingException


class TestMfdWindowsPing:
    @pytest.fixture()
    def ping_tool(self, mocker):
        ping_tool = WindowsPing(connection=mocker.create_autospec(AsyncConnection))
        mocker.stopall()
        return ping_tool

    @pytest.mark.parametrize("dst_ip,src_ip", [("256.0.0.1", "10.10.10.10"), ("10.10.10.10", "256.0.0.1")])
    def test_ping_incorrect_ip(self, ping_tool, dst_ip, src_ip):
        with pytest.raises(PingException, match="Address is in unexpected format."):
            ping_tool.start(dst_ip=dst_ip, src_ip=src_ip)

    def test_ping_no_same_version(self, ping_tool):
        with pytest.raises(PingException, match="Source IP address is not in the same version as destination IP"):
            ping_tool.start(dst_ip="10.10.10.10", src_ip="2001:db8::")

    def test_ping(self, ping_tool, mocker):
        mocker.patch("mfd_ping.windows.TimeoutCounter")
        ping_tool.start(dst_ip="127.0.0.1", mtu=1234)
        ping_tool._connection.start_process.assert_called_once_with("ping -4 -l 1206 127.0.0.1", output_file=None)

    def test_ping_ipv6(self, ping_tool, mocker):
        mocker.patch("mfd_ping.windows.TimeoutCounter")
        ping_tool.start(dst_ip="::1", count=12)
        ping_tool._connection.start_process.assert_called_once_with("ping -6 -n 12 ::1", output_file=None)

    def test_ping_invalid_args(self, mocker, ping_tool):
        timeout_mocker = mocker.patch("mfd_ping.windows.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        process_mock = mocker.create_autospec(RemoteProcess)
        process_mock.running = False
        process_mock.stdout_text = "Bad option -qw."
        ping_tool._connection.start_process.return_value = process_mock
        with pytest.raises(PingException, match="Passed unsupported option as args"):
            ping_tool.start(dst_ip="127.0.0.1", args="-qw")
        ping_tool._connection.start_process.assert_called_once_with("ping -4 -qw 127.0.0.1", output_file=None)

    def test__prepare_arguments(self, ping_tool):
        expected_output = "-4 -n 10 -S 10.10.10.10 -w 11 -l 32 -a 10.10.10.11"
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv4Address("10.10.10.11"),
                src_ip=IPv4Address("10.10.10.10"),
                count=10,
                packet_size=32,
                timeout=11,
                mtu=None,
                args="-a",
                frag=None,
                broadcast=None,
                ttl=None,
            )
            == expected_output
        )

    def test__prepare_arguments_ipv6(self, ping_tool):
        expected_output = "-6 -n 10 -S ::1 -w 11 -l 32 -a ::2"
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv6Address("::2"),
                src_ip=IPv6Address("::1"),
                count=10,
                packet_size=32,
                timeout=11,
                mtu=None,
                args="-a",
                frag=None,
                broadcast=None,
                ttl=None,
            )
            == expected_output
        )

    def test__prepare_arguments_mtu_override_packet_size(self, ping_tool, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        expected_output = "-4 -n 10 -S 10.10.10.10 -w 11 -l 4 -a 10.10.10.11"
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv4Address("10.10.10.11"),
                src_ip=IPv4Address("10.10.10.10"),
                count=10,
                packet_size=60,
                timeout=11,
                mtu=32,
                args="-a",
                frag=None,
                broadcast=None,
                ttl=None,
            )
            == expected_output
        )
        assert "Not using packet_size, because passed MTU." in caplog.text

    def test__prepare_arguments_mtu_and_frag(self, ping_tool, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        expected_output = "-4 -n 10 -S 10.10.10.10 -w 11 -f -l 4 -a 10.10.10.11"
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv4Address("10.10.10.11"),
                src_ip=IPv4Address("10.10.10.10"),
                count=10,
                packet_size=None,
                timeout=11,
                mtu=32,
                args="-a",
                frag=False,
                broadcast=None,
                ttl=None,
            )
            == expected_output
        )

    def test__prepare_arguments_packet_size_zero(self, ping_tool):
        expected_output = "-4 -n 10 -S 10.10.10.10 -w 11 -l 0 -a 10.10.10.11"
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv4Address("10.10.10.11"),
                src_ip=IPv4Address("10.10.10.10"),
                count=10,
                packet_size=0,
                timeout=11,
                mtu=None,
                args="-a",
                frag=None,
                broadcast=None,
                ttl=None,
            )
            == expected_output
        )

    def test__prepare_arguments_packet_broadcast(self, ping_tool, mocker):
        logger_mock = mocker.patch("mfd_ping.windows.logger")
        ping_tool._prepare_arguments(
            dst_ip=IPv4Address("10.10.10.11"),
            src_ip=IPv4Address("10.10.10.10"),
            count=10,
            packet_size=0,
            timeout=11,
            mtu=None,
            args="-a",
            frag=None,
            broadcast=True,
            ttl=None,
        )
        logger_mock.log.assert_called_once_with(
            level=log_levels.MODULE_DEBUG, msg="Broadcast is not supported with Windows, skipping argument."
        )

    def test_stop_stopped(self, ping_tool, mocker):
        process_mock = mocker.create_autospec(RemoteProcess)
        process_mock.running = False
        process_mock.stdout_text = ""
        process_mock.log_path = None
        ping_tool._parse_output = mocker.create_autospec(ping_tool._parse_output, return_value=PingResult(0, 0))
        assert ping_tool.stop(process_mock) == PingResult(pass_count=0, fail_count=0)

    def test_stop(self, ping_tool, mocker, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        process_mock = mocker.create_autospec(RemoteProcess)
        process_mock.running = True
        process_mock.stdout_text = ""
        process_mock.log_path = None
        ping_tool._parse_output = mocker.create_autospec(ping_tool._parse_output, return_value=PingResult(0, 0))
        assert ping_tool.stop(process_mock) == PingResult(pass_count=0, fail_count=0)
        process_mock.stop.assert_called_once_with(1)
        assert "Stopping ping process." in caplog.text

    def test__parse_output_with_summary(self, ping_tool):
        ping_output = dedent(
            """\
        Pinging 127.0.0.1 with 32 bytes of data:
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Request timed out.

        Ping statistics for 127.0.0.1:
            Packets: Sent = 10, Received = 9, Lost = 1 (10% loss),
        Approximate round trip times in milli-seconds:
            Minimum = 0ms, Maximum = 0ms, Average = 0ms"""
        )
        expected_output = PingResult(
            pass_count=9,
            fail_count=1,
            packets_transmitted=10,
            packets_received=9,
            packet_loss=10.0,
            rtt_min=0.0,
            rtt_avg=0.0,
            rtt_max=0.0,
        )
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary(self, ping_tool):
        ping_output = dedent(
            """\
        Pinging 127.0.0.1 with 32 bytes of data:
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128"""
        )
        expected_output = PingResult(pass_count=9, fail_count=0)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary_ipv6(self, ping_tool):
        ping_output = dedent(
            """\
        Pinging ::1 with 32 bytes of data:
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms"""
        )
        expected_output = PingResult(pass_count=9, fail_count=0)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary_with_fails(self, ping_tool):
        ping_output = dedent(
            """\
        Pinging 127.0.0.1 with 32 bytes of data:
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Request timed out.
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
        Request timed out.
        Reply from 127.0.0.1: bytes=32 time<1ms TTL=128"""
        )
        expected_output = PingResult(pass_count=4, fail_count=2)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary_with_fails_ipv6(self, ping_tool):
        ping_output = dedent(
            """\
        Pinging ::1 with 32 bytes of data:
        Reply from ::1: time<1ms
        Reply from ::1: time<1ms
        Request timed out.
        Reply from ::1: time<1ms
        Request timed out.
        Reply from ::1: time<1ms"""
        )
        expected_output = PingResult(pass_count=4, fail_count=2)
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

    def test__parse_output_with_summary_with_general_failure(self, ping_tool, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        ping_output = dedent(
            """\
        Pinging 127.0.0.0 with 32 bytes of data:
        General failure.
        General failure.
        General failure.
        General failure.
        Ping statistics for 127.0.0.0:
            Packets: Sent = 4, Received = 0, Lost = 4 (100% loss),"""
        )
        with pytest.raises(PingException, match='Cannot ping host due to "General failure" error'):
            ping_tool._parse_output(ping_output)
        assert ping_output in caplog.text

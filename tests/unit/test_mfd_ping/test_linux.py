# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Tests for `mfd_ping` package."""

from textwrap import dedent

import pytest
from mfd_common_libs import log_levels
from mfd_connect.process import RemoteProcess
from ipaddress import IPv4Address, IPv6Address

from mfd_ping import LinuxPing, PingResult
from mfd_connect import AsyncConnection

from mfd_ping.exceptions import PingException


class TestMfdLinuxPing:
    @pytest.fixture()
    def ping_tool(self, mocker):
        ping_tool = LinuxPing(connection=mocker.create_autospec(AsyncConnection))
        mocker.stopall()
        return ping_tool

    @pytest.fixture()
    def process_mock(self, mocker):
        return mocker.create_autospec(RemoteProcess)

    @pytest.mark.parametrize("dst_ip,src_ip", [("256.0.0.1", "10.10.10.10"), ("10.10.10.10", "256.0.0.1")])
    def test_ping_incorrect_ip(self, ping_tool, dst_ip, src_ip):
        with pytest.raises(PingException, match="Address is in unexpected format."):
            ping_tool.start(dst_ip=dst_ip, src_ip=src_ip)

    def test_ping_no_same_version(self, ping_tool):
        with pytest.raises(PingException, match="Source IP address is not in the same version as destination IP"):
            ping_tool.start(dst_ip="10.10.10.10", src_ip="2001:db8::")

    def test_ping(self, ping_tool, mocker):
        mocker.patch("mfd_ping.linux.TimeoutCounter")
        ping_tool.start(dst_ip="127.0.0.1", mtu=1234)
        ping_tool._connection.start_process.assert_called_once_with("ping -s 1206 127.0.0.1", output_file=None)

    def test_ping_invalid_args(self, mocker, process_mock, ping_tool):
        timeout_mocker = mocker.patch("mfd_ping.linux.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        process_mock.running = False
        process_mock.stderr_text = "ping: invalid option"
        ping_tool._connection.start_process.return_value = process_mock
        with pytest.raises(PingException, match="Passed unsupported option as args"):
            ping_tool.start(dst_ip="127.0.0.1", args="-0")
        ping_tool._connection.start_process.assert_called_once_with("ping -0 127.0.0.1", output_file=None)

    def test_ping_uncompleted_args(self, mocker, process_mock, ping_tool):
        timeout_mocker = mocker.patch("mfd_ping.linux.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        process_mock.running = False
        process_mock.stderr_text = "ping: option requires an argument -- 'w'"
        ping_tool._connection.start_process.return_value = process_mock
        with pytest.raises(PingException, match="Passed uncompleted option in args"):
            ping_tool.start(dst_ip="127.0.0.1", args="-qw")
        ping_tool._connection.start_process.assert_called_once_with("ping -qw 127.0.0.1", output_file=None)

    def test_ping_cannot_assign_requested_address(self, mocker, process_mock, ping_tool):
        timeout_mocker = mocker.patch("mfd_ping.linux.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        process_mock.running = False
        process_mock.stderr_text = "ping: bind: Cannot assign requested address"
        ping_tool._connection.start_process.return_value = process_mock
        with pytest.raises(PingException, match=f"Process did not start due to error:\n{process_mock.stderr_text}"):
            ping_tool.start(dst_ip="1.2.1.1", count=4, timeout=2, src_ip="1.1.1.1")
        ping_tool._connection.start_process.assert_called_once_with(
            "ping -c 4 -I 1.1.1.1 -W 2 1.2.1.1", output_file=None
        )

    def test_ping_with_namespace(self, ping_tool, mocker):
        mocker.patch("mfd_ping.linux.TimeoutCounter")
        ping_tool.start(dst_ip="127.0.0.1", mtu=1234, namespace="net1")
        ping_tool._connection.start_process.assert_called_once_with(
            "ip netns exec net1 ping -s 1206 127.0.0.1", output_file=None
        )

    def test__prepare_arguments(self, ping_tool):
        expected_output = "-c 10 -I 10.10.10.10 -W 11 -s 1206 -a -4 10.10.10.11"
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
                ttl=None,
                broadcast=None,
            )
            == expected_output
        )

    def test__prepare_arguments_v6(self, ping_tool):
        expected_output = "-6 -c 10 -I ::2 -W 11 -s 1186 -a ::1"
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv6Address("::1"),
                src_ip=IPv6Address("::2"),
                count=10,
                packet_size=32,
                timeout=11,
                mtu=1234,
                args="-a",
                frag=None,
                ttl=None,
                broadcast=None,
            )
            == expected_output
        )

    def test__prepare_arguments_v6_multicast(self, ping_tool):
        expected_output = "-6 -c 10 -I 3001:1::1:a:2 ff02::1%eth1"
        assert (
            ping_tool._prepare_arguments(
                dst_ip=IPv6Address("ff02::1%eth1"),
                src_ip=IPv6Address("3001:1::1:a:2"),
                count=10,
                packet_size=None,
                timeout=None,
                mtu=None,
                args=None,
                frag=None,
                ttl=None,
                broadcast=None,
            )
            == expected_output
        )

    def test_stop_stopped(self, ping_tool, process_mock, mocker):
        process_mock.running = False
        process_mock.stdout_text = ""
        process_mock.log_path = None
        ping_tool._parse_output = mocker.create_autospec(ping_tool._parse_output, return_value=PingResult(0, 0))
        assert ping_tool.stop(process_mock) == PingResult(pass_count=0, fail_count=0)

    def test_stop(self, ping_tool, mocker, process_mock, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        process_mock.stdout_text = ""
        process_mock.log_path = None
        type(process_mock).running = mocker.PropertyMock(side_effect=[True, False])
        ping_tool._stop_ping = mocker.create_autospec(ping_tool._stop_ping, return_value=None)
        ping_tool._parse_output = mocker.create_autospec(ping_tool._parse_output, return_value=PingResult(0, 0))
        assert ping_tool.stop(process_mock) == PingResult(pass_count=0, fail_count=0)
        assert "Stopping ping process." in caplog.text

    def test_kill(self, ping_tool, mocker, process_mock, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        type(process_mock).running = mocker.PropertyMock(side_effect=[True, True, False])
        process_mock.stdout_text = ""
        process_mock.log_path = None
        ping_tool._stop_ping = mocker.create_autospec(ping_tool._stop_ping, return_value=None)
        ping_tool._kill_ping = mocker.create_autospec(ping_tool._kill_ping, return_value=None)
        ping_tool._parse_output = mocker.create_autospec(ping_tool._parse_output, return_value=PingResult(0, 0))
        assert ping_tool.stop(process_mock) == PingResult(pass_count=0, fail_count=0)
        assert "Killing ping process." in caplog.text

    def test__parse_output_with_summary(self, ping_tool):
        ping_output = dedent(
            """\
        PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
        64 bytes from 127.0.0.1: icmp_seq=1 ttl=128 time=0.599 ms
        64 bytes from 127.0.0.1: icmp_seq=2 ttl=128 time=0.754 ms
        64 bytes from 127.0.0.1: icmp_seq=3 ttl=128 time=0.682 ms
        64 bytes from 127.0.0.1: icmp_seq=4 ttl=128 time=0.633 ms
        64 bytes from 127.0.0.1: icmp_seq=5 ttl=128 time=1.36 ms
        64 bytes from 127.0.0.1: icmp_seq=6 ttl=128 time=1.33 ms
        64 bytes from 127.0.0.1: icmp_seq=7 ttl=128 time=0.490 ms
        64 bytes from 127.0.0.1: icmp_seq=8 ttl=128 time=1.21 ms
        64 bytes from 127.0.0.1: icmp_seq=9 ttl=128 time=0.572 ms

        --- 127.0.0.1 ping statistics ---
        10 packets transmitted, 9 received, 10% packet loss, time 9012ms
        rtt min/avg/max/mdev = 0.490/0.855/1.355/0.312 ms"""
        )
        expected_output = PingResult(
            pass_count=9,
            fail_count=1,
            packets_transmitted=10,
            packets_received=9,
            packets_duplicates=None,
            errors=None,
            packet_loss=10.0,
            rtt_min=0.490,
            rtt_avg=0.855,
            rtt_max=1.355,
        )
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary(self, ping_tool):
        ping_output = dedent(
            """\
        PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
        64 bytes from 127.0.0.1: icmp_seq=1 ttl=128 time=0.599 ms
        64 bytes from 127.0.0.1: icmp_seq=2 ttl=128 time=0.754 ms
        64 bytes from 127.0.0.1: icmp_seq=3 ttl=128 time=0.682 ms
        64 bytes from 127.0.0.1: icmp_seq=4 ttl=128 time=0.572 ms"""
        )
        expected_output = PingResult(pass_count=4, fail_count=0)
        assert ping_tool._parse_output(ping_output) == expected_output

    def test__parse_output_without_summary_with_fails(self, ping_tool):
        ping_output = dedent(
            """\
        PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
        64 bytes from 127.0.0.1: icmp_seq=1 ttl=128 time=0.599 ms
        64 bytes from 127.0.0.1: icmp_seq=2 ttl=128 time=0.754 ms
        64 bytes from 127.0.0.1: icmp_seq=3 ttl=128 time=0.682 ms
        64 bytes from 127.0.0.1: icmp_seq=10 ttl=128 time=0.572 ms"""
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

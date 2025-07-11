# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import logging

import pytest
from mfd_connect import RPyCConnection
from mfd_connect.process import RemoteProcess
from mfd_typing import OSName, OSType

from mfd_ping import LinuxPing, WindowsPing, FreeBSDPing, EsxiPing, PingResult
from mfd_ping.exceptions import PingException
from mfd_ping.traffics.client_traffic import PingClientTraffic


def validate_packet_loss(results: PingResult, *, packet_loss_threshold: float) -> bool:
    """
    Validate packets loss occurred.

    :param results: PingResult
    :param packet_loss_threshold: packet loss threshold allowed for validation. eg - 0.0
    :return: status of validation
    """
    actual_pkt_loss = results.packet_loss
    if actual_pkt_loss > packet_loss_threshold:
        logging.debug(f"Packet loss greater than: {packet_loss_threshold}")
        return False
    return True


class TestPingTraffic:
    def stop_already_stopped(self, client, mocker):
        client._process = mocker.MagicMock()
        mock_running = mocker.PropertyMock(return_value=False)
        type(client._process).running = mock_running
        client.stop()
        client._process.stop.assert_not_called()
        client._process.kill.assert_not_called()

    def stop(self, client, mocker):
        client._process = mocker.MagicMock()
        mock_running = mocker.PropertyMock(side_effect=[True, False])
        type(client._process).running = mock_running
        timeout_mocker = mocker.patch("mfd_ping.traffics.client_traffic.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        client.stop()
        client._process.stop.assert_called_once()
        client._process.kill.assert_not_called()

    def stop_failure(self, client, mocker):
        client._process = mocker.MagicMock()
        mock_running = mocker.PropertyMock(side_effect=[True, True])
        type(client._process).running = mock_running
        timeout_mocker = mocker.patch("mfd_ping.traffics.client_traffic.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = True
        with pytest.raises(PingException):
            client.stop()
        client._process.stop.assert_called_once()
        client._process.kill.assert_called_once()

    def stop_with_kill(self, client, mocker):
        client._process = mocker.MagicMock()
        mock_running = mocker.PropertyMock(side_effect=[True, False])
        type(client._process).running = mock_running
        timeout_mocker = mocker.patch("mfd_ping.traffics.client_traffic.TimeoutCounter")
        timeout_mocker.return_value.__bool__.side_effect = [True, False]
        client.stop()
        client._process.stop.assert_called_once()
        client._process.kill.assert_called_once()

    def run(self, client, mocker):
        client.start = mocker.create_autospec(client.start)
        mock_running = mocker.PropertyMock(return_value=False)
        type(client._process).running = mock_running
        timeout_mocker = mocker.patch("mfd_ping.traffics.client_traffic.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = False
        client.run(duration=1)
        client.start.assert_called_once()

    def run_with_stop(self, client, mocker):
        client.start = mocker.create_autospec(client.start)
        client.stop = mocker.create_autospec(client.stop)
        mock_running = mocker.PropertyMock(return_value=True)
        type(client._process).running = mock_running
        timeout_mocker = mocker.patch("mfd_ping.traffics.client_traffic.TimeoutCounter")
        timeout_mocker.return_value.__bool__.return_value = True
        client.run(duration=1)
        client.start.assert_called_once()
        client.stop.assert_called_once()

    def validate(self, client, mocker):
        client._ping._parse_output = mocker.create_autospec(client._ping._parse_output)
        client._ping._parse_output.return_value = PingResult(
            pass_count=0,
            fail_count=3,
            packets_transmitted=3,
            packets_received=0,
            packets_duplicates=None,
            errors=None,
            packet_loss=100.0,
            rtt_min=None,
            rtt_avg=None,
            rtt_max=None,
        )
        assert client.validate() is True
        validation_criteria = {validate_packet_loss: {"packet_loss_threshold": 0.0}}
        assert client.validate(validation_criteria) is False
        validation_criteria = {validate_packet_loss: {"packet_loss_threshold": 100.0}}
        assert client.validate(validation_criteria) is True


class TestLinuxPingClient(TestPingTraffic):
    @pytest.fixture()
    def linux_connection(self, mocker):
        linux_conn = mocker.create_autospec(RPyCConnection)
        linux_conn.get_os_name.return_value = OSName.LINUX
        yield linux_conn

    @pytest.fixture()
    def linux_client(self, mocker, linux_connection):
        traffic = PingClientTraffic(connection=linux_connection, dst_ip="10.10.10.1", packet_size=2000, mtu=1500)
        traffic._process = mocker.create_autospec(RemoteProcess)
        traffic._process.log_path = None
        yield traffic

    def test_init_linux(self, linux_client):
        assert isinstance(linux_client._ping, LinuxPing)
        assert linux_client.dst_ip == "10.10.10.1"
        assert linux_client.packet_size == 2000
        assert linux_client.mtu == 1500

    def test_start_linux(self, linux_client, mocker):
        process = mocker.create_autospec(RemoteProcess)
        linux_client._ping.start = mocker.create_autospec(linux_client._ping.start)
        linux_client._ping.start.return_value = process
        linux_client.start()
        linux_client._ping.start.assert_called_once_with(
            dst_ip="10.10.10.1",
            mtu=1500,
            count=None,
            packet_size=2000,
            src_ip=None,
            timeout=None,
            args=None,
            output_file=None,
            frag=None,
            ttl=None,
            broadcast=None,
            namespace=None,
        )

    def test_stop_already_stopped_linux(self, linux_client, mocker):
        return super().stop_already_stopped(linux_client, mocker)

    def test_stop_linux(self, linux_client, mocker):
        return super().stop(linux_client, mocker)

    def test_stop_failure(self, linux_client, mocker):
        return super().stop_failure(linux_client, mocker)

    def test_stop_with_kill(self, linux_client, mocker):
        return super().stop_with_kill(linux_client, mocker)

    def test_run(self, linux_client, mocker):
        return super().run(linux_client, mocker)

    def test_run_with_stop(self, linux_client, mocker):
        return super().run_with_stop(linux_client, mocker)

    def test_validate(self, linux_client, mocker):
        return super().validate(linux_client, mocker)


class TestWindowsPingClient(TestPingTraffic):
    @pytest.fixture()
    def windows_connection(self, mocker):
        windows_conn = mocker.create_autospec(RPyCConnection)
        windows_conn.get_os_name.return_value = OSName.WINDOWS
        yield windows_conn

    @pytest.fixture()
    def windows_client(self, mocker, windows_connection):
        traffic = PingClientTraffic(connection=windows_connection, dst_ip="10.10.10.1", packet_size=2000, mtu=1500)
        traffic._process = mocker.create_autospec(RemoteProcess)
        traffic._process.log_path = None
        yield traffic

    def test_init_windows(self, windows_client):
        assert isinstance(windows_client._ping, WindowsPing)
        assert windows_client.dst_ip == "10.10.10.1"
        assert windows_client.packet_size == 2000
        assert windows_client.mtu == 1500

    def test_start_windows(self, windows_client, mocker):
        process = mocker.create_autospec(RemoteProcess)
        windows_client._ping.start = mocker.create_autospec(windows_client._ping.start)
        windows_client._ping.start.return_value = process
        windows_client.start()
        windows_client._ping.start.assert_called_once_with(
            dst_ip="10.10.10.1",
            mtu=1500,
            count=None,
            packet_size=2000,
            src_ip=None,
            timeout=None,
            args=None,
            output_file=None,
            frag=None,
            ttl=None,
            broadcast=None,
            namespace=None,
        )

    def test_stop_already_stopped_windows(self, windows_client, mocker):
        return super().stop_already_stopped(windows_client, mocker)

    def test_stop_windows(self, windows_client, mocker):
        return super().stop(windows_client, mocker)

    def test_stop_failure_windows(self, windows_client, mocker):
        return super().stop_failure(windows_client, mocker)

    def test_stop_with_kill_windows(self, windows_client, mocker):
        return super().stop_with_kill(windows_client, mocker)

    def test_run_windows(self, windows_client, mocker):
        return super().run(windows_client, mocker)

    def test_run_with_stop_windows(self, windows_client, mocker):
        return super().run_with_stop(windows_client, mocker)

    def test_validate_windows(self, windows_client, mocker):
        return super().validate(windows_client, mocker)


class TestFreeBSDPingClient(TestPingTraffic):
    @pytest.fixture()
    def freebsd_connection(self, mocker):
        freebsd_connection = mocker.create_autospec(RPyCConnection)
        freebsd_connection.get_os_name.return_value = OSName.FREEBSD
        freebsd_connection.get_os_type.return_value = OSType.POSIX
        yield freebsd_connection

    @pytest.fixture()
    def freebsd_client(self, mocker, freebsd_connection):
        traffic = PingClientTraffic(connection=freebsd_connection, dst_ip="10.10.10.1", packet_size=2000, mtu=1500)
        traffic._process = mocker.create_autospec(RemoteProcess)
        traffic._process.log_path = None
        yield traffic

    def test_init_freebsd(self, freebsd_client):
        assert isinstance(freebsd_client._ping, FreeBSDPing)
        assert freebsd_client.dst_ip == "10.10.10.1"
        assert freebsd_client.packet_size == 2000
        assert freebsd_client.mtu == 1500

    def test_start_freebsd(self, freebsd_client, mocker):
        process = mocker.create_autospec(RemoteProcess)
        freebsd_client._ping.start = mocker.create_autospec(freebsd_client._ping.start)
        freebsd_client._ping.start.return_value = process
        freebsd_client.start()
        freebsd_client._ping.start.assert_called_once_with(
            dst_ip="10.10.10.1",
            mtu=1500,
            count=None,
            packet_size=2000,
            src_ip=None,
            timeout=None,
            args=None,
            output_file=None,
            frag=None,
            ttl=None,
            broadcast=None,
            namespace=None,
        )

    def test_stop_already_stopped_freebsd(self, freebsd_client, mocker):
        return super().stop_already_stopped(freebsd_client, mocker)

    def test_stop_freebsd(self, freebsd_client, mocker):
        return super().stop(freebsd_client, mocker)

    def test_stop_failure_freebsd(self, freebsd_client, mocker):
        return super().stop_failure(freebsd_client, mocker)

    def test_stop_with_kill_freebsd(self, freebsd_client, mocker):
        return super().stop_with_kill(freebsd_client, mocker)

    def test_run_freebsd(self, freebsd_client, mocker):
        return super().run(freebsd_client, mocker)

    def test_run_with_stop_freebsd(self, freebsd_client, mocker):
        return super().run_with_stop(freebsd_client, mocker)

    def test_validate_freebsd(self, freebsd_client, mocker):
        return super().validate(freebsd_client, mocker)


class TestESXIPingClient(TestPingTraffic):
    @pytest.fixture()
    def esxi_connection(self, mocker):
        esxi_conn = mocker.create_autospec(RPyCConnection)
        esxi_conn.get_os_name.return_value = OSName.ESXI
        yield esxi_conn

    @pytest.fixture()
    def esxi_client(self, mocker, esxi_connection):
        traffic = PingClientTraffic(connection=esxi_connection, dst_ip="10.10.10.1", packet_size=2000, mtu=1500)
        traffic._process = mocker.create_autospec(RemoteProcess)
        traffic._process.log_path = None
        yield traffic

    def test_init_esxi(self, esxi_client):
        assert isinstance(esxi_client._ping, EsxiPing)
        assert esxi_client.dst_ip == "10.10.10.1"
        assert esxi_client.packet_size == 2000
        assert esxi_client.mtu == 1500

    def test_start_esxi(self, esxi_client, mocker):
        process = mocker.create_autospec(RemoteProcess)
        esxi_client._ping.start = mocker.create_autospec(esxi_client._ping.start)
        esxi_client._ping.start.return_value = process
        esxi_client.start()
        esxi_client._ping.start.assert_called_once_with(
            dst_ip="10.10.10.1",
            mtu=1500,
            count=None,
            packet_size=2000,
            src_ip=None,
            timeout=None,
            args=None,
            output_file=None,
            frag=None,
            ttl=None,
            broadcast=None,
            namespace=None,
        )

    def test_stop_already_stopped_esxi(self, esxi_client, mocker):
        return super().stop_already_stopped(esxi_client, mocker)

    def test_stop_esxi(self, esxi_client, mocker):
        return super().stop(esxi_client, mocker)

    def test_stop_failure_esxi(self, esxi_client, mocker):
        return super().stop_failure(esxi_client, mocker)

    def test_stop_with_kill_esxi(self, esxi_client, mocker):
        return super().stop_with_kill(esxi_client, mocker)

    def test_run_esxi(self, esxi_client, mocker):
        return super().run(esxi_client, mocker)

    def test_run_with_stop_esxi(self, esxi_client, mocker):
        return super().run_with_stop(esxi_client, mocker)

    def test_validate_esxi(self, esxi_client, mocker):
        return super().validate(esxi_client, mocker)

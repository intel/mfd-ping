# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest
from unittest.mock import MagicMock

from mfd_connect.interactive_ssh import InteractiveSSHConnection

from mfd_ping.exceptions import PingException
from mfd_ping.mellanox import MellanoxPing


class TestMellanoxPing:
    @pytest.fixture
    def mellanox_ping(self, mocker):
        ping = MellanoxPing(connection=mocker.create_autospec(InteractiveSSHConnection))
        ping._connection = MagicMock()
        ping._connection.start_process = MagicMock()
        return ping

    @pytest.fixture
    def mock_process(self):
        process = MagicMock()
        process.running = False
        process.stderr_text = ""
        return process

    def test_start_ping_successful(self, mellanox_ping, mock_process):
        mock_process.stderr_text = ""
        mellanox_ping._connection.start_process.return_value = mock_process

        result = mellanox_ping.start(dst_ip="192.168.1.1", count=5)
        assert result == mock_process
        mellanox_ping._connection.start_process.assert_called_once()

    def test_start_ping_with_src_and_dst_different_versions(self, mellanox_ping):
        with pytest.raises(PingException) as excinfo:
            mellanox_ping.start(dst_ip="192.168.1.1", src_ip="2001:db8::1")
        assert "Source IP address is not in the same version as destination IP" in str(excinfo.value)

    def test_start_ping_with_invalid_args(self, mellanox_ping, mock_process):
        mock_process.stderr_text = "invalid"
        mellanox_ping._connection.start_process.return_value = mock_process

        with pytest.raises(PingException) as excinfo:
            mellanox_ping.start(dst_ip="192.168.1.1", args="-w 10")
        assert "Passed unsupported option as args" in str(excinfo.value)

    def test_start_ping_with_uncompleted_args(self, mellanox_ping, mock_process):
        mock_process.stderr_text = "option requires an argument"
        mellanox_ping._connection.start_process.return_value = mock_process

        with pytest.raises(PingException) as excinfo:
            mellanox_ping.start(dst_ip="192.168.1.1", args="-c")
        assert "Passed uncompleted option in args" in str(excinfo.value)

    def test_start_ping_problem_with_executing(self, mellanox_ping):
        mellanox_ping._connection.start_process.side_effect = Exception

        with pytest.raises(PingException) as excinfo:
            mellanox_ping.start(dst_ip="192.168.1.1", args="-c")
        assert "Problem with execution of ping command" in str(excinfo.value)

    def test_start_ping_with_general_error(self, mellanox_ping, mock_process):
        mock_process.stderr_text = "General error"
        mellanox_ping._connection.start_process.return_value = mock_process

        with pytest.raises(PingException) as excinfo:
            mellanox_ping.start(dst_ip="192.168.1.1")
        assert "Process did not start due to error" in str(excinfo.value)

    def test_prepare_arguments_with_all_options(self, mellanox_ping):
        args = mellanox_ping._prepare_arguments(dst_ip="192.168.1.1", count=5, timeout=10, args="-i 0.2")
        assert "-c 5 -i 0.2 192.168.1.1" in args

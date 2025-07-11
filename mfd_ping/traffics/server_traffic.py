# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Ping server traffic."""

import logging
from typing import Callable, Any

from mfd_common_libs import log_levels, add_logging_level
from mfd_traffic_manager.base import Traffic


logger = logging.getLogger(__name__)
add_logging_level("MODULE_DEBUG", log_levels.MODULE_DEBUG)


class PingServerTraffic(Traffic):
    """Class for Ping server traffic."""

    def __init__(self):
        """Initialize ping server traffic."""
        self._started = False
        self._running = False

    def start(self) -> None:
        """Start ping dummy server traffic."""
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg="Executing dummy server start for ping traffic",
        )
        self._started = True
        self._running = True

    def stop(self) -> None:
        """Stop ping dummy server traffic."""
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg="Executing dummy server stop for ping traffic",
        )
        self._running = False

    def run(self, duration: int) -> None:
        """
        Run ping dummy server traffic for specified duration.

        :param duration: duration of traffic in seconds
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg="Executing dummy server run for ping traffic",
        )
        self._started = True
        self._running = False  # False imitates the end state of the traffic

    def validate(self, validation_criteria: dict[Callable, dict[str, Any]] | None = None) -> bool:
        """
        Validate ping dummy server traffic by specified criteria.

        :param validation_criteria: criteria by which traffic should be validated
        :return: True if traffic is correct according to criteria, False otherwise
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg="No validation required for ping server",
        )
        return True

    @property
    def started(self) -> bool:
        """Get the dummy info if ping server process started."""
        return self._started

    @property
    def running(self) -> bool:
        """Get the dummy info if ping server process is running."""
        return self._running

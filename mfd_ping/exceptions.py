# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for exceptions."""


class PingException(Exception):
    """Handle pinging exceptions."""


class PingConnectedOSNotSupported(PingException):
    """Handle connected OS not supported exceptions."""

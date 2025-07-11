# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import time

from mfd_connect import LocalConnection
from mfd_ping import Ping
import logging

logging.basicConfig(level=logging.DEBUG)

"""
Command below will instantiate proper subclass based on local OS type
e.g. when working on Windows system, it will return WindowsPing
"""
ping_tool = Ping(connection=LocalConnection())
ping_process = ping_tool.start(dst_ip="127.0.0.1", count=10)
time.sleep(10)
print(ping_tool.stop(ping_process))

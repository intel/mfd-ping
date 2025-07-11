# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import time

from mfd_connect.interactive_ssh import InteractiveSSHConnection

from mfd_ping import Ping

# required mfd-connect>=6.45.0


conn = InteractiveSSHConnection(ip="10.10.10.10", username="", password="")

ping_tool = Ping(connection=conn)
ping_process = ping_tool.start(dst_ip="127.0.0.1")
time.sleep(10)
print(ping_tool.stop(ping_process))

# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Ping Traffic example."""
import logging

from mfd_connect import RPyCConnection
from mfd_ping import PingClientTraffic, PingServerTraffic, PingResult
from mfd_traffic_manager import TrafficManager, Stream


# example validate function
def validate_pkts_transmitted(results: PingResult, *, pkts_transmitted: int) -> bool:
    """
    Validate packets transmitted.

    :param results: PingResult
    :param pkts_sent: expected number of packets transmitted
    :return: status of validation
    """
    actual_pkts_transmitted = int(results.packets_transmitted)
    if actual_pkts_transmitted != pkts_transmitted:
        logging.debug("Number of packets transmitted are not as expected")
        return False
    return True


manager = TrafficManager()
connection = RPyCConnection(ip="1.1.1.1")

ping_client = PingClientTraffic(connection=connection, dst_ip="10.10.10.10")  # ping 10.10.10.10
ping_server = PingServerTraffic()  # Dummy ping server

ping_stream = Stream(clients=[ping_client], server=ping_server, name="Stream_1")
manager.add_stream(ping_stream)

manager.start(name="Stream_1")  # Start ping
manager.stop(name="Stream_1")  # Stop ping
manager.run(name="Stream_1", duration=5)  # Run ping for specified duration

validation_criteria = {validate_pkts_transmitted: {"pkts_transmitted": 10}}

# only client validation needed for ping
logging.debug(manager.validate(name="PingStreams_1", clients_validation_criteria=validation_criteria))

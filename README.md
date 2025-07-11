> [!IMPORTANT]  
> This project is under development. All source code and features on the main branch are for the purpose of testing or evaluation and not production ready.


# MFD Ping
Module for handling ping command.

> [!IMPORTANT]
> ESXi Users ONLY\
> This module requires `vsphere-automation-sdk` to work.\
> Please add `vsphere-automation-sdk` to your requirements file or install it manually:
> ```bash
> pip install vsphere-automation-sdk @ git+https://github.com/vmware/vsphere-automation-sdk-python@v8.0.3.0
> ```
> For currently supported version of `vsphere-automation-sdk` please refer to [mfd-esxi/README](https://github.com/intel/mfd-esxi/?tab=readme-ov-file#mfd-esxi).

## Usage
```python
from mfd_connect import LocalConnection
from mfd_ping import Ping

ping_tool = Ping(connection=LocalConnection())
ping_process = ping_tool.start(dst_ip='127.0.0.1', count=10)
print(ping_tool.stop(ping_process))
```

## API

* Start ping, `dst_ip` is required, rest of arguments are optional. "namespace" argument is available only on Linux systems.
```python
def start( 
    dst_ip: IPv4Address | IPv6Address | IPAddress | str,
    mtu: int | None = None,
    count: int | None = None,
    packet_size: int | None = None,
    src_ip: IPv4Address | IPv6Address | IPAddress | str | None = None,
    timeout: int | None = None,
    frag: bool | None = None,
    ttl: int | None = None,
    broadcast: bool | None = None,
    args: str | None = None,
    namespace: str | None = None,
    output_file: str | None = None,
    ) -> "RemoteProcess"
    """
    Start pinging destination machine.
    
    :param dst_ip: Destination IP address to perform ping
    :param mtu: Value of maximum transmission unit. Overriding usage of packet_size
    :param count: Number of echo requests to send
    :param packet_size: Size of ping packet in bytes. Not compatible with mtu. MTU size will be used instead.
    :param src_ip: Source IP address to use ping
    :param timeout: Program execution timeout, in seconds
    :param frag: Enable fragmentation
    :param ttl: Time-To-Live value
    :param broadcast: Broadcast ping
    :param args: Additional arguments to ping method
    :param namespace: Namespace in which command should be executed
    :param output_file: path to file where log will be saved
    :return: OS process with ping.
    :raises PingException:  if addresses are incorrect.
                            if ping command fails on execution
                            if passed incorrect args
    """
```
* Stop ping
```python
def stop(process: "RemoteProcess") -> "PingResult"
    """
    Kill pinging process and report result.
    
    :param process: OS process with ping.
    :return: DataClass PingResult with pass_count and fail_count of ping requests.
    """
```

`PingResult` dataclass:
```
pass_count: int - (legacy packets_transmitted)
fail_count: int - (legacy packets_transmitted - packets_received)
packets_transmitted: int
packets_received: int
packets_duplicates: int
errors: int
packet_loss: float
rtt_min: float
rtt_avg: float
rtt_max: float
```

## MTU (Maximum Transmission Unit)
**MTU** is a networking term that defines the largest packet size that can be sent over a network connection.

For IPv4 it's lowered about 28 and for IPv6 about 48 bytes (headers)

If user pass values to `mtu` and `packet_size` arguments in `start()` function at the same time, `packet_size` will be ignored and `mtu` will be used instead.

### Traffic Manager
PingClientTraffic/PingServerTraffic has been implemented with [Traffic](https://github.com/intel/mfd-traffic-manager/tree/main#traffic-api) interface. It can be used with Traffic Manager and Stream in [mfd-traffic-manager](https://github.com/intel-innersource/libraries.python.mfd.mfd-traffic-manager) as one of supported traffics.
Details are available in mfd-traffic-manager documentation.

#### `Traffic` API
All classes for specific traffics (e.g. PingClientTraffic) should inherit from Traffic base class interface.
It provides some abstract methods, all of them need to be implemented in child classes:
* `start() -> None` - start traffic 
* `stop() -> None` - stop traffic
* `run(duration: int) -> None` - run traffic for a specified number of seconds 
* `validate(validation_criteria: dict[Callable, dict[str, Any]] | None = None) -> bool` - validate traffic by passed criteria

Example usage:
```python
import time

from mfd_connect import RPyCConnection

from mfd_ping import PingClientTraffic, PingServerTraffic 
from mfd_traffic_manager import TrafficManager, Stream

manager = TrafficManager()
conn = RPyCConnection(ip="10.10.10.11") 

ping_client_1 = PingClientTraffic(connection=conn, dst_ip="12.12.12.12")
ping_client_2 = PingClientTraffic(connection=conn, dst_ip="12.12.12.13" mtu=1500)
ping_server = PingServerTraffic() # Initialize dummy server for ping traffic
ping_stream_1 = Stream(clients=[ping_client_1], server=ping_server)
ping_stream_2 = Stream(clients=[ping_client_2], server=ping_server)
manager.add_stream(ping_stream_1)
manager.add_stream(ping_stream_2)
manager.start_all()
time.sleep(3)  # some waiting or actions
manager.stop_all()
manager.validate_all()
manager.run_all(duration=5)
```

## OS supported:

Here is a place to write what OSes support your MFD module:
* WINDOWS
* LINUX
* ESXi
* FREEBSD
* Mellanox switch with InteractiveSSHConnection

## Issue reporting

If you encounter any bugs or have suggestions for improvements, you're welcome to contribute directly or open an issue [here](https://github.com/intel/mfd-ping/issues).
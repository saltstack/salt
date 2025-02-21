"""
unittests for virt_query outputter
"""

import pytest

import salt.output.virt_query as virt_query
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {virt_query: {}}


@pytest.fixture
def data():
    return {
        "suffix": "progress",
        "event": {
            "data": {
                "mysystem": {
                    "freecpu": 14,
                    "freemem": 29566.0,
                    "node_info": {
                        "cpucores": 8,
                        "cpumhz": 1089,
                        "cpumodel": "x86_64",
                        "cpus": 16,
                        "cputhreads": 2,
                        "numanodes": 1,
                        "phymemory": 30846,
                        "sockets": 1,
                    },
                    "vm_info": {
                        "vm1": {
                            "cpu": 2,
                            "cputime": 1214270000000,
                            "disks": {
                                "vda": {
                                    "file": "default/vm1-main-disk",
                                    "type": "disk",
                                    "file format": "qcow2",
                                    "virtual size": 214748364800,
                                    "disk size": 1831731200,
                                    "backing file": {
                                        "file": "/var/lib/libvirt/images/sles15sp4o",
                                        "file format": "qcow2",
                                    },
                                },
                                "hdd": {
                                    "file": "default/vm1-cloudinit-disk",
                                    "type": "cdrom",
                                    "file format": "raw",
                                    "virtual size": 374784,
                                    "disk size": 376832,
                                },
                            },
                            "graphics": {
                                "autoport": "yes",
                                "keymap": "None",
                                "listen": "0.0.0.0",
                                "port": "5900",
                                "type": "spice",
                            },
                            "nics": {
                                "aa:bb:cc:dd:ee:ff": {
                                    "type": "network",
                                    "mac": "aa:bb:cc:dd:ee:ff",
                                    "source": {"network": "default"},
                                    "model": "virtio",
                                    "address": {
                                        "type": "pci",
                                        "domain": "0x0000",
                                        "bus": "0x00",
                                        "slot": "0x03",
                                        "function": "0x0",
                                    },
                                }
                            },
                            "uuid": "yyyyyy",
                            "loader": {"path": "None"},
                            "on_crash": "destroy",
                            "on_reboot": "restart",
                            "on_poweroff": "destroy",
                            "maxMem": 1048576,
                            "mem": 1048576,
                            "state": "running",
                        },
                        "uyuni-proxy": {
                            "cpu": 2,
                            "cputime": 0,
                            "disks": {
                                "vda": {
                                    "file": "default/uyuni-proxy-main-disk",
                                    "type": "disk",
                                    "file format": "qcow2",
                                    "virtual size": 214748364800,
                                    "disk size": 4491255808,
                                    "backing file": {
                                        "file": "/var/lib/libvirt/images/leapmicro55o",
                                        "file format": "qcow2",
                                    },
                                }
                            },
                            "graphics": {
                                "autoport": "yes",
                                "keymap": "None",
                                "listen": "0.0.0.0",
                                "port": "None",
                                "type": "spice",
                            },
                            "nics": {
                                "aa:bb:cc:dd:ee:aa": {
                                    "type": "network",
                                    "mac": "aa:bb:cc:dd:ee:aa",
                                    "source": {"network": "default"},
                                    "model": "virtio",
                                    "address": {
                                        "type": "pci",
                                        "domain": "0x0000",
                                        "bus": "0x00",
                                        "slot": "0x03",
                                        "function": "0x0",
                                    },
                                }
                            },
                            "uuid": "xxxxx",
                            "loader": {"path": "None"},
                            "on_crash": "destroy",
                            "on_reboot": "restart",
                            "on_poweroff": "destroy",
                            "maxMem": 2097152,
                            "mem": 2097152,
                            "state": "shutdown",
                        },
                    },
                }
            },
            "outputter": "virt_query",
            "_stamp": "2025-02-21T11:28:04.406561",
        },
    }


def test_default_output(data):
    ret = virt_query.output(data)
    expected = """mysystem
  vm1
    CPU: 2
    Memory: 1048576
    State: running
    Disk - vda:
      Size: 1831731200
      File: default/vm1-main-disk
      File Format: qcow2
    Disk - hdd:
      Size: 376832
      File: default/vm1-cloudinit-disk
      File Format: raw
    NIC - aa:bb:cc:dd:ee:ff:
      Source: default
      Type: network
  uyuni-proxy
    CPU: 2
    Memory: 2097152
    State: shutdown
    Disk - vda:
      Size: 4491255808
      File: default/uyuni-proxy-main-disk
      File Format: qcow2
    NIC - aa:bb:cc:dd:ee:aa:
      Source: default
      Type: network
"""
    assert expected == ret

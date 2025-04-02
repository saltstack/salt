"""
Unit tests for Network runner
"""

import logging

import pytest

import salt.runners.network as network
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def mac_addr_list():
    test_list_mac_addresses = [
        "08:00:27:82:b2:ca",
        "52:54:00:ee:eb:e1",
        "52:54:00:ee:eb:e1",
    ]
    return test_list_mac_addresses.sort()


@pytest.fixture
def id_minion():
    return "test-host"


@pytest.fixture
def cache_grain_data(id_minion):
    return {
        id_minion: {
            "cwd": "/",
            "ip_gw": True,
            "ip4_gw": "192.168.0.1",
            "ip6_gw": False,
            "dns": {
                "nameservers": ["192.168.0.1"],
                "ip4_nameservers": ["192.168.0.1"],
                "ip6_nameservers": [],
                "sortlist": [],
                "domain": "",
                "search": ["example.org"],
                "options": [],
            },
            "fqdns": ["Unknown.example.org"],
            "machine_id": "ae886ddffbcc4f0da1e72769adfe0171",
            "master": "192.168.0.109",
            "server_id": 644891398,
            "localhost": "Unknown.example.org",
            "fqdn": "Unknown.example.org",
            "host": "Unknown",
            "domain": "example.org",
            "hwaddr_interfaces": {
                "lo": "00:00:00:00:00:00",
                "enp0s3": "08:00:27:82:b2:ca",
                "virbr0": "52:54:00:ee:eb:e1",
                "virbr0-nic": "52:54:00:ee:eb:e1",
            },
            "id": "test-host",
            "ip4_interfaces": {
                "lo": ["127.0.0.1"],
                "enp0s3": ["192.168.0.124"],
                "virbr0": ["192.168.122.1"],
                "virbr0-nic": [],
            },
            "ip6_interfaces": {
                "lo": ["::1"],
                "enp0s3": ["fe80::a00:27ff:fe82:b2ca"],
                "virbr0": [],
                "virbr0-nic": [],
            },
            "ipv4": ["127.0.0.1", "192.168.0.124", "192.168.122.1"],
            "ipv6": ["::1", "fe80::a00:27ff:fe82:b2ca"],
            "fqdn_ip4": ["192.168.0.70"],
            "fqdn_ip6": [],
            "ip_interfaces": {
                "lo": ["127.0.0.1", "::1"],
                "enp0s3": ["192.168.0.124", "fe80::a00:27ff:fe82:b2ca"],
                "virbr0": ["192.168.122.1"],
                "virbr0-nic": [],
            },
            "kernelparams": [
                ["BOOT_IMAGE", "/vmlinuz-3.10.0-1127.18.2.el7.x86_64"],
                ["root", "/dev/mapper/centos-root"],
                ["ro", None],
                ["rd.lvm.lv", "centos/root"],
                ["rd.lvm.lv", "centos/swap"],
                ["rhgb", None],
                ["quiet", None],
                ["LANG", "en_US.UTF-8"],
            ],
            "locale_info": {
                "defaultlanguage": "en_US",
                "defaultencoding": "UTF-8",
                "detectedencoding": "UTF-8",
                "timezone": "unknown",
            },
            "num_gpus": 1,
            "gpus": [{"vendor": "vmware", "model": "SVGA II Adapter"}],
            "kernel": "Linux",
            "nodename": "Unknown.example.org",
            "kernelrelease": "3.10.0-1127.18.2.el7.x86_64",
            "kernelversion": "#1 SMP Sun Jul 26 15:27:06 UTC 2020",
            "cpuarch": "x86_64",
            "selinux": {"enabled": False, "enforced": "Disabled"},
            "systemd": {
                "version": "219",
                "features": (
                    "+PAM +AUDIT +SELINUX +IMA -APPARMOR +SMACK +SYSVINIT +UTMP"
                    " +LIBCRYPTSETUP +GCRYPT +GNUTLS +ACL +XZ +LZ4 -SECCOMP +BLKID"
                    " +ELFUTILS +KMOD +IDN"
                ),
            },
            "init": "systemd",
            "lsb_distrib_id": "CentOS Linux",
            "lsb_distrib_codename": "CentOS Linux 7 (Core)",
            "osfullname": "CentOS Linux",
            "osrelease": "7.8.2003",
            "oscodename": "CentOS Linux 7 (Core)",
            "os": "CentOS",
            "num_cpus": 1,
            "cpu_model": "Intel(R) Core(TM) i7-8750H CPU @ 2.20GHz",
            "cpu_flags": [
                "fpu",
                "vme",
                "de",
                "pse",
                "tsc",
                "msr",
                "pae",
                "mce",
                "cx8",
                "apic",
                "sep",
                "mtrr    ",
                "pge",
                "mca",
                "cmov",
                "pat",
                "pse36",
                "clflush",
                "mmx",
                "fxsr",
                "sse",
                "sse2",
                "ht",
                "syscall",
                "nx",
                "rdtscp",
                "lm",
                "constant_tsc",
                "rep_good",
                "nopl",
                "xtopology",
                "nonstop_tsc",
                "eagerfpu",
                "pni",
                "pclmulqdq",
                "monitor",
                "ssse3",
                "cx16",
                "pcid",
                "sse4_1",
                "sse4_2",
                "x2apic",
                "movbe",
                "popcnt",
                "aes",
                "xsave",
                "avx",
                "rdrand",
                "hypervisor",
                "lahf_lm",
                "abm",
                "3dnowprefetch",
                "invpcid_single",
                "fsgsbase",
                "avx2",
                "inv    pcid",
                "rdseed",
                "clflushopt",
                "md_clear",
                "flush_l1d",
            ],
            "os_family": "RedHat",
            "osarch": "x86_64",
            "mem_total": 1998,
            "swap_total": 2047,
            "biosversion": "VirtualBox",
            "productname": "VirtualBox",
            "manufacturer": "innotek GmbH",
            "biosreleasedate": "12/01/2006",
            "uuid": "dd95fedd-1a2b-5e48-86a7-7e339f9f02a1",
            "serialnumber": "0",
            "virtual": "VirtualBox",
            "ps": "ps -efHww",
            "osrelease_info": [7, 8, 2003],
            "osmajorrelease": 7,
            "osfinger": "CentOS Linux-7",
            "path": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin",
            "systempath": [
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/sbin",
                "/usr/bin",
            ],
            "pythonexecutable": "/usr/bin/python3",
            "pythonpath": [
                "/usr/bin",
                "/usr/lib64/python36.zip",
                "/usr/lib64/python3.6",
                "/usr/lib64/python3.6/lib-dynload",
                "/usr/lib64/python3.6/site-packages",
                "/usr/lib/python3.6/site-packages",
            ],
            "pythonversion": [3, 6, 8, "final", 0],
            "saltpath": "/usr/lib/python3.6/site-packages/salt",
            "saltversion": "3003",
            "saltversioninfo": [3003],
            "zmqversion": "4.1.4",
            "disks": ["sda", "sr0"],
            "ssds": [],
            "shell": "/bin/sh",
            "lvm": {"centos": ["root", "swap"]},
            "mdadm": [],
            "username": "root",
            "groupname": "root",
            "pid": 2469,
            "gid": 0,
            "uid": 0,
            "zfs_support": False,
            "zfs_feature_flags": False,
        }
    }


@pytest.fixture
def configure_loader_modules():

    return {
        network: {
            "__grains__": {
                "osarch": "x86_64",
                "os_family": "Redhat",
                "osmajorrelease": 7,
                "kernelrelease": "3.10.0-1127.18.2.el7.x86_64",
            },
        },
    }


def test_wolmatch(cache_grain_data, id_minion, mac_addr_list):
    """
    Test wolmatch
    """
    cache_mock = MagicMock(return_value=cache_grain_data)
    patches = {
        "cache.grains": cache_mock,
    }
    wol_out = MagicMock(return_value=mac_addr_list)
    with patch.dict(network.__salt__, patches):
        with patch("salt.runners.network.wol", wol_out):
            added = network.wolmatch(id_minion)
            assert added.sort() == mac_addr_list

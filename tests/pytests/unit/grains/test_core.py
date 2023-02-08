"""
tests.pytests.unit.grains.test_core
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: Erik Johnson <erik@saltstack.com>
    :codeauthor: David Murphy <damurphy@vmware.com>
"""

import errno
import logging
import os
import pathlib
import platform
import socket
import sys
import tempfile
import textwrap
from collections import namedtuple

import pytest

import salt.grains.core as core
import salt.loader
import salt.modules.cmdmod
import salt.modules.network
import salt.modules.smbios
import salt.utils.dns
import salt.utils.files
import salt.utils.network
import salt.utils.path
import salt.utils.platform
from salt._compat import ipaddress
from tests.support.mock import MagicMock, Mock, mock_open, patch

log = logging.getLogger(__name__)


@pytest.fixture
def ipv4_tuple():
    """
    return tuple of IPv4 local, addr1, addr2
    """
    return ("127.0.0.1", "10.0.0.1", "10.0.0.2")


@pytest.fixture
def ipv6_tuple():
    """
    return tuple of IPv6 local, addr1, addr2, scope
    """
    return (
        "::1",
        "2001:4860:4860::8844",
        "2001:4860:4860::8888",
        "fe80::6238:e0ff:fe06:3f6b%enp2s0",
    )


@pytest.fixture
def os_release_dir():
    return pathlib.Path(__file__).parent.joinpath("os-releases")


@pytest.fixture
def solaris_dir():
    return pathlib.Path(__file__).parent.joinpath("solaris")


@pytest.fixture
def configure_loader_modules():
    return {core: {}}


@pytest.mark.skipif(
    sys.version_info >= (3, 10), reason="_parse_os_release() not defined/used"
)
def test_parse_etc_os_release():
    with patch("os.path.isfile", return_value="/usr/lib/os-release"):
        # /etc/os-release file taken from base-files 9.6ubuntu102
        os_release_content = textwrap.dedent(
            """
            NAME="Ubuntu"
            VERSION="17.10 (Artful Aardvark)"
            ID=ubuntu
            ID_LIKE=debian
            PRETTY_NAME="Ubuntu 17.10"
            VERSION_ID="17.10"
            HOME_URL="https://www.ubuntu.com/"
            SUPPORT_URL="https://help.ubuntu.com/"
            BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
            PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
            VERSION_CODENAME=artful
            UBUNTU_CODENAME=artful
            """
        )
    with patch("salt.utils.files.fopen", mock_open(read_data=os_release_content)):
        os_release = core._parse_os_release("/etc/os-release", "/usr/lib/os-release")
    assert os_release == {
        "NAME": "Ubuntu",
        "VERSION": "17.10 (Artful Aardvark)",
        "ID": "ubuntu",
        "ID_LIKE": "debian",
        "PRETTY_NAME": "Ubuntu 17.10",
        "VERSION_ID": "17.10",
        "HOME_URL": "https://www.ubuntu.com/",
        "SUPPORT_URL": "https://help.ubuntu.com/",
        "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
        "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
        "VERSION_CODENAME": "artful",
        "UBUNTU_CODENAME": "artful",
    }


def test_network_grains_secondary_ip(tmp_path):
    """
    Secondary IP should be added to IPv4 or IPv6 address list depending on type
    """
    data = {
        "wlo1": {
            "up": True,
            "hwaddr": "29:9f:9f:e9:67:f4",
            "inet": [
                {
                    "address": "172.16.13.85",
                    "netmask": "255.255.248.0",
                    "broadcast": "172.16.15.255",
                    "label": "wlo1",
                }
            ],
            "inet6": [
                {
                    "address": "2001:4860:4860::8844",
                    "prefixlen": "64",
                    "scope": "fe80::6238:e0ff:fe06:3f6b%enp2s0",
                }
            ],
            "secondary": [
                {
                    "type": "inet",
                    "address": "172.16.13.86",
                    "netmask": "255.255.248.0",
                    "broadcast": "172.16.15.255",
                    "label": "wlo1",
                },
                {
                    "type": "inet6",
                    "address": "2001:4860:4860::8888",
                    "prefixlen": "64",
                    "scope": "fe80::6238:e0ff:fe06:3f6b%enp2s0",
                },
            ],
        }
    }
    cache_dir = tmp_path / "cache"
    extmods = tmp_path / "extmods"
    opts = {
        "cachedir": str(cache_dir),
        "extension_modules": str(extmods),
        "optimization_order": [0],
    }
    with patch("salt.utils.network.interfaces", side_effect=[data]):
        grains = salt.loader.grain_funcs(opts)
        ret_ip4 = grains["core.ip4_interfaces"]()
        assert ret_ip4["ip4_interfaces"]["wlo1"] == ["172.16.13.85", "172.16.13.86"]

        ret_ip6 = grains["core.ip6_interfaces"]()
        assert ret_ip6["ip6_interfaces"]["wlo1"] == [
            "2001:4860:4860::8844",
            "2001:4860:4860::8888",
        ]

        ret_ip = grains["core.ip_interfaces"]()
        assert ret_ip["ip_interfaces"]["wlo1"] == [
            "172.16.13.85",
            "2001:4860:4860::8844",
            "172.16.13.86",
            "2001:4860:4860::8888",
        ]


def test_network_grains_cache(tmp_path):
    """
    Network interfaces are cache is cleared by the loader
    """
    call_1 = {
        "lo": {
            "up": True,
            "hwaddr": "00:00:00:00:00:00",
            "inet": [
                {
                    "address": "127.0.0.1",
                    "netmask": "255.0.0.0",
                    "broadcast": None,
                    "label": "lo",
                }
            ],
            "inet6": [],
        },
        "wlo1": {
            "up": True,
            "hwaddr": "29:9f:9f:e9:67:f4",
            "inet": [
                {
                    "address": "172.16.13.85",
                    "netmask": "255.255.248.0",
                    "broadcast": "172.16.15.255",
                    "label": "wlo1",
                }
            ],
            "inet6": [],
        },
    }
    call_2 = {
        "lo": {
            "up": True,
            "hwaddr": "00:00:00:00:00:00",
            "inet": [
                {
                    "address": "127.0.0.1",
                    "netmask": "255.0.0.0",
                    "broadcast": None,
                    "label": "lo",
                }
            ],
            "inet6": [],
        },
        "wlo1": {
            "up": True,
            "hwaddr": "29:9f:9f:e9:67:f4",
            "inet": [
                {
                    "address": "172.16.13.86",
                    "netmask": "255.255.248.0",
                    "broadcast": "172.16.15.255",
                    "label": "wlo1",
                }
            ],
            "inet6": [],
        },
    }
    cache_dir = tmp_path / "cache"
    extmods = tmp_path / "extmods"
    opts = {
        "cachedir": str(cache_dir),
        "extension_modules": str(extmods),
        "optimization_order": [0],
    }
    with patch(
        "salt.utils.network.interfaces", side_effect=[call_1, call_2]
    ) as interfaces:
        grains = salt.loader.grain_funcs(opts)
        assert interfaces.call_count == 0
        ret = grains["core.ip_interfaces"]()
        # interfaces has been called
        assert interfaces.call_count == 1
        assert ret["ip_interfaces"]["wlo1"] == ["172.16.13.85"]
        # interfaces has been cached
        ret = grains["core.ip_interfaces"]()
        assert interfaces.call_count == 1
        assert ret["ip_interfaces"]["wlo1"] == ["172.16.13.85"]

        grains = salt.loader.grain_funcs(opts)
        ret = grains["core.ip_interfaces"]()
        # A new loader clears the cache and interfaces is called again
        assert interfaces.call_count == 2
        assert ret["ip_interfaces"]["wlo1"] == ["172.16.13.86"]


@pytest.mark.parametrize(
    "cpe,cpe_ret",
    (
        (
            "cpe:/o:opensuse:leap:15.0",
            {
                "phase": None,
                "version": "15.0",
                "product": "leap",
                "vendor": "opensuse",
                "part": "operating system",
            },
        ),
        (
            "cpe:/o:vendor:product:42:beta",
            {
                "phase": "beta",
                "version": "42",
                "product": "product",
                "vendor": "vendor",
                "part": "operating system",
            },
        ),
    ),
)
def test_parse_cpe_name_wfn(cpe, cpe_ret):
    """
    Parse correct CPE_NAME data WFN formatted
    :return:
    """
    ret = core._parse_cpe_name(cpe)
    for key, value in cpe_ret.items():
        assert key in ret
        assert ret[key] == value


@pytest.mark.parametrize(
    "cpe,cpe_ret",
    (
        (
            "cpe:2.3:o:microsoft:windows_xp:5.1.601:beta:*:*:*:*:*:*",
            {
                "phase": "beta",
                "version": "5.1.601",
                "product": "windows_xp",
                "vendor": "microsoft",
                "part": "operating system",
            },
        ),
        (
            "cpe:2.3:h:corellian:millenium_falcon:1.0:*:*:*:*:*:*:*",
            {
                "phase": None,
                "version": "1.0",
                "product": "millenium_falcon",
                "vendor": "corellian",
                "part": "hardware",
            },
        ),
        (
            "cpe:2.3:*:dark_empire:light_saber:3.0:beta:*:*:*:*:*:*",
            {
                "phase": "beta",
                "version": "3.0",
                "product": "light_saber",
                "vendor": "dark_empire",
                "part": None,
            },
        ),
    ),
)
def test_parse_cpe_name_v23(cpe, cpe_ret):
    """
    Parse correct CPE_NAME data v2.3 formatted
    :return:
    """
    ret = core._parse_cpe_name(cpe)
    for key, value in cpe_ret.items():
        assert key in ret
        assert ret[key] == value


@pytest.mark.parametrize(
    "cpe",
    (
        "cpe:broken",
        "cpe:broken:in:all:ways:*:*:*:*",
        "cpe:x:still:broken:123",
        "who:/knows:what:is:here",
    ),
)
def test_parse_cpe_name_broken(cpe):
    """
    Parse broken CPE_NAME data
    :return:
    """
    assert core._parse_cpe_name(cpe) == {}


@pytest.mark.skipif(
    sys.version_info >= (3, 10), reason="_parse_os_release() not defined/used"
)
def test_missing_os_release():
    with patch("salt.utils.files.fopen", mock_open(read_data={})):
        with pytest.raises(OSError):
            core._parse_os_release("/etc/os-release", "/usr/lib/os-release")


def test__linux_lsb_distrib_data():
    lsb_distro_information = {
        "ID": "Ubuntu",
        "DESCRIPTION": "Ubuntu 20.04.3 LTS",
        "RELEASE": "20.04",
        "CODENAME": "focal",
    }
    expectation = {
        "lsb_distrib_id": "Ubuntu",
        "lsb_distrib_description": "Ubuntu 20.04.3 LTS",
        "lsb_distrib_release": "20.04",
        "lsb_distrib_codename": "focal",
    }

    orig_import = __import__

    def _import_mock(name, *args):
        if name == "lsb_release":
            lsb_release_mock = MagicMock()
            lsb_release_mock.get_distro_information.return_value = (
                lsb_distro_information
            )
            return lsb_release_mock
        return orig_import(name, *args)

    with patch("{}.__import__".format("builtins"), side_effect=_import_mock):
        grains, has_error = core._linux_lsb_distrib_data()

    assert grains == expectation
    assert not has_error


@pytest.mark.skip_unless_on_linux
def test_gnu_slash_linux_in_os_name():
    """
    Test to return a list of all enabled services
    """
    _path_exists_map = {"/proc/1/cmdline": False}
    _path_isfile_map = {}
    _cmd_run_map = {
        "dpkg --print-architecture": "amd64",
    }

    path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
    path_isfile_mock = MagicMock(side_effect=lambda x: _path_isfile_map.get(x, False))
    cmd_run_mock = MagicMock(side_effect=lambda x: _cmd_run_map[x])
    empty_mock = MagicMock(return_value={})
    missing_os_release_mock = MagicMock(
        side_effect=OSError(errno.ENOENT, "no os-release files")
    )

    orig_import = __import__
    built_in = "builtins"

    def _import_mock(name, *args):
        if name == "lsb_release":
            raise ImportError("No module named lsb_release")
        return orig_import(name, *args)

    # - Skip the first if statement
    # - Skip the selinux/systemd stuff (not pertinent)
    # - Skip the init grain compilation (not pertinent)
    # - Ensure that lsb_release fails to import
    # - Skip all the /etc/*-release stuff (not pertinent)
    # - Mock _linux_distribution to give us the OS name that we want
    # - Make a bunch of functions return empty dicts, we don't care about
    #   these grains for the purposes of this test.
    # - Mock the osarch
    distro_mock = MagicMock(return_value=("Debian GNU/Linux", "8.3", ""))
    with patch.object(
        salt.utils.platform, "is_proxy", MagicMock(return_value=False)
    ), patch.object(
        core, "_linux_bin_exists", MagicMock(return_value=False)
    ), patch.object(
        os.path, "exists", path_exists_mock
    ), patch(
        "{}.__import__".format(built_in), side_effect=_import_mock
    ), patch.object(
        os.path, "isfile", path_isfile_mock
    ), patch.object(
        core, "_parse_lsb_release", empty_mock
    ), patch.object(
        core, "_freedesktop_os_release", missing_os_release_mock
    ), patch.object(
        core, "_parse_lsb_release", empty_mock
    ), patch.object(
        core, "_linux_distribution", distro_mock
    ), patch.object(
        core, "_linux_cpudata", empty_mock
    ), patch.object(
        core, "_linux_gpu_data", empty_mock
    ), patch.object(
        core, "_memdata", empty_mock
    ), patch.object(
        core, "_hw_data", empty_mock
    ), patch.object(
        core, "_virtual", empty_mock
    ), patch.object(
        core, "_ps", empty_mock
    ), patch.dict(
        core.__salt__, {"cmd.run": cmd_run_mock}
    ):
        os_grains = core.os_data()

    assert os_grains.get("os_family") == "Debian"


@pytest.mark.skip_unless_on_linux
def test_suse_os_from_cpe_data():
    """
    Test if 'os' grain is parsed from CPE_NAME of /etc/os-release
    """
    _path_exists_map = {"/proc/1/cmdline": False}
    _os_release_map = {
        "NAME": "SLES",
        "VERSION": "12-SP1",
        "VERSION_ID": "12.1",
        "PRETTY_NAME": "SUSE Linux Enterprise Server 12 SP1",
        "ID": "sles",
        "ANSI_COLOR": "0;32",
        "CPE_NAME": "cpe:/o:suse:sles:12:sp1",
    }

    path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
    empty_mock = MagicMock(return_value={})
    osarch_mock = MagicMock(return_value="amd64")
    os_release_mock = MagicMock(return_value=_os_release_map)

    orig_import = __import__
    built_in = "builtins"

    def _import_mock(name, *args):
        if name == "lsb_release":
            raise ImportError("No module named lsb_release")
        return orig_import(name, *args)

    distro_mock = MagicMock(
        return_value=("SUSE Linux Enterprise Server ", "12", "x86_64")
    )

    # - Skip the first if statement
    # - Skip the selinux/systemd stuff (not pertinent)
    # - Skip the init grain compilation (not pertinent)
    # - Ensure that lsb_release fails to import
    # - Skip all the /etc/*-release stuff (not pertinent)
    # - Mock _linux_distribution to give us the OS name that we want
    # - Mock the osarch
    with patch.object(
        salt.utils.platform, "is_proxy", MagicMock(return_value=False)
    ), patch.object(
        core, "_linux_bin_exists", MagicMock(return_value=False)
    ), patch.object(
        os.path, "exists", path_exists_mock
    ), patch(
        "{}.__import__".format(built_in), side_effect=_import_mock
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ), patch.object(
        core, "_freedesktop_os_release", os_release_mock
    ), patch.object(
        core, "_parse_lsb_release", empty_mock
    ), patch.object(
        core, "_linux_distribution", distro_mock
    ), patch.object(
        core, "_linux_gpu_data", empty_mock
    ), patch.object(
        core, "_hw_data", empty_mock
    ), patch.object(
        core, "_linux_cpudata", empty_mock
    ), patch.object(
        core, "_virtual", empty_mock
    ), patch.dict(
        core.__salt__, {"cmd.run": osarch_mock}
    ):
        os_grains = core.os_data()

    assert os_grains.get("os_family") == "Suse"
    assert os_grains.get("os") == "SUSE"


def _run_os_grains_tests(os_release_data, os_release_map, expectation):
    path_isfile_mock = MagicMock(
        side_effect=lambda x: x in os_release_map.get("files", [])
    )
    empty_mock = MagicMock(return_value={})
    osarch_mock = MagicMock(return_value="amd64")

    if os_release_data:
        freedesktop_os_release_mock = MagicMock(return_value=os_release_data)
    else:
        freedesktop_os_release_mock = MagicMock(
            side_effect=OSError(
                errno.ENOENT,
                "Unable to read files /etc/os-release, /usr/lib/os-release",
            )
        )

    orig_import = __import__
    built_in = "builtins"

    def _import_mock(name, *args):
        if name == "lsb_release":
            raise ImportError("No module named lsb_release")
        return orig_import(name, *args)

    suse_release_file = os_release_map.get("suse_release_file")

    file_contents = {"/proc/1/cmdline": ""}
    if suse_release_file:
        file_contents["/etc/SuSE-release"] = suse_release_file

    # - Skip the first if statement
    # - Skip the selinux/systemd stuff (not pertinent)
    # - Skip the init grain compilation (not pertinent)
    # - Ensure that lsb_release fails to import
    # - Skip all the /etc/*-release stuff (not pertinent)
    # - Mock _linux_distribution to give us the OS name that we want
    # - Mock the osarch
    _linux_distribution = os_release_map.get(
        "_linux_distribution", ("id", "version", "codename")
    )
    distro_mock = MagicMock(return_value=_linux_distribution)
    with patch.object(
        salt.utils.platform, "is_proxy", MagicMock(return_value=False)
    ), patch.object(
        core, "_linux_bin_exists", MagicMock(return_value=False)
    ), patch.object(
        os.path, "exists", path_isfile_mock
    ), patch(
        "{}.__import__".format(built_in), side_effect=_import_mock
    ), patch.object(
        os.path, "isfile", path_isfile_mock
    ), patch.object(
        core, "_freedesktop_os_release", freedesktop_os_release_mock
    ), patch.object(
        core, "_parse_lsb_release", empty_mock
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=file_contents)
    ), patch.object(
        core, "_linux_distribution", distro_mock
    ), patch.object(
        core, "_linux_gpu_data", empty_mock
    ), patch.object(
        core, "_linux_cpudata", empty_mock
    ), patch.object(
        core, "_virtual", empty_mock
    ), patch.dict(
        core.__salt__, {"cmd.run": osarch_mock}
    ):
        os_grains = core.os_data()

    grains = {
        k: v
        for k, v in os_grains.items()
        if k
        in {
            "os",
            "os_family",
            "osfullname",
            "oscodename",
            "osfinger",
            "osrelease",
            "osrelease_info",
            "osmajorrelease",
        }
    }
    assert grains == expectation


def _run_suse_os_grains_tests(os_release_data, os_release_map, expectation):
    expectation["os"] = "SUSE"
    expectation["os_family"] = "Suse"
    _run_os_grains_tests(os_release_data, os_release_map, expectation)


@pytest.mark.skip_unless_on_linux
def test_suse_os_grains_sles11sp3():
    """
    Test if OS grains are parsed correctly in SLES 11 SP3
    """
    _os_release_map = {
        "suse_release_file": textwrap.dedent(
            """
            SUSE Linux Enterprise Server 11 (x86_64)
            VERSION = 11
            PATCHLEVEL = 3
            """
        ),
        "files": ["/etc/SuSE-release"],
    }
    expectation = {
        "oscodename": "SUSE Linux Enterprise Server 11 SP3",
        "osfullname": "SLES",
        "osrelease": "11.3",
        "osrelease_info": (11, 3),
        "osmajorrelease": 11,
        "osfinger": "SLES-11",
    }
    _run_suse_os_grains_tests(None, _os_release_map, expectation)


@pytest.mark.skip_unless_on_linux
def test_suse_os_grains_sles11sp4():
    """
    Test if OS grains are parsed correctly in SLES 11 SP4
    """
    _os_release_data = {
        "NAME": "SLES",
        "VERSION": "11.4",
        "VERSION_ID": "11.4",
        "PRETTY_NAME": "SUSE Linux Enterprise Server 11 SP4",
        "ID": "sles",
        "ANSI_COLOR": "0;32",
        "CPE_NAME": "cpe:/o:suse:sles:11:4",
    }
    expectation = {
        "oscodename": "SUSE Linux Enterprise Server 11 SP4",
        "osfullname": "SLES",
        "osrelease": "11.4",
        "osrelease_info": (11, 4),
        "osmajorrelease": 11,
        "osfinger": "SLES-11",
    }
    _run_suse_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_suse_os_grains_sles12():
    """
    Test if OS grains are parsed correctly in SLES 12
    """
    _os_release_data = {
        "NAME": "SLES",
        "VERSION": "12",
        "VERSION_ID": "12",
        "PRETTY_NAME": "SUSE Linux Enterprise Server 12",
        "ID": "sles",
        "ANSI_COLOR": "0;32",
        "CPE_NAME": "cpe:/o:suse:sles:12",
    }
    expectation = {
        "oscodename": "SUSE Linux Enterprise Server 12",
        "osfullname": "SLES",
        "osrelease": "12",
        "osrelease_info": (12,),
        "osmajorrelease": 12,
        "osfinger": "SLES-12",
    }
    _run_suse_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_suse_os_grains_sles12sp1():
    """
    Test if OS grains are parsed correctly in SLES 12 SP1
    """
    _os_release_data = {
        "NAME": "SLES",
        "VERSION": "12-SP1",
        "VERSION_ID": "12.1",
        "PRETTY_NAME": "SUSE Linux Enterprise Server 12 SP1",
        "ID": "sles",
        "ANSI_COLOR": "0;32",
        "CPE_NAME": "cpe:/o:suse:sles:12:sp1",
    }
    expectation = {
        "oscodename": "SUSE Linux Enterprise Server 12 SP1",
        "osfullname": "SLES",
        "osrelease": "12.1",
        "osrelease_info": (12, 1),
        "osmajorrelease": 12,
        "osfinger": "SLES-12",
    }
    _run_suse_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_suse_os_grains_opensuse_leap_42_1():
    """
    Test if OS grains are parsed correctly in openSUSE Leap 42.1
    """
    _os_release_data = {
        "NAME": "openSUSE Leap",
        "VERSION": "42.1",
        "VERSION_ID": "42.1",
        "PRETTY_NAME": "openSUSE Leap 42.1 (x86_64)",
        "ID": "opensuse",
        "ANSI_COLOR": "0;32",
        "CPE_NAME": "cpe:/o:opensuse:opensuse:42.1",
    }
    expectation = {
        "oscodename": "openSUSE Leap 42.1 (x86_64)",
        "osfullname": "Leap",
        "osrelease": "42.1",
        "osrelease_info": (42, 1),
        "osmajorrelease": 42,
        "osfinger": "Leap-42",
    }
    _run_suse_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_suse_os_grains_tumbleweed():
    """
    Test if OS grains are parsed correctly in openSUSE Tumbleweed
    """
    _os_release_data = {
        "NAME": "openSUSE",
        "VERSION": "Tumbleweed",
        "VERSION_ID": "20160504",
        "PRETTY_NAME": "openSUSE Tumbleweed (20160504) (x86_64)",
        "ID": "opensuse",
        "ANSI_COLOR": "0;32",
        "CPE_NAME": "cpe:/o:opensuse:opensuse:20160504",
    }
    expectation = {
        "oscodename": "openSUSE Tumbleweed (20160504) (x86_64)",
        "osfullname": "Tumbleweed",
        "osrelease": "20160504",
        "osrelease_info": (20160504,),
        "osmajorrelease": 20160504,
        "osfinger": "Tumbleweed-20160504",
    }
    _run_suse_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_debian_9_os_grains():
    """
    Test if OS grains are parsed correctly in Debian 9 "stretch"
    """
    # /etc/os-release data taken from base-files 9.9+deb9u13
    _os_release_data = {
        "PRETTY_NAME": "Debian GNU/Linux 9 (stretch)",
        "NAME": "Debian GNU/Linux",
        "VERSION_ID": "9",
        "VERSION": "9 (stretch)",
        "VERSION_CODENAME": "stretch",
        "ID": "debian",
        "HOME_URL": "https://www.debian.org/",
        "SUPPORT_URL": "https://www.debian.org/support",
        "BUG_REPORT_URL": "https://bugs.debian.org/",
    }
    expectation = {
        "os": "Debian",
        "os_family": "Debian",
        "oscodename": "stretch",
        "osfullname": "Debian GNU/Linux",
        "osrelease": "9",
        "osrelease_info": (9,),
        "osmajorrelease": 9,
        "osfinger": "Debian-9",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_debian_10_os_grains():
    """
    Test if OS grains are parsed correctly in Debian 10 "buster"
    """
    # /etc/os-release data taken from base-files 10.3+deb10u11
    _os_release_data = {
        "PRETTY_NAME": "Debian GNU/Linux 10 (buster)",
        "NAME": "Debian GNU/Linux",
        "VERSION_ID": "10",
        "VERSION": "10 (buster)",
        "VERSION_CODENAME": "buster",
        "ID": "debian",
        "HOME_URL": "https://www.debian.org/",
        "SUPPORT_URL": "https://www.debian.org/support",
        "BUG_REPORT_URL": "https://bugs.debian.org/",
    }
    expectation = {
        "os": "Debian",
        "os_family": "Debian",
        "oscodename": "buster",
        "osfullname": "Debian GNU/Linux",
        "osrelease": "10",
        "osrelease_info": (10,),
        "osmajorrelease": 10,
        "osfinger": "Debian-10",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_debian_11_os_grains():
    """
    Test if OS grains are parsed correctly in Debian 11 "bullseye"
    """
    # /etc/os-release data taken from base-files 11.1+deb11u2
    _os_release_data = {
        "PRETTY_NAME": "Debian GNU/Linux 11 (bullseye)",
        "NAME": "Debian GNU/Linux",
        "VERSION_ID": "11",
        "VERSION": "11 (bullseye)",
        "VERSION_CODENAME": "bullseye",
        "ID": "debian",
        "HOME_URL": "https://www.debian.org/",
        "SUPPORT_URL": "https://www.debian.org/support",
        "BUG_REPORT_URL": "https://bugs.debian.org/",
    }
    expectation = {
        "os": "Debian",
        "os_family": "Debian",
        "oscodename": "bullseye",
        "osfullname": "Debian GNU/Linux",
        "osrelease": "11",
        "osrelease_info": (11,),
        "osmajorrelease": 11,
        "osfinger": "Debian-11",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_centos_8_os_grains():
    """
    Test if OS grains are parsed correctly in Centos 8
    """
    _os_release_data = {
        "NAME": "CentOS Linux",
        "VERSION": "8 (Core)",
        "VERSION_ID": "8",
        "PRETTY_NAME": "CentOS Linux 8 (Core)",
        "ID": "centos",
        "ANSI_COLOR": "0;31",
        "CPE_NAME": "cpe:/o:centos:centos:8",
    }
    _os_release_map = {
        "_linux_distribution": ("centos", "8.1.1911", "Core"),
    }

    expectation = {
        "os": "CentOS",
        "os_family": "RedHat",
        "oscodename": "CentOS Linux 8 (Core)",
        "osfullname": "CentOS Linux",
        "osrelease": "8.1.1911",
        "osrelease_info": (8, 1, 1911),
        "osmajorrelease": 8,
        "osfinger": "CentOS Linux-8",
    }
    _run_os_grains_tests(_os_release_data, _os_release_map, expectation)


@pytest.mark.skip_unless_on_linux
def test_alinux2_os_grains():
    """
    Test if OS grains are parsed correctly in Alibaba Cloud Linux
    """
    _os_release_data = {
        "NAME": "Alibaba Cloud Linux (Aliyun Linux)",
        "VERSION": "2.1903 LTS (Hunting Beagle)",
        "VERSION_ID": "2.1903",
        "PRETTY_NAME": "Alibaba Cloud Linux (Aliyun Linux) 2.1903 LTS (Hunting Beagle)",
        "ID": "alinux",
        "ANSI_COLOR": "0;31",
    }
    _os_release_map = {
        "_linux_distribution": ("alinux", "2.1903", "LTS"),
    }

    expectation = {
        "os": "Alinux",
        "os_family": "RedHat",
        "oscodename": "Alibaba Cloud Linux (Aliyun Linux) 2.1903 LTS (Hunting Beagle)",
        "osfullname": "Alibaba Cloud Linux (Aliyun Linux)",
        "osrelease": "2.1903",
        "osrelease_info": (2, 1903),
        "osmajorrelease": 2,
        "osfinger": "Alibaba Cloud Linux (Aliyun Linux)-2",
    }
    _run_os_grains_tests(_os_release_data, _os_release_map, expectation)


@pytest.mark.skip_unless_on_linux
def test_centos_stream_8_os_grains():
    """
    Test if OS grains are parsed correctly in Centos 8
    """
    _os_release_data = {
        "NAME": "CentOS Stream",
        "VERSION": "8",
        "VERSION_ID": "8",
        "PRETTY_NAME": "CentOS Stream 8",
        "ID": "centos",
        "ANSI_COLOR": "0;31",
        "CPE_NAME": "cpe:/o:centos:centos:8",
    }
    _os_release_map = {
        "_linux_distribution": ("centos", "8", ""),
    }

    expectation = {
        "os": "CentOS Stream",
        "os_family": "RedHat",
        "oscodename": "CentOS Stream 8",
        "osfullname": "CentOS Stream",
        "osrelease": "8",
        "osrelease_info": (8,),
        "osmajorrelease": 8,
        "osfinger": "CentOS Stream-8",
    }
    _run_os_grains_tests(_os_release_data, _os_release_map, expectation)


@pytest.mark.skip_unless_on_linux
def test_rocky_8_os_grains():
    """
    Test if OS grains are parsed correctly in Rocky Linux 8
    """
    # /etc/os-release data taken from Docker image rockylinux:8
    _os_release_data = {
        "NAME": "Rocky Linux",
        "VERSION": "8.5 (Green Obsidian)",
        "ID": "rocky",
        "ID_LIKE": "rhel centos fedora",
        "VERSION_ID": "8.5",
        "PLATFORM_ID": "platform:el8",
        "PRETTY_NAME": "Rocky Linux 8.5 (Green Obsidian)",
        "ANSI_COLOR": "0;32",
        "CPE_NAME": "cpe:/o:rocky:rocky:8.5:GA",
        "HOME_URL": "https://rockylinux.org/",
        "BUG_REPORT_URL": "https://bugs.rockylinux.org/",
        "ROCKY_SUPPORT_PRODUCT": "Rocky Linux",
        "ROCKY_SUPPORT_PRODUCT_VERSION": "8",
    }
    expectation = {
        "os": "Rocky",
        "os_family": "RedHat",
        "oscodename": "Green Obsidian",
        "osfullname": "Rocky Linux",
        "osrelease": "8.5",
        "osrelease_info": (8, 5),
        "osmajorrelease": 8,
        "osfinger": "Rocky Linux-8",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_osmc_os_grains():
    """
    Test if OS grains are parsed correctly in OSMC
    """
    _os_release_map = {
        "_linux_distribution": ("OSMC", "2022.03-1", "Open Source Media Center"),
    }

    expectation = {
        "os": "OSMC",
        "os_family": "Debian",
        "oscodename": "Open Source Media Center",
        "osfullname": "OSMC",
        "osrelease": "2022.03-1",
        "osrelease_info": (2022, "03-1"),
        "osmajorrelease": 2022,
        "osfinger": "OSMC-2022",
    }
    _run_os_grains_tests(None, _os_release_map, expectation)


@pytest.mark.skip_unless_on_linux
def test_mendel_os_grains():
    """
    Test if OS grains are parsed correctly in Mendel Linux 5.3 Eagle (Nov 2021)
    """
    # From https://coral.ai/software/
    # downloaded enterprise-eagle-flashcard-20211117215217.zip
    # -> flashcard_arm64.img -> rootfs.img -> /etc/os-release
    _os_release_data = {
        "PRETTY_NAME": "Mendel GNU/Linux 5 (Eagle)",
        "NAME": "Mendel GNU/Linux",
        "ID": "mendel",
        "ID_LIKE": "debian",
        "HOME_URL": "https://coral.ai/",
        "SUPPORT_URL": "https://coral.ai/",
        "BUG_REPORT_URL": "https://coral.ai/",
        "VERSION_CODENAME": "eagle",
    }
    expectation = {
        "os": "Mendel",
        "os_family": "Debian",
        "oscodename": "eagle",
        "osfullname": "Mendel GNU/Linux",
        "osrelease": "5",
        "osrelease_info": (5,),
        "osmajorrelease": 5,
        "osfinger": "Mendel GNU/Linux-5",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_almalinux_8_os_grains():
    """
    Test if OS grains are parsed correctly in AlmaLinux 8
    """
    # /etc/os-release data taken from Docker image almalinux:8
    _os_release_data = {
        "NAME": "AlmaLinux",
        "ID": "almalinux",
        "PRETTY_NAME": "AlmaLinux 8.5 (Arctic Sphynx)",
        "VERSION": "8.5 (Arctic Sphynx)",
        "ID_LIKE": "rhel centos fedora",
        "VERSION_ID": "8.5",
        "PLATFORM_ID": "platform:el8",
        "ANSI_COLOR": "0;34",
        "CPE_NAME": "cpe:/o:almalinux:almalinux:8::baseos",
        "HOME_URL": "https://almalinux.org/",
        "DOCUMENTATION_URL": "https://wiki.almalinux.org/",
        "BUG_REPORT_URL": "https://bugs.almalinux.org/",
        "ALMALINUX_MANTISBT_PROJECT": "AlmaLinux-8",
        "ALMALINUX_MANTISBT_PROJECT_VERSION": "8.5",
    }
    expectation = {
        "os": "AlmaLinux",
        "os_family": "RedHat",
        "oscodename": "Arctic Sphynx",
        "osfullname": "AlmaLinux",
        "osrelease": "8.5",
        "osrelease_info": (8, 5),
        "osmajorrelease": 8,
        "osfinger": "AlmaLinux-8",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_endeavouros_os_grains():
    """
    Test if OS grains are parsed correctly in EndeavourOS
    """
    _os_release_data = {
        "NAME": "EndeavourOS",
        "ID": "endeavouros",
        "PRETTY_NAME": "EndeavourOS",
        "ID_LIKE": "arch",
        "BUILD_ID": "rolling",
        "ANSI_COLOR": "38;2;23;147;209",
        "HOME_URL": "https://endeavouros.com/",
        "DOCUMENTATION_URL": "https://discovery.endeavouros.com/",
        "SUPPORT_URL": "https://forums.endeavouros.com/",
        "BUG_REPORT_URL": "https://forums.endeavouros.com/c/arch-based-related-questions/bug-reports",
        "LOGO": "endeavouros",
        "IMAGE_ID": "endeavouros",
        "IMAGE_VERSION": "2022.09.10",
    }
    _os_release_map = {
        "os_release_file": {
            "NAME": "EndeavourOS",
            "VERSION_ID": "22.9",
        },
        "_linux_distribution": ("EndeavourOS", "22.9", ""),
    }

    expectation = {
        "os": "EndeavourOS",
        "os_family": "Arch",
        "oscodename": "EndeavourOS",
        "osfullname": "EndeavourOS",
        "osrelease": "22.9",
        "osrelease_info": (22, 9),
        "osmajorrelease": 22,
        "osfinger": "EndeavourOS-22",
    }
    _run_os_grains_tests(_os_release_data, _os_release_map, expectation)


@pytest.mark.skip_unless_on_linux
def test_Parrot_OS_grains():
    """
    Test if OS grains are parsed correctly in Parrot OS
    """
    # /etc/os-release data taken from ParrotOS 5.1
    _os_release_data = {
        "PRETTY_NAME": "Parrot OS 5.1 (Electro Ara)",
        "NAME": "Parrot OS",
        "VERSION_ID": "5.1",
        "VERSION": "5.1 (Electro Ara)",
        "VERSION_CODENAME": "ara",
        "ID": "parrot",
        "ID_LIKE": "debian",
        "HOME_URL": "https://www.parrotsec.org/",
        "SUPPORT_URL": "https://community.parrotsec.org/",
        "BUG_REPORT_URL": "https://community.parrotsec.org/",
    }
    _os_release_map = {
        "_linux_distribution": ("Parrot", "5.1", "Electro Ara"),
    }

    expectation = {
        "os": "Parrot OS",
        "os_family": "Debian",
        "oscodename": "ara",
        "osfullname": "Parrot OS",
        "osrelease": "5.1",
        "osrelease_info": (5, 1),
        "osmajorrelease": 5,
        "osfinger": "Parrot OS-5",
    }
    _run_os_grains_tests(_os_release_data, _os_release_map, expectation)


def test_unicode_error():
    raise_unicode_mock = MagicMock(name="raise_unicode_error", side_effect=UnicodeError)
    with patch("salt.grains.core.hostname"), patch(
        "socket.getaddrinfo", raise_unicode_mock
    ):
        ret = core.ip_fqdn()
        assert ret["fqdn_ip4"] == ret["fqdn_ip6"] == []


@pytest.mark.skip_unless_on_linux
def test_ubuntu_focal_os_grains():
    """
    Test if OS grains are parsed correctly in Ubuntu 20.04 LTS "Focal Fossa"
    """
    # /etc/os-release data taken from base-files 11ubuntu5.4
    _os_release_data = {
        "NAME": "Ubuntu",
        "VERSION": "20.04.3 LTS (Focal Fossa)",
        "ID": "ubuntu",
        "ID_LIKE": "debian",
        "PRETTY_NAME": "Ubuntu 20.04.3 LTS",
        "VERSION_ID": "20.04",
        "HOME_URL": "https://www.ubuntu.com/",
        "SUPPORT_URL": "https://help.ubuntu.com/",
        "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
        "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
        "VERSION_CODENAME": "focal",
        "UBUNTU_CODENAME": "focal",
    }
    expectation = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "focal",
        "osfullname": "Ubuntu",
        "osrelease": "20.04",
        "osrelease_info": (20, 4),
        "osmajorrelease": 20,
        "osfinger": "Ubuntu-20.04",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_ubuntu_impish_os_grains():
    """
    Test if OS grains are parsed correctly in Ubuntu 21.10 "Impish Indri"
    """
    # /etc/os-release data taken from base-files 11.1ubuntu5
    _os_release_data = {
        "PRETTY_NAME": "Ubuntu 21.10",
        "NAME": "Ubuntu",
        "VERSION_ID": "21.10",
        "VERSION": "21.10 (Impish Indri)",
        "VERSION_CODENAME": "impish",
        "ID": "ubuntu",
        "ID_LIKE": "debian",
        "HOME_URL": "https://www.ubuntu.com/",
        "SUPPORT_URL": "https://help.ubuntu.com/",
        "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
        "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
        "UBUNTU_CODENAME": "impish",
    }
    expectation = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "impish",
        "osfullname": "Ubuntu",
        "osrelease": "21.10",
        "osrelease_info": (21, 10),
        "osmajorrelease": 21,
        "osfinger": "Ubuntu-21.10",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_linux_mint_una_os_grains():
    """
    Test if OS grains are parsed correctly in Linux Mint 20.3 "Una"
    """
    # /etc/os-release data taken from base-files 20.3.0
    _os_release_data = {
        "NAME": "Linux Mint",
        "VERSION": "20.3 (Una)",
        "ID": "linuxmint",
        "ID_LIKE": "ubuntu",
        "PRETTY_NAME": "Linux Mint 20.3",
        "VERSION_ID": "20.3",
        "HOME_URL": "https://www.linuxmint.com/",
        "SUPPORT_URL": "https://forums.linuxmint.com/",
        "BUG_REPORT_URL": "http://linuxmint-troubleshooting-guide.readthedocs.io/en/latest/",
        "PRIVACY_POLICY_URL": "https://www.linuxmint.com/",
        "VERSION_CODENAME": "una",
        "UBUNTU_CODENAME": "focal",
    }
    expectation = {
        "os": "Mint",
        "os_family": "Debian",
        "oscodename": "una",
        "osfullname": "Linux Mint",
        "osrelease": "20.3",
        "osrelease_info": (20, 3),
        "osmajorrelease": 20,
        "osfinger": "Linux Mint-20",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_pop_focal_os_grains():
    """
    Test if OS grains are parsed correctly in Pop!_OS 20.04 "Focal Fossa"
    """
    # /etc/pop-os/os-release data taken from
    # pop-default-settings 4.0.6~1642047816~20.04~932caee
    _os_release_data = {
        "NAME": "Pop!_OS",
        "VERSION": "20.04 LTS",
        "ID": "pop",
        "ID_LIKE": "ubuntu debian",
        "PRETTY_NAME": "Pop!_OS 20.04 LTS",
        "VERSION_ID": "20.04",
        "HOME_URL": "https://pop.system76.com",
        "SUPPORT_URL": "https://support.system76.com",
        "BUG_REPORT_URL": "https://github.com/pop-os/pop/issues",
        "PRIVACY_POLICY_URL": "https://system76.com/privacy",
        "VERSION_CODENAME": "focal",
        "UBUNTU_CODENAME": "focal",
        "LOGO": "distributor-logo-pop-os",
    }
    expectation = {
        "os": "Pop",
        "os_family": "Debian",
        "oscodename": "focal",
        "osfullname": "Pop!_OS",
        "osrelease": "20.04",
        "osrelease_info": (20, 4),
        "osmajorrelease": 20,
        "osfinger": "Pop!_OS-20.04",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_pop_impish_os_grains():
    """
    Test if OS grains are parsed correctly in Pop!_OS 21.10 "Impish Indri"
    """
    # /etc/pop-os/os-release data taken from
    # pop-default-settings 5.1.0~1640204937~21.10~3f0be51
    _os_release_data = {
        "NAME": "Pop!_OS",
        "VERSION": "21.10",
        "ID": "pop",
        "ID_LIKE": "ubuntu debian",
        "PRETTY_NAME": "Pop!_OS 21.10",
        "VERSION_ID": "21.10",
        "HOME_URL": "https://pop.system76.com",
        "SUPPORT_URL": "https://support.system76.com",
        "BUG_REPORT_URL": "https://github.com/pop-os/pop/issues",
        "PRIVACY_POLICY_URL": "https://system76.com/privacy",
        "VERSION_CODENAME": "impish",
        "UBUNTU_CODENAME": "impish",
        "LOGO": "distributor-logo-pop-os",
    }
    expectation = {
        "os": "Pop",
        "os_family": "Debian",
        "oscodename": "impish",
        "osfullname": "Pop!_OS",
        "osrelease": "21.10",
        "osrelease_info": (21, 10),
        "osmajorrelease": 21,
        "osfinger": "Pop!_OS-21.10",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_astralinuxce_os_grains():
    """
    Test that OS grains are parsed correctly for Astra Linux Orel
    """
    # os-release data taken from astra-version 8.1.24+v2.12.43.6
    # found in pool on installer ISO downloaded from
    # https://mirrors.edge.kernel.org/astra/stable/orel/iso/orel-current.iso
    _os_release_data = {
        "PRETTY_NAME": "Astra Linux (Orel 2.12.43)",
        "NAME": "Astra Linux (Orel)",
        "ID": "astra",
        "ID_LIKE": "debian",
        "ANSI_COLOR": "1;31",
        "HOME_URL": "http://astralinux.ru",
        "SUPPORT_URL": "http://astralinux.ru/support",
        "VARIANT_ID": "orel",
        "VARIANT": "Orel",
        "LOGO": "astra",
        "VERSION_ID": "2.12.43",
        "VERSION_CODENAME": "orel",
    }
    expectation = {
        "os": "AstraLinuxCE",
        "os_family": "Debian",
        "oscodename": "orel",
        "osfullname": "Astra Linux (Orel)",
        "osrelease": "2.12.43",
        "osrelease_info": (2, 12, 43),
        "osmajorrelease": 2,
        "osfinger": "Astra Linux (Orel)-2",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_linux
def test_astralinuxse_os_grains():
    """
    Test that OS grains are parsed correctly for Astra Linux Smolensk
    """
    # /etc/os-release data taken from base-files 7.2astra2
    # from Docker image crbrka/astra16se:latest
    _os_release_data = {
        "PRETTY_NAME": "Astra Linux (Smolensk 1.6)",
        "NAME": "Astra Linux (Smolensk)",
        "ID": "astra",
        "ID_LIKE": "debian",
        "ANSI_COLOR": "1;31",
        "HOME_URL": "http://astralinux.ru",
        "SUPPORT_URL": "http://astralinux.ru/support",
        "VARIANT_ID": "smolensk",
        "VARIANT": "Smolensk",
        "VERSION_ID": "1.6",
    }
    expectation = {
        "os": "AstraLinuxSE",
        "os_family": "Debian",
        "oscodename": "smolensk",
        "osfullname": "Astra Linux (Smolensk)",
        "osrelease": "1.6",
        "osrelease_info": (1, 6),
        "osmajorrelease": 1,
        "osfinger": "Astra Linux (Smolensk)-1",
    }
    _run_os_grains_tests(_os_release_data, {}, expectation)


@pytest.mark.skip_unless_on_windows
def test_windows_platform_data():
    """
    Test the _windows_platform_data function
    """
    grains = [
        "biosversion",
        "kernelrelease",
        "kernelversion",
        "manufacturer",
        "motherboard",
        "osfullname",
        "osmanufacturer",
        "osrelease",
        "osservicepack",
        "osversion",
        "productname",
        "serialnumber",
        "timezone",
        # "virtual", <-- only present on VMs
        "windowsdomain",
        "windowsdomaintype",
    ]
    returned_grains = core._windows_platform_data()
    for grain in grains:
        assert grain in returned_grains

    valid_types = ["Unknown", "Unjoined", "Workgroup", "Domain"]
    assert returned_grains["windowsdomaintype"] in valid_types
    valid_releases = [
        "Vista",
        "7",
        "8",
        "8.1",
        "10",
        "11",
        "2008Server",
        "2008ServerR2",
        "2012Server",
        "2012ServerR2",
        "2016Server",
        "2019Server",
        "2022Server",
    ]
    assert returned_grains["osrelease"] in valid_releases


def test__windows_os_release_grain(subtests):
    versions = {
        "Windows 10 Home": "10",
        "Windows 10 Pro": "10",
        "Windows 10 Pro for Workstations": "10",
        "Windows 10 Pro Education": "10",
        "Windows 10 Enterprise": "10",
        "Windows 10 Enterprise LTSB": "10",
        "Windows 10 Education": "10",
        "Windows 10 IoT Core": "10",
        "Windows 10 IoT Enterprise": "10",
        "Windows 10 S": "10",
        "Windows 8.1": "8.1",
        "Windows 8.1 Pro": "8.1",
        "Windows 8.1 Enterprise": "8.1",
        "Windows 8.1 OEM": "8.1",
        "Windows 8.1 with Bing": "8.1",
        "Windows 8": "8",
        "Windows 8 Pro": "8",
        "Windows 8 Enterprise": "8",
        "Windows 8 OEM": "8",
        "Windows 7 Starter": "7",
        "Windows 7 Home Basic": "7",
        "Windows 7 Home Premium": "7",
        "Windows 7 Professional": "7",
        "Windows 7 Enterprise": "7",
        "Windows 7 Ultimate": "7",
        "Windows Thin PC": "Thin",
        "Windows Vista Starter": "Vista",
        "Windows Vista Home Basic": "Vista",
        "Windows Vista Home Premium": "Vista",
        "Windows Vista Business": "Vista",
        "Windows Vista Enterprise": "Vista",
        "Windows Vista Ultimate": "Vista",
        "Windows Server 2019 Essentials": "2019Server",
        "Windows Server 2019 Standard": "2019Server",
        "Windows Server 2019 Datacenter": "2019Server",
        "Windows Server 2016 Essentials": "2016Server",
        "Windows Server 2016 Standard": "2016Server",
        "Windows Server 2016 Datacenter": "2016Server",
        "Windows Server 2012 R2 Foundation": "2012ServerR2",
        "Windows Server 2012 R2 Essentials": "2012ServerR2",
        "Windows Server 2012 R2 Standard": "2012ServerR2",
        "Windows Server 2012 R2 Datacenter": "2012ServerR2",
        "Windows Server 2012 Foundation": "2012Server",
        "Windows Server 2012 Essentials": "2012Server",
        "Windows Server 2012 Standard": "2012Server",
        "Windows Server 2012 Datacenter": "2012Server",
        "Windows MultiPoint Server 2012": "2012Server",
        "Windows Small Business Server 2011": "2011Server",
        "Windows MultiPoint Server 2011": "2011Server",
        "Windows Home Server 2011": "2011Server",
        "Windows MultiPoint Server 2010": "2010Server",
        "Windows Server 2008 R2 Foundation": "2008ServerR2",
        "Windows Server 2008 R2 Standard": "2008ServerR2",
        "Windows Server 2008 R2 Enterprise": "2008ServerR2",
        "Windows Server 2008 R2 Datacenter": "2008ServerR2",
        "Windows Server 2008 R2 for Itanium-based Systems": "2008ServerR2",
        "Windows Web Server 2008 R2": "2008ServerR2",
        "Windows Storage Server 2008 R2": "2008ServerR2",
        "Windows HPC Server 2008 R2": "2008ServerR2",
        "Windows Server 2008 Standard": "2008Server",
        "Windows Server 2008 Enterprise": "2008Server",
        "Windows Server 2008 Datacenter": "2008Server",
        "Windows Server 2008 for Itanium-based Systems": "2008Server",
        "Windows Server Foundation 2008": "2008Server",
        "Windows Essential Business Server 2008": "2008Server",
        "Windows HPC Server 2008": "2008Server",
        "Windows Small Business Server 2008": "2008Server",
        "Windows Storage Server 2008": "2008Server",
        "Windows Web Server 2008": "2008Server",
    }
    for caption, expected_version in versions.items():
        with subtests.test(caption):
            version = core._windows_os_release_grain(caption, 1)
            assert version == expected_version

    embedded_versions = {
        "Windows Embedded 8.1 Industry Pro": "8.1",
        "Windows Embedded 8 Industry Pro": "8",
        "Windows POSReady 7": "7",
        "Windows Embedded Standard 7": "7",
        "Windows Embedded POSReady 2009": "2009",
        "Windows Embedded Standard 2009": "2009",
        "Windows XP Embedded": "XP",
    }
    for caption, expected_version in embedded_versions.items():
        with subtests.test(caption):
            version = core._windows_os_release_grain(caption, 1)
            assert version == expected_version

    # Special Cases
    # Windows Embedded Standard is Windows 7
    caption = "Windows Embedded Standard"
    with subtests.test(caption):
        with patch("platform.release", MagicMock(return_value="7")):
            version = core._windows_os_release_grain(caption, 1)
            assert version == "7"

    # Microsoft Hyper-V Server 2019
    # Issue https://github.com/saltstack/salt/issue/55212
    caption = "Microsoft Hyper-V Server"
    with subtests.test(caption):
        version = core._windows_os_release_grain(caption, 1)
        assert version == "2019Server"

    # Microsoft Windows Server Datacenter
    # Issue https://github.com/saltstack/salt/issue/59611
    caption = "Microsoft Windows Server Datacenter"
    with subtests.test(caption):
        version = core._windows_os_release_grain(caption, 1)
        assert version == "2019Server"


@pytest.mark.skip_unless_on_linux
def test_linux_memdata():
    """
    Test memdata on Linux systems
    """
    _proc_meminfo = textwrap.dedent(
        """\
        MemTotal:       16277028 kB
        SwapTotal:       4789244 kB"""
    )
    with patch("salt.utils.files.fopen", mock_open(read_data=_proc_meminfo)):
        memdata = core._linux_memdata()
    assert memdata.get("mem_total") == 15895
    assert memdata.get("swap_total") == 4676


@pytest.mark.skip_on_windows
def test_bsd_memdata():
    """
    Test to memdata on *BSD systems
    """
    _path_exists_map = {}
    _cmd_run_map = {
        "freebsd-version -u": "10.3-RELEASE",
        "/sbin/sysctl -n hw.physmem": "2121781248",
        "/sbin/sysctl -n vm.swap_total": "419430400",
    }

    path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
    cmd_run_mock = MagicMock(side_effect=lambda x: _cmd_run_map[x])
    empty_mock = MagicMock(return_value={})

    nt_uname = namedtuple(
        "nt_uname", ["system", "node", "release", "version", "machine", "processor"]
    )
    mock_freebsd_uname = MagicMock(
        return_value=nt_uname(
            "FreeBSD",
            "freebsd10.3-hostname-8148",
            "10.3-RELEASE",
            "FreeBSD 10.3-RELEASE #0 r297264: Fri Mar 25 02:10:02 UTC 2016     root@releng1.nyi.freebsd.org:/usr/obj/usr/src/sys/GENERIC",
            "amd64",
            "amd64",
        )
    )
    with patch.object(platform, "uname", mock_freebsd_uname), patch.object(
        salt.utils.platform, "is_linux", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.platform, "is_freebsd", MagicMock(return_value=True)
    ), patch.object(
        # Skip the first if statement
        salt.utils.platform,
        "is_proxy",
        MagicMock(return_value=False),
    ), patch.object(
        # Skip the init grain compilation (not pertinent)
        os.path,
        "exists",
        path_exists_mock,
    ), patch(
        "salt.utils.path.which", return_value="/sbin/sysctl"
    ):
        # Make a bunch of functions return empty dicts,
        # we don't care about these grains for the
        # purposes of this test.
        with patch.object(core, "_bsd_cpudata", empty_mock), patch.object(
            core, "_hw_data", empty_mock
        ), patch.object(core, "_virtual", empty_mock), patch.object(
            core, "_ps", empty_mock
        ), patch.dict(
            # Mock the osarch
            core.__salt__,
            {"cmd.run": cmd_run_mock},
        ):
            os_grains = core.os_data()

    assert os_grains.get("mem_total") == 2023
    assert os_grains.get("swap_total") == 400


@pytest.mark.skip_on_windows
@pytest.mark.parametrize(
    "cgroup_substr",
    (
        ":/system.slice/docker",
        ":/docker/",
        ":/docker-ce/",
    ),
)
def test_docker_virtual(cgroup_substr):
    """
    Test if virtual grains are parsed correctly in Docker.
    """
    cgroup_data = "10:memory{}a_long_sha256sum".format(cgroup_substr)
    log.debug("Testing Docker cgroup substring '%s'", cgroup_substr)
    with patch.object(os.path, "isdir", MagicMock(return_value=False)), patch.object(
        os.path,
        "isfile",
        MagicMock(side_effect=lambda x: True if x == "/proc/1/cgroup" else False),
    ), patch("salt.utils.files.fopen", mock_open(read_data=cgroup_data)), patch.dict(
        core.__salt__, {"cmd.run_all": MagicMock()}
    ):
        grains = core._virtual({"kernel": "Linux"})
        assert grains.get("virtual_subtype") == "Docker"
        assert grains.get("virtual") == "container"


@pytest.mark.skip_on_windows
def test_lxc_virtual():
    """
    Test if virtual grains are parsed correctly in LXC.
    """
    cgroup_data = "10:memory:/lxc/a_long_sha256sum"
    with patch.object(os.path, "isdir", MagicMock(return_value=False)), patch.object(
        os.path,
        "isfile",
        MagicMock(side_effect=lambda x: True if x == "/proc/1/cgroup" else False),
    ), patch("salt.utils.files.fopen", mock_open(read_data=cgroup_data)), patch.dict(
        core.__salt__, {"cmd.run_all": MagicMock()}
    ):
        grains = core._virtual({"kernel": "Linux"})
        assert grains.get("virtual_subtype") == "LXC"
        assert grains.get("virtual") == "container"

    file_contents = {
        "/proc/1/cgroup": "10:memory",
        "/proc/1/environ": "container=lxc",
    }
    with patch.object(os.path, "isdir", MagicMock(return_value=False)), patch.object(
        os.path,
        "isfile",
        MagicMock(
            side_effect=lambda x: True
            if x in ("/proc/1/cgroup", "/proc/1/environ")
            else False
        ),
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_contents)), patch.dict(
        core.__salt__, {"cmd.run_all": MagicMock()}
    ):
        grains = core._virtual({"kernel": "Linux"})
        assert grains.get("virtual_subtype") == "LXC"
        assert grains.get("virtual") == "container"


@pytest.mark.skip_on_windows
def test_lxc_virtual_with_virt_what():
    """
    Test if virtual grains are parsed correctly in LXC using virt-what.
    """
    virt = "lxc\nkvm"
    with patch.object(
        salt.utils.platform, "is_windows", MagicMock(return_value=False)
    ), patch.object(salt.utils.path, "which", MagicMock(return_value=True)), patch.dict(
        core.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"pid": 78, "retcode": 0, "stderr": "", "stdout": virt}
            )
        },
    ):
        osdata = {"kernel": "test"}
        ret = core._virtual(osdata)
        assert ret["virtual"] == "container"
        assert ret["virtual_subtype"] == "LXC"


@pytest.mark.skip_on_windows
def test_container_inside_virtual_machine():
    """
    Test if a container inside an hypervisor is shown as a container
    """
    file_contents = {
        "/proc/cpuinfo": "QEMU Virtual CPU",
        "/proc/1/cgroup": "10:memory",
        "/proc/1/environ": "container=lxc",
    }
    with patch.object(os.path, "isdir", MagicMock(return_value=False)), patch.object(
        os.path,
        "isfile",
        MagicMock(
            side_effect=lambda x: True
            if x in ("/proc/cpuinfo", "/proc/1/cgroup", "/proc/1/environ")
            else False
        ),
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_contents)), patch.dict(
        core.__salt__, {"cmd.run_all": MagicMock()}
    ):
        grains = core._virtual({"kernel": "Linux"})
        assert grains.get("virtual_subtype") == "LXC"
        assert grains.get("virtual") == "container"


@pytest.mark.skip_unless_on_linux
def test_xen_virtual():
    """
    Test if OS grains are parsed correctly for Xen hypervisors
    """
    with patch.multiple(
        os.path,
        isdir=MagicMock(
            side_effect=lambda x: x
            in ["/sys/bus/xen", "/sys/bus/xen/drivers/xenconsole"]
        ),
    ), patch.dict(core.__salt__, {"cmd.run": MagicMock(return_value="")}), patch.dict(
        core.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""})},
    ), patch.object(
        os.path,
        "isfile",
        MagicMock(side_effect=lambda x: True if x == "/proc/1/cgroup" else False),
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data="")
    ):
        assert (
            core._virtual({"kernel": "Linux"}).get("virtual_subtype") == "Xen PV DomU"
        )


@pytest.mark.skip_on_windows
def test_illumos_virtual():
    """
    Test if virtual grains are parsed correctly inside illumos/solaris zone
    """

    def _cmd_side_effect(cmd):
        if cmd == "/usr/bin/zonename":
            # NOTE: we return the name of the zone
            return "myzone"
        mylogdebug = "cmd.run_all: '{}'".format(cmd)
        log.debug(mylogdebug)

    def _cmd_all_side_effect(cmd):
        # NOTE: prtdiag doesn't work inside a zone
        #       so we return the expected result
        if cmd == "/usr/sbin/prtdiag ":
            return {
                "pid": 32208,
                "retcode": 1,
                "stdout": "",
                "stderr": "prtdiag can only be run in the global zone",
            }
        log.debug("cmd.run_all: '%s'", cmd)

    def _which_side_effect(path):
        if path == "prtdiag":
            return "/usr/sbin/prtdiag"
        elif path == "zonename":
            return "/usr/bin/zonename"
        return None

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": MagicMock(side_effect=_cmd_side_effect),
            "cmd.run_all": MagicMock(side_effect=_cmd_all_side_effect),
        },
    ), patch("salt.utils.path.which", MagicMock(side_effect=_which_side_effect)):
        grains = core._virtual({"kernel": "SunOS"})
        assert grains.get("virtual") == "zone"


@pytest.mark.skip_on_windows
def test_illumos_fallback_virtual():
    """
    Test if virtual grains are parsed correctly inside illumos/solaris zone
    """

    def _cmd_all_side_effect(cmd):
        # NOTE: prtdiag doesn't work inside a zone
        #       so we return the expected result
        if cmd == "/usr/sbin/prtdiag ":
            return {
                "pid": 32208,
                "retcode": 1,
                "stdout": "",
                "stderr": "prtdiag can only be run in the global zone",
            }
        log.debug("cmd.run_all: '%s'", cmd)

    def _which_side_effect(path):
        if path == "prtdiag":
            return "/usr/sbin/prtdiag"
        return None

    def _isdir_side_effect(path):
        if path == "/.SUNWnative":
            return True
        return False

    with patch.dict(
        core.__salt__,
        {"cmd.run_all": MagicMock(side_effect=_cmd_all_side_effect)},
    ), patch("salt.utils.path.which", MagicMock(side_effect=_which_side_effect)), patch(
        "os.path.isdir", MagicMock(side_effect=_isdir_side_effect)
    ):
        grains = core._virtual({"kernel": "SunOS"})
        assert grains.get("virtual") == "zone"


def test_if_virtual_subtype_exists_virtual_should_fallback_to_virtual():
    def mockstat(path):
        if path == "/":
            return "fnord"
        elif path == "/proc/1/root/.":
            return "roscivs"
        return None

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": MagicMock(return_value=""),
            "cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""}),
        },
    ), patch.multiple(
        os.path,
        isfile=MagicMock(return_value=False),
        isdir=MagicMock(side_effect=lambda x: x == "/proc"),
    ), patch.multiple(
        os,
        stat=MagicMock(side_effect=mockstat),
    ):
        grains = core._virtual({"kernel": "Linux"})
        assert grains.get("virtual_subtype") is not None
        assert grains.get("virtual") == "virtual"


def _check_ipaddress(value, ip_v):
    """
    check if ip address in a list is valid
    """
    for val in value:
        assert isinstance(val, str)
        ip_method = "is_ipv{}".format(ip_v)
        assert getattr(salt.utils.network, ip_method)(val)


def _check_empty(key, value, empty):
    """
    if empty is False and value does not exist assert error
    if empty is True and value exists assert error
    """
    if not empty and not value:
        raise Exception("{} is empty, expecting a value".format(key))
    elif empty and value:
        raise Exception(
            "{} is suppose to be empty. value: {} exists".format(key, value)
        )


def _check_ip_fqdn_set(value, empty, _set=None):
    if empty:
        assert len(value) == 0
    else:
        assert sorted(value) == sorted(_set)


@pytest.mark.skip_unless_on_linux
def test_fqdn_return(ipv4_tuple, ipv6_tuple):
    """
    test ip4 and ip6 return values
    """
    ipv4_local, ipv4_addr1, ipv4_addr2 = ipv4_tuple
    ipv6_local, ipv6_addr1, ipv6_addr2, _ = ipv6_tuple

    net_ip4_mock = [ipv4_local, ipv4_addr1, ipv4_addr2]
    net_ip6_mock = [ipv6_local, ipv6_addr1, ipv6_addr2]

    _run_fqdn_tests(
        ipv4_tuple,
        ipv6_tuple,
        net_ip4_mock,
        net_ip6_mock,
        ip4_empty=False,
        ip6_empty=False,
    )


@pytest.mark.skip_unless_on_linux
def test_fqdn6_empty(ipv4_tuple, ipv6_tuple):
    """
    test when ip6 is empty
    """
    ipv4_local, ipv4_addr1, ipv4_addr2 = ipv4_tuple
    net_ip4_mock = [ipv4_local, ipv4_addr1, ipv4_addr2]
    net_ip6_mock = []

    _run_fqdn_tests(ipv4_tuple, ipv6_tuple, net_ip4_mock, net_ip6_mock, ip4_empty=False)


@pytest.mark.skip_unless_on_linux
def test_fqdn4_empty(ipv4_tuple, ipv6_tuple):
    """
    test when ip4 is empty
    """
    ipv6_local, ipv6_addr1, ipv6_addr2, _ = ipv6_tuple
    net_ip4_mock = []
    net_ip6_mock = [ipv6_local, ipv6_addr1, ipv6_addr2]

    _run_fqdn_tests(ipv4_tuple, ipv6_tuple, net_ip4_mock, net_ip6_mock, ip6_empty=False)


@pytest.mark.skip_unless_on_linux
def test_fqdn_all_empty(ipv4_tuple, ipv6_tuple):
    """
    test when both ip4 and ip6 are empty
    """
    net_ip4_mock = []
    net_ip6_mock = []

    _run_fqdn_tests(ipv4_tuple, ipv6_tuple, net_ip4_mock, net_ip6_mock)


def _run_fqdn_tests(
    ipv4_tuple, ipv6_tuple, net_ip4_mock, net_ip6_mock, ip6_empty=True, ip4_empty=True
):
    _, ipv4_addr1, ipv4_addr2 = ipv4_tuple
    _, ipv6_addr1, ipv6_addr2, _ = ipv6_tuple

    ipv4_mock = [
        (2, 1, 6, "", (ipv4_addr1, 0)),
        (2, 2, 17, "", (ipv4_addr1, 0)),
        (2, 3, 0, "", (ipv4_addr1, 0)),
        (2, 3, 0, "", (ipv4_addr2, 0)),
        (2, 1, 6, "", (ipv4_addr2, 0)),
        (2, 2, 17, "", (ipv4_addr2, 0)),
    ]

    ipv6_mock = [
        (10, 1, 6, "", (ipv6_addr1, 0, 0, 0)),
        (10, 2, 17, "", (ipv6_addr1, 0, 0, 0)),
        (10, 3, 0, "", (ipv6_addr1, 0, 0, 0)),
        (10, 1, 6, "", (ipv6_addr2, 0, 0, 0)),
        (10, 2, 17, "", (ipv6_addr2, 0, 0, 0)),
        (10, 3, 0, "", (ipv6_addr2, 0, 0, 0)),
    ]

    def _getaddrinfo(fqdn, port, family=0, *args, **kwargs):
        if not ip4_empty and family == socket.AF_INET:
            return ipv4_mock
        elif not ip6_empty and family == socket.AF_INET6:
            return ipv6_mock
        else:
            return []

    def _check_type(key, value, ip4_empty, ip6_empty):
        """
        check type and other checks
        """
        assert isinstance(value, list)

        if "4" in key:
            _check_empty(key, value, ip4_empty)
            _check_ipaddress(value, ip_v="4")
        elif "6" in key:
            _check_empty(key, value, ip6_empty)
            _check_ipaddress(value, ip_v="6")

    with patch.object(
        salt.utils.network, "ip_addrs", MagicMock(return_value=net_ip4_mock)
    ), patch.object(
        salt.utils.network, "ip_addrs6", MagicMock(return_value=net_ip6_mock)
    ), patch.object(
        core.socket, "getaddrinfo", side_effect=_getaddrinfo
    ):
        get_fqdn = core.ip_fqdn()
        ret_keys = ["fqdn_ip4", "fqdn_ip6", "ipv4", "ipv6"]
        for key in ret_keys:
            value = get_fqdn[key]
            _check_type(key, value, ip4_empty, ip6_empty)
            if key.startswith("fqdn_ip"):
                if key.endswith("4"):
                    _check_ip_fqdn_set(value, ip4_empty, _set=[ipv4_addr1, ipv4_addr2])
                if key.endswith("6"):
                    _check_ip_fqdn_set(value, ip6_empty, _set=[ipv6_addr1, ipv6_addr2])


@pytest.mark.skip_unless_on_linux
def test_dns_return(ipv4_tuple, ipv6_tuple):
    """
    test the return for a dns grain. test for issue:
    https://github.com/saltstack/salt/issues/41230
    """
    _, ipv4_addr1, _ = ipv4_tuple
    _, ipv6_addr1, _, ipv6_add_scope = ipv6_tuple

    resolv_mock = {
        "domain": "",
        "sortlist": [],
        "nameservers": [
            ipaddress.IPv4Address(ipv4_addr1),
            ipaddress.IPv6Address(ipv6_addr1),
            ipv6_add_scope,
        ],
        "ip4_nameservers": [ipaddress.IPv4Address(ipv4_addr1)],
        "search": ["test.saltstack.com"],
        "ip6_nameservers": [ipaddress.IPv6Address(ipv6_addr1), ipv6_add_scope],
        "options": [],
    }
    ret = {
        "dns": {
            "domain": "",
            "sortlist": [],
            "nameservers": [ipv4_addr1, ipv6_addr1, ipv6_add_scope],
            "ip4_nameservers": [ipv4_addr1],
            "search": ["test.saltstack.com"],
            "ip6_nameservers": [ipv6_addr1, ipv6_add_scope],
            "options": [],
        }
    }
    with patch.object(
        salt.utils.platform, "is_windows", MagicMock(return_value=False)
    ), patch("salt.grains.core.__opts__", {"ipv6": False}):
        with patch.object(
            salt.utils.dns, "parse_resolv", MagicMock(return_value=resolv_mock)
        ):
            assert core.dns() == ret

        with patch("os.path.exists", return_value=True), patch.object(
            salt.utils.dns, "parse_resolv", MagicMock(return_value=resolv_mock)
        ):
            assert core.dns() == ret


def test_enable_fqdns_false():
    """
    tests enable_fqdns_grains is set to False
    """
    with patch.dict("salt.grains.core.__opts__", {"enable_fqdns_grains": False}):
        assert core.fqdns() == {"fqdns": []}


def test_enable_fqdns_true():
    """
    testing that grains uses network.fqdns module
    """
    with patch.dict(
        "salt.grains.core.__salt__",
        {"network.fqdns": MagicMock(return_value="my.fake.domain")},
    ), patch.dict("salt.grains.core.__opts__", {"enable_fqdns_grains": True}):
        assert core.fqdns() == "my.fake.domain"


def test_enable_fqdns_none():
    """
    testing default fqdns grains is returned when enable_fqdns_grains is None
    """
    with patch.dict("salt.grains.core.__opts__", {"enable_fqdns_grains": None}):
        assert core.fqdns() == {"fqdns": []}


def test_enable_fqdns_without_patching():
    """
    testing fqdns grains is enabled by default
    """
    with patch.dict(
        "salt.grains.core.__salt__",
        {"network.fqdns": MagicMock(return_value="my.fake.domain")},
    ):
        # fqdns is disabled by default on Windows and macOS
        if salt.utils.platform.is_windows() or salt.utils.platform.is_darwin():
            assert core.fqdns() == {"fqdns": []}
        else:
            assert core.fqdns() == "my.fake.domain"


def test_enable_fqdns_false_is_proxy():
    """
    testing fqdns grains is disabled by default for proxy minions
    """
    with patch(
        "salt.utils.platform.is_proxy", return_value=True, autospec=True
    ), patch.dict(
        "salt.grains.core.__salt__",
        {"network.fqdns": MagicMock(return_value="my.fake.domain")},
    ):
        # fqdns is disabled by default on proxy minions
        assert core.fqdns() == {"fqdns": []}


def test_enable_fqdns_false_is_aix():
    """
    testing fqdns grains is disabled by default for minions on AIX
    """
    with patch(
        "salt.utils.platform.is_aix", return_value=True, autospec=True
    ), patch.dict(
        "salt.grains.core.__salt__",
        {"network.fqdns": MagicMock(return_value="my.fake.domain")},
    ):
        # fqdns is disabled by default on minions on AIX
        assert core.fqdns() == {"fqdns": []}


def test_enable_fqdns_false_is_sunos():
    """
    testing fqdns grains is disabled by default for minions on Solaris platforms
    """
    with patch(
        "salt.utils.platform.is_sunos", return_value=True, autospec=True
    ), patch.dict(
        "salt.grains.core.__salt__",
        {"network.fqdns": MagicMock(return_value="my.fake.domain")},
    ):
        # fqdns is disabled by default on minions on Solaris platforms
        assert core.fqdns() == {"fqdns": []}


def test_enable_fqdns_false_is_junos():
    """
    testing fqdns grains is disabled by default for minions on Junos
    """
    with patch(
        "salt.utils.platform.is_junos", return_value=True, autospec=True
    ), patch.dict(
        "salt.grains.core.__salt__",
        {"network.fqdns": MagicMock(return_value="my.fake.domain")},
    ):
        # fqdns is disabled by default on minions on Junos (Juniper)
        assert core.fqdns() == {"fqdns": []}


@pytest.mark.skip_unless_on_linux
def test_fqdns_return():
    """
    test the return for a dns grain. test for issue:
    https://github.com/saltstack/salt/issues/41230
    """
    reverse_resolv_mock = [
        ("foo.bar.baz", [], ["1.2.3.4"]),
        ("rinzler.evil-corp.com", [], ["5.6.7.8"]),
        ("foo.bar.baz", [], ["fe80::a8b2:93ff:fe00:0"]),
        ("bluesniff.foo.bar", [], ["fe80::a8b2:93ff:dead:beef"]),
    ]
    ret = {"fqdns": ["bluesniff.foo.bar", "foo.bar.baz", "rinzler.evil-corp.com"]}
    with patch(
        "salt.utils.network.ip_addrs", MagicMock(return_value=["1.2.3.4", "5.6.7.8"])
    ), patch(
        "salt.utils.network.ip_addrs6",
        MagicMock(return_value=["fe80::a8b2:93ff:fe00:0", "fe80::a8b2:93ff:dead:beef"]),
    ), patch(
        # Just pass-through
        "salt.utils.network.socket.getfqdn",
        MagicMock(side_effect=lambda v: v),
    ), patch.dict(
        core.__salt__, {"network.fqdns": salt.modules.network.fqdns}
    ), patch.object(
        socket, "gethostbyaddr", side_effect=reverse_resolv_mock
    ):
        fqdns = core.fqdns()
        assert "fqdns" in fqdns
        assert len(fqdns["fqdns"]) == len(ret["fqdns"])
        assert set(fqdns["fqdns"]) == set(ret["fqdns"])


@pytest.mark.skip_unless_on_linux
def test_fqdns_socket_error(caplog):
    """
    test the behavior on non-critical socket errors of the dns grain
    """

    def _gen_gethostbyaddr(errno):
        def _gethostbyaddr(_):
            herror = socket.herror()
            herror.errno = errno
            raise herror

        return _gethostbyaddr

    with patch(
        "salt.utils.network.ip_addrs", MagicMock(return_value=["1.2.3.4"])
    ), patch("salt.utils.network.ip_addrs6", MagicMock(return_value=[])):
        for errno in (0, core.HOST_NOT_FOUND, core.NO_DATA):
            mock_log = MagicMock()
            with patch.dict(
                core.__salt__, {"network.fqdns": salt.modules.network.fqdns}
            ), patch.object(
                socket, "gethostbyaddr", side_effect=_gen_gethostbyaddr(errno)
            ), patch(
                "salt.modules.network.log", mock_log
            ):
                assert core.fqdns() == {"fqdns": []}
                mock_log.debug.assert_called()
                mock_log.error.assert_not_called()

        caplog.set_level(logging.WARNING)
        with patch.dict(
            core.__salt__, {"network.fqdns": salt.modules.network.fqdns}
        ), patch.object(socket, "gethostbyaddr", side_effect=_gen_gethostbyaddr(-1)):
            assert core.fqdns() == {"fqdns": []}
        assert "Failed to resolve address 1.2.3.4:" in caplog.text


def test_core_virtual():
    """
    test virtual grain with cmd virt-what
    """
    virt = "kvm"
    with patch.object(
        salt.utils.platform, "is_windows", MagicMock(return_value=False)
    ), patch.object(salt.utils.path, "which", MagicMock(return_value=True)), patch.dict(
        core.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"pid": 78, "retcode": 0, "stderr": "", "stdout": virt}
            )
        },
    ):
        osdata = {"kernel": "test"}
        ret = core._virtual(osdata)
        assert ret["virtual"] == virt

        with patch.dict(
            core.__salt__,
            {
                "cmd.run_all": MagicMock(
                    return_value={
                        "pid": 78,
                        "retcode": 0,
                        "stderr": "",
                        "stdout": "\n\n{}".format(virt),
                    }
                )
            },
        ):
            osdata = {"kernel": "test"}
            ret = core._virtual(osdata)
            assert ret["virtual"] == virt


def test_solaris_sparc_s7zone(os_release_dir, solaris_dir):
    """
    verify productname grain for s7 zone
    """
    expectation = {
        "productname": "SPARC S7-2",
        "product": "SPARC S7-2",
        "manufacturer": "Oracle Corporation",
    }
    with salt.utils.files.fopen(
        str(solaris_dir / "prtconf.s7-zone")
    ) as sparc_return_data:
        this_sparc_return_data = "\n".join(sparc_return_data.readlines())
        this_sparc_return_data += "\n"
    _check_solaris_sparc_productname_grains(
        os_release_dir, this_sparc_return_data, expectation
    )


def test_solaris_sparc_s7(os_release_dir, solaris_dir):
    """
    verify productname grain for s7
    """
    expectation = {
        "productname": "SPARC S7-2",
        "product": "SPARC S7-2",
        "manufacturer": "Oracle Corporation",
    }
    with salt.utils.files.fopen(str(solaris_dir / "prtdiag.s7")) as sparc_return_data:
        this_sparc_return_data = "\n".join(sparc_return_data.readlines())
        this_sparc_return_data += "\n"
    _check_solaris_sparc_productname_grains(
        os_release_dir, this_sparc_return_data, expectation
    )


def test_solaris_sparc_t5220(os_release_dir, solaris_dir):
    """
    verify productname grain for t5220
    """
    expectation = {
        "productname": "SPARC Enterprise T5220",
        "product": "SPARC Enterprise T5220",
        "manufacturer": "Oracle Corporation",
    }
    with salt.utils.files.fopen(
        str(solaris_dir / "prtdiag.t5220")
    ) as sparc_return_data:
        this_sparc_return_data = "\n".join(sparc_return_data.readlines())
        this_sparc_return_data += "\n"
    _check_solaris_sparc_productname_grains(
        os_release_dir, this_sparc_return_data, expectation
    )


def test_solaris_sparc_t5220zone(os_release_dir, solaris_dir):
    """
    verify productname grain for t5220 zone
    """
    expectation = {
        "productname": "SPARC Enterprise T5220",
        "product": "SPARC Enterprise T5220",
        "manufacturer": "Oracle Corporation",
    }
    with salt.utils.files.fopen(
        str(solaris_dir / "prtconf.t5220-zone")
    ) as sparc_return_data:
        this_sparc_return_data = "\n".join(sparc_return_data.readlines())
        this_sparc_return_data += "\n"
    _check_solaris_sparc_productname_grains(
        os_release_dir, this_sparc_return_data, expectation
    )


def _check_solaris_sparc_productname_grains(os_release_dir, prtdata, expectation):
    """
    verify product grains on solaris sparc
    """

    path_isfile_mock = MagicMock(side_effect=lambda x: x in ["/etc/release"])
    with salt.utils.files.fopen(
        str(os_release_dir / "solaris-11.3")
    ) as os_release_file:
        os_release_content = os_release_file.readlines()
    uname_mock = MagicMock(
        return_value=("SunOS", "testsystem", "5.11", "11.3", "sunv4", "sparc")
    )
    with patch.object(platform, "uname", uname_mock), patch.object(
        salt.utils.platform, "is_proxy", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.platform, "is_linux", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.platform, "is_windows", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.platform, "is_smartos", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.path, "which_bin", MagicMock(return_value=None)
    ), patch.object(
        os.path, "isfile", path_isfile_mock
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=os_release_content)
    ) as os_release_file, patch.object(
        core,
        "_sunos_cpudata",
        MagicMock(
            return_value={
                "cpuarch": "sparcv9",
                "num_cpus": "1",
                "cpu_model": "MOCK_CPU_MODEL",
                "cpu_flags": [],
            }
        ),
    ), patch.object(
        core, "_memdata", MagicMock(return_value={"mem_total": 16384})
    ), patch.object(
        core, "_virtual", MagicMock(return_value={})
    ), patch.object(
        core, "_ps", MagicMock(return_value={})
    ), patch.object(
        salt.utils.path, "which", MagicMock(return_value=True)
    ), patch.dict(
        core.__salt__, {"cmd.run": MagicMock(return_value=prtdata)}
    ):
        os_grains = core.os_data()
    grains = {
        k: v
        for k, v in os_grains.items()
        if k in {"product", "productname", "manufacturer"}
    }
    assert grains == expectation


def test_core_virtual_unicode():
    """
    test virtual grain with unicode character in product_name file
    """

    def path_side_effect(path):
        if path == "/sys/devices/virtual/dmi/id/product_name":
            return True
        return False

    virt = "kvm"
    with patch("os.path.isfile", side_effect=path_side_effect), patch(
        "os.path.isdir", side_effect=path_side_effect
    ), patch.object(
        salt.utils.platform, "is_windows", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.path, "which", MagicMock(return_value=True)
    ), patch.dict(
        core.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"pid": 78, "retcode": 0, "stderr": "", "stdout": virt}
            )
        },
    ), patch(
        "salt.utils.files.fopen",
        mock_open(read_data="嗨".encode()),
    ):
        osdata = {
            "kernel": "Linux",
        }
        osdata = {
            "kernel": "Linux",
        }
        ret = core._virtual(osdata)
        assert ret["virtual"] == virt


def test_core_virtual_invalid():
    """
    test virtual grain with an invalid unicode character in product_name file
    """

    def path_side_effect(path):
        if path == "/sys/devices/virtual/dmi/id/product_name":
            return True
        return False

    virt = "kvm"
    with patch("os.path.isfile", side_effect=path_side_effect), patch(
        "os.path.isdir", side_effect=path_side_effect
    ), patch.object(
        salt.utils.platform, "is_windows", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.path, "which", MagicMock(return_value=True)
    ), patch.dict(
        core.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"pid": 78, "retcode": 0, "stderr": "", "stdout": virt}
            )
        },
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=b"\xff")
    ):
        osdata = {"kernel": "Linux"}
        ret = core._virtual(osdata)
        assert ret["virtual"] == virt


def test_osx_memdata_with_comma():
    """
    test osx memdata method when comma returns
    """

    def _cmd_side_effect(cmd):
        if "hw.memsize" in cmd:
            return "4294967296"
        elif "vm.swapusage" in cmd:
            return "total = 1024,00M  used = 160,75M  free = 863,25M  (encrypted)"

    with patch.dict(
        core.__salt__, {"cmd.run": MagicMock(side_effect=_cmd_side_effect)}
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/sysctl")):
        ret = core._osx_memdata()
        assert ret["swap_total"] == 1024
        assert ret["mem_total"] == 4096


def test_osx_memdata():
    """
    test osx memdata
    """

    def _cmd_side_effect(cmd):
        if "hw.memsize" in cmd:
            return "4294967296"
        elif "vm.swapusage" in cmd:
            return "total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)"

    with patch.dict(
        core.__salt__, {"cmd.run": MagicMock(side_effect=_cmd_side_effect)}
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/sysctl")):
        ret = core._osx_memdata()
        assert ret["swap_total"] == 0
        assert ret["mem_total"] == 4096


@pytest.mark.skipif(not core._DATEUTIL_TZ, reason="Missing dateutil.tz")
def test_locale_info_tzname():
    # mock datetime.now().tzname()
    # cant just mock now because it is read only
    tzname = Mock(return_value="MDT_FAKE")
    now_ret_object = Mock(tzname=tzname)
    now = Mock(return_value=now_ret_object)
    datetime = Mock(now=now)

    with patch.object(
        core, "datetime", datetime=datetime
    ) as datetime_module, patch.object(
        core.dateutil.tz, "tzlocal", return_value=object
    ) as tzlocal, patch.object(
        salt.utils.platform, "is_proxy", return_value=False
    ) as is_proxy:
        ret = core.locale_info()

        tzname.assert_called_once_with()
        assert len(now_ret_object.method_calls) == 1
        now.assert_called_once_with(object)
        assert len(datetime.method_calls) == 1
        assert len(datetime_module.method_calls) == 1
        tzlocal.assert_called_once_with()
        is_proxy.assert_called_once_with()

        assert ret["locale_info"]["timezone"] == "MDT_FAKE"


@pytest.mark.skipif(not core._DATEUTIL_TZ, reason="Missing dateutil.tz")
def test_locale_info_unicode_error_tzname():
    # UnicodeDecodeError most have the default string encoding
    unicode_error = UnicodeDecodeError("fake", b"\x00\x00", 1, 2, "fake")

    # mock datetime.now().tzname()
    # cant just mock now because it is read only
    tzname = Mock(return_value="MDT_FAKE")
    now_ret_object = Mock(tzname=tzname)
    now = Mock(return_value=now_ret_object)
    datetime = Mock(now=now)

    # mock tzname[0].decode()
    decode = Mock(return_value="CST_FAKE")
    tzname2 = [Mock(decode=decode)]

    with patch.object(
        core, "datetime", datetime=datetime
    ) as datetime_module, patch.object(
        core.dateutil.tz, "tzlocal", side_effect=unicode_error
    ) as tzlocal, patch.object(
        salt.utils.platform, "is_proxy", return_value=False
    ) as is_proxy, patch.object(
        core.salt.utils.platform, "is_windows", return_value=True
    ) as is_windows, patch.object(
        core, "time", tzname=tzname2
    ):
        ret = core.locale_info()

        tzname.assert_not_called()
        assert len(now_ret_object.method_calls) == 0
        now.assert_not_called()
        assert len(datetime.method_calls) == 0
        decode.assert_called_once_with("mbcs")
        assert len(tzname2[0].method_calls) == 1
        assert len(datetime_module.method_calls) == 0
        tzlocal.assert_called_once_with()
        is_proxy.assert_called_once_with()
        is_windows.assert_called_once_with()

        assert ret["locale_info"]["timezone"] == "CST_FAKE"


@pytest.mark.skipif(core._DATEUTIL_TZ, reason="Not Missing dateutil.tz")
def test_locale_info_no_tz_tzname():
    with patch.object(
        salt.utils.platform, "is_proxy", return_value=False
    ) as is_proxy, patch.object(
        core.salt.utils.platform, "is_windows", return_value=True
    ) as is_windows:
        ret = core.locale_info()
        is_proxy.assert_called_once_with()
        is_windows.assert_not_called()
        assert ret["locale_info"]["timezone"] == "unknown"


def test_cwd_exists():
    cwd_grain = core.cwd()

    assert isinstance(cwd_grain, dict)
    assert "cwd" in cwd_grain
    assert cwd_grain["cwd"] == os.getcwd()


def test_cwd_is_cwd():
    cwd = os.getcwd()

    try:
        # change directory
        new_dir = os.path.split(cwd)[0]
        os.chdir(new_dir)

        cwd_grain = core.cwd()

        assert cwd_grain["cwd"] == new_dir
    finally:
        # change back to original directory
        os.chdir(cwd)


def test_virtual_set_virtual_grain():
    osdata = {}

    (
        osdata["kernel"],
        osdata["nodename"],
        osdata["kernelrelease"],
        osdata["kernelversion"],
        osdata["cpuarch"],
        _,
    ) = platform.uname()

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": salt.modules.cmdmod.run,
            "cmd.run_all": salt.modules.cmdmod.run_all,
            "cmd.retcode": salt.modules.cmdmod.retcode,
            "smbios.get": salt.modules.smbios.get,
        },
    ):

        virtual_grains = core._virtual(osdata)

    assert "virtual" in virtual_grains


def test_virtual_has_virtual_grain():
    osdata = {"virtual": "something"}

    (
        osdata["kernel"],
        osdata["nodename"],
        osdata["kernelrelease"],
        osdata["kernelversion"],
        osdata["cpuarch"],
        _,
    ) = platform.uname()

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": salt.modules.cmdmod.run,
            "cmd.run_all": salt.modules.cmdmod.run_all,
            "cmd.retcode": salt.modules.cmdmod.retcode,
            "smbios.get": salt.modules.smbios.get,
        },
    ):

        virtual_grains = core._virtual(osdata)

    assert "virtual" in virtual_grains
    assert virtual_grains["virtual"] != "physical"


@pytest.mark.skip_unless_on_windows
@pytest.mark.parametrize(
    ("osdata", "expected"),
    [
        ({"kernel": "Not Windows"}, {}),
        ({"kernel": "Windows"}, {"virtual": "physical"}),
        ({"kernel": "Windows", "manufacturer": "QEMU"}, {"virtual": "kvm"}),
        ({"kernel": "Windows", "manufacturer": "Bochs"}, {"virtual": "kvm"}),
        (
            {"kernel": "Windows", "productname": "oVirt"},
            {"virtual": "kvm", "virtual_subtype": "oVirt"},
        ),
        (
            {"kernel": "Windows", "productname": "RHEV Hypervisor"},
            {"virtual": "kvm", "virtual_subtype": "rhev"},
        ),
        (
            {"kernel": "Windows", "productname": "CloudStack KVM Hypervisor"},
            {"virtual": "kvm", "virtual_subtype": "cloudstack"},
        ),
        (
            {"kernel": "Windows", "productname": "VirtualBox"},
            {"virtual": "VirtualBox"},
        ),
        (
            # Old value
            {"kernel": "Windows", "productname": "VMware Virtual Platform"},
            {"virtual": "VMware"},
        ),
        (
            # Server 2019 Value
            {"kernel": "Windows", "productname": "VMware7,1"},
            {"virtual": "VMware"},
        ),
        (
            # Shorter value
            {"kernel": "Windows", "productname": "VMware"},
            {"virtual": "VMware"},
        ),
        (
            {
                "kernel": "Windows",
                "manufacturer": "Microsoft",
                "productname": "Virtual Machine",
            },
            {"virtual": "VirtualPC"},
        ),
        (
            {"kernel": "Windows", "manufacturer": "Parallels Software"},
            {"virtual": "Parallels"},
        ),
    ],
)
def test__windows_virtual(osdata, expected):
    result = core._windows_virtual(osdata)
    assert result == expected


@pytest.mark.skip_unless_on_windows
def test_windows_virtual_set_virtual_grain():
    osdata = {}

    (
        osdata["kernel"],
        osdata["nodename"],
        osdata["kernelrelease"],
        osdata["kernelversion"],
        osdata["cpuarch"],
        _,
    ) = platform.uname()

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": salt.modules.cmdmod.run,
            "cmd.run_all": salt.modules.cmdmod.run_all,
            "cmd.retcode": salt.modules.cmdmod.retcode,
            "smbios.get": salt.modules.smbios.get,
        },
    ):

        virtual_grains = core._windows_virtual(osdata)

    assert "virtual" in virtual_grains


@pytest.mark.skip_unless_on_windows
def test_windows_virtual_has_virtual_grain():
    osdata = {"virtual": "something"}

    (
        osdata["kernel"],
        osdata["nodename"],
        osdata["kernelrelease"],
        osdata["kernelversion"],
        osdata["cpuarch"],
        _,
    ) = platform.uname()

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": salt.modules.cmdmod.run,
            "cmd.run_all": salt.modules.cmdmod.run_all,
            "cmd.retcode": salt.modules.cmdmod.retcode,
            "smbios.get": salt.modules.smbios.get,
        },
    ):

        virtual_grains = core._windows_virtual(osdata)

    assert "virtual" in virtual_grains
    assert virtual_grains["virtual"] != "physical"


@pytest.mark.skip_unless_on_windows
def test_osdata_virtual_key_win():
    with patch.dict(
        core.__salt__,
        {
            "cmd.run": salt.modules.cmdmod.run,
            "cmd.run_all": salt.modules.cmdmod.run_all,
            "cmd.retcode": salt.modules.cmdmod.retcode,
            "smbios.get": salt.modules.smbios.get,
        },
    ):

        _windows_platform_data_ret = core.os_data()
        _windows_platform_data_ret["virtual"] = "something"

        with patch.object(
            core, "_windows_platform_data", return_value=_windows_platform_data_ret
        ) as _windows_platform_data:

            osdata_grains = core.os_data()
            _windows_platform_data.assert_called_once()

        assert "virtual" in osdata_grains
        assert osdata_grains["virtual"] != "physical"


@pytest.mark.skip_unless_on_linux
def test_linux_cpu_data_num_cpus():
    cpuinfo_list = []
    for i in range(0, 20):
        cpuinfo_dict = {
            "processor": i,
            "cpu_family": 6,
            "model_name": "Intel(R) Core(TM) i7-7700HQ CPU @ 2.80GHz",
            "flags": "fpu vme de pse tsc msr pae mce cx8 apic sep mtrr",
        }
        cpuinfo_list.append(cpuinfo_dict)
    cpuinfo_content = ""
    for item in cpuinfo_list:
        cpuinfo_content += (
            "processor: {}\n" "cpu family: {}\n" "model name: {}\n" "flags: {}\n\n"
        ).format(
            item["processor"], item["cpu_family"], item["model_name"], item["flags"]
        )

    with patch.object(os.path, "isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", mock_open(read_data=cpuinfo_content)
    ):
        ret = core._linux_cpudata()
        assert "num_cpus" in ret
        assert len(cpuinfo_list) == ret["num_cpus"]


@pytest.mark.skip_on_windows
def test_bsd_osfullname():
    """
    Test to ensure osfullname exists on *BSD systems
    """
    _path_exists_map = {}
    _path_isfile_map = {}
    _cmd_run_map = {
        "freebsd-version -u": "10.3-RELEASE",
        "/sbin/sysctl -n hw.physmem": "2121781248",
        "/sbin/sysctl -n vm.swap_total": "419430400",
    }

    path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
    path_isfile_mock = MagicMock(side_effect=lambda x: _path_isfile_map.get(x, False))
    cmd_run_mock = MagicMock(side_effect=lambda x: _cmd_run_map[x])
    empty_mock = MagicMock(return_value={})

    nt_uname = namedtuple(
        "nt_uname", ["system", "node", "release", "version", "machine", "processor"]
    )
    mock_freebsd_uname = MagicMock(
        return_value=nt_uname(
            "FreeBSD",
            "freebsd10.3-hostname-8148",
            "10.3-RELEASE",
            "FreeBSD 10.3-RELEASE #0 r297264: Fri Mar 25 02:10:02 UTC 2016     root@releng1.nyi.freebsd.org:/usr/obj/usr/src/sys/GENERIC",
            "amd64",
            "amd64",
        )
    )

    with patch.object(platform, "uname", mock_freebsd_uname), patch.object(
        salt.utils.platform, "is_linux", MagicMock(return_value=False)
    ), patch.object(
        salt.utils.platform, "is_freebsd", MagicMock(return_value=True)
    ), patch.object(
        # Skip the first if statement
        salt.utils.platform,
        "is_proxy",
        MagicMock(return_value=False),
    ), patch.object(
        # Skip the init grain compilation (not pertinent)
        os.path,
        "exists",
        path_exists_mock,
    ), patch(
        "salt.utils.path.which", return_value="/sbin/sysctl"
    ):
        # Make a bunch of functions return empty dicts,
        # we don't care about these grains for the
        # purposes of this test.
        with patch.object(core, "_bsd_cpudata", empty_mock), patch.object(
            core, "_hw_data", empty_mock
        ), patch.object(core, "_virtual", empty_mock), patch.object(
            core, "_ps", empty_mock
        ), patch.dict(
            core.__salt__, {"cmd.run": cmd_run_mock}
        ):
            os_grains = core.os_data()

    assert "osfullname" in os_grains
    assert os_grains.get("osfullname") == "FreeBSD"


def test_saltversioninfo():
    """
    test saltversioninfo core grain.
    """
    ret = core.saltversioninfo()
    info = ret["saltversioninfo"]
    assert isinstance(ret, dict)
    assert isinstance(info, list)
    try:
        assert len(info) == 1
    except AssertionError:
        # We have a minor version we need to test
        assert len(info) == 2
    assert all([x is not None for x in info])
    assert all([isinstance(x, int) for x in info])


def test_path():
    comps = ["foo", "bar", "baz"]
    path = os.path.pathsep.join(comps)
    with patch.dict(os.environ, {"PATH": path}):
        result = core.path()
    assert result == {"path": path, "systempath": comps}, result


@pytest.mark.skip_unless_on_linux
def test__hw_data_linux_empty():
    with patch("os.path.exists", return_value=True), patch(
        "salt.utils.platform.is_proxy", return_value=False
    ), patch("salt.utils.files.fopen", mock_open(read_data=b"")):
        assert core._hw_data({"kernel": "Linux"}) == {
            "biosreleasedate": "",
            "biosversion": "",
            "biosvendor": "",
            "boardname": "",
            "manufacturer": "",
            "productname": "",
            "serialnumber": "",
            "uuid": "",
        }


@pytest.mark.skip_unless_on_linux
def test__hw_data_linux_unicode_error():
    def _fopen(*args):
        class _File:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                raise UnicodeDecodeError("enconding", b"", 1, 2, "reason")

        return _File()

    with patch("os.path.exists", return_value=True), patch(
        "salt.utils.platform.is_proxy"
    ), patch("salt.utils.files.fopen", _fopen):
        assert core._hw_data({"kernel": "Linux"}) == {}


@pytest.mark.skip_unless_on_windows
def test_kernelparams_return_windows():
    """
    Should return empty dictionary on Windows
    """
    assert core.kernelparams() == {}


@pytest.mark.skip_unless_on_linux
@pytest.mark.parametrize(
    "cmdline,expectation",
    (
        (
            "BOOT_IMAGE=/vmlinuz-3.10.0-693.2.2.el7.x86_64",
            {"kernelparams": [("BOOT_IMAGE", "/vmlinuz-3.10.0-693.2.2.el7.x86_64")]},
        ),
        (
            "root=/dev/mapper/centos_daemon-root",
            {"kernelparams": [("root", "/dev/mapper/centos_daemon-root")]},
        ),
        (
            "rhgb quiet ro",
            {"kernelparams": [("rhgb", None), ("quiet", None), ("ro", None)]},
        ),
        ('param="value1"', {"kernelparams": [("param", "value1")]}),
        (
            'param="value1 value2 value3"',
            {"kernelparams": [("param", "value1 value2 value3")]},
        ),
        (
            'param="value1 value2 value3" LANG="pl" ro',
            {
                "kernelparams": [
                    ("param", "value1 value2 value3"),
                    ("LANG", "pl"),
                    ("ro", None),
                ]
            },
        ),
        ("ipv6.disable=1", {"kernelparams": [("ipv6.disable", "1")]}),
        (
            'param="value1:value2:value3"',
            {"kernelparams": [("param", "value1:value2:value3")]},
        ),
        (
            'param="value1,value2,value3"',
            {"kernelparams": [("param", "value1,value2,value3")]},
        ),
        (
            'param="value1" param="value2" param="value3"',
            {
                "kernelparams": [
                    ("param", "value1"),
                    ("param", "value2"),
                    ("param", "value3"),
                ]
            },
        ),
    ),
)
def test_kernelparams_return_linux(cmdline, expectation):
    with patch("salt.utils.files.fopen", mock_open(read_data=cmdline)):
        assert core.kernelparams() == expectation


@pytest.mark.skip_unless_on_linux
def test_kernelparams_return_linux_non_utf8():
    _salt_utils_files_fopen = salt.utils.files.fopen

    expected = {
        "kernelparams": [
            ("TEST_KEY1", "VAL1"),
            ("TEST_KEY2", "VAL2"),
            ("BOOTABLE_FLAG", "\udc80"),
            ("TEST_KEY_NOVAL", None),
            ("TEST_KEY3", "3"),
        ]
    }

    with tempfile.TemporaryDirectory() as tempdir:

        def _open_mock(file_name, *args, **kwargs):
            return _salt_utils_files_fopen(
                os.path.join(tempdir, "cmdline"), *args, **kwargs
            )

        with salt.utils.files.fopen(
            os.path.join(tempdir, "cmdline"),
            "wb",
        ) as cmdline_fh, patch("salt.utils.files.fopen", _open_mock):
            cmdline_fh.write(
                b'TEST_KEY1=VAL1 TEST_KEY2=VAL2 BOOTABLE_FLAG="\x80" TEST_KEY_NOVAL TEST_KEY3=3\n'
            )
            cmdline_fh.close()
            assert core.kernelparams() == expected


def test_linux_gpus():
    """
    Test GPU detection on Linux systems
    """

    def _cmd_side_effect(cmd):
        ret = ""
        for device in devices:
            ret += textwrap.dedent(
                """
                                      Class:	{}
                                      Vendor:	{}
                                      Device:	{}
                                      SVendor:	Evil Corp.
                                      SDevice:	Graphics XXL
                                      Rev:	c1
                                      NUMANode:	0"""
            ).format(*device)
            ret += "\n"
        return ret.strip()

    devices = [
        [
            "VGA compatible controller",
            "Advanced Micro Devices, Inc. [AMD/ATI]",
            "Vega [Radeon RX Vega]]",
            "amd",
        ],  # AMD
        [
            "Audio device",
            "Advanced Micro Devices, Inc. [AMD/ATI]",
            "Device aaf8",
            None,
        ],  # non-GPU device
        [
            "VGA compatible controller",
            "NVIDIA Corporation",
            "GK208 [GeForce GT 730]",
            "nvidia",
        ],  # Nvidia
        [
            "VGA compatible controller",
            "Intel Corporation",
            "Device 5912",
            "intel",
        ],  # Intel
        [
            "VGA compatible controller",
            "ATI Technologies Inc",
            "RC410 [Radeon Xpress 200M]",
            "ati",
        ],  # ATI
        [
            "3D controller",
            "NVIDIA Corporation",
            "GeForce GTX 950M",
            "nvidia",
        ],  # 3D controller
        [
            "Display controller",
            "Intel Corporation",
            "HD Graphics P630",
            "intel",
        ],  # Display controller
    ]
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/sbin/lspci")
    ), patch.dict(core.__salt__, {"cmd.run": MagicMock(side_effect=_cmd_side_effect)}):
        ret = core._linux_gpu_data()["gpus"]
        count = 0
        for device in devices:
            if device[3] is None:
                continue
            assert ret[count]["model"] == device[2]
            assert ret[count]["vendor"] == device[3]
            count += 1


def test_get_server_id():
    expected = {"server_id": 94889706}
    with patch.dict(core.__opts__, {"id": "anid"}):
        assert core.get_server_id() == expected

    with patch.dict(core.__opts__, {"id": "otherid"}):
        assert core.get_server_id() != expected


def test_linux_cpudata_ppc64le():
    cpuinfo = """processor	: 0
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              processor	: 1
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              processor	: 2
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              processor	: 3
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              processor	: 4
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              processor	: 5
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              processor	: 6
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              processor	: 7
              cpu		: POWER9 (architected), altivec supported
              clock		: 2750.000000MHz
              revision	: 2.2 (pvr 004e 0202)

              timebase	: 512000000
              platform	: pSeries
              model		: IBM,9009-42A
              machine		: CHRP IBM,9009-42A
              MMU		: Hash
              """

    expected = {
        "num_cpus": 8,
        "cpu_model": "POWER9 (architected), altivec supported",
        "cpu_flags": [],
    }

    with patch("os.path.isfile", return_value=True):
        with patch("salt.utils.files.fopen", mock_open(read_data=cpuinfo)):
            assert expected == core._linux_cpudata()


@pytest.mark.parametrize(
    "virt,expected",
    [
        ("ibm_power-kvm", {"virtual": "kvm"}),
        ("ibm_power-lpar_shared", {"virtual": "LPAR", "virtual_subtype": "shared"}),
        (
            "ibm_power-lpar_dedicated",
            {"virtual": "LPAR", "virtual_subtype": "dedicated"},
        ),
        ("ibm_power-some_other", {"virtual": "physical"}),
    ],
)
def test_ibm_power_virtual(virt, expected):
    """
    Test if virtual grains are parsed correctly on various IBM power virt types
    """
    with patch.object(salt.utils.platform, "is_windows", MagicMock(return_value=False)):
        with patch.object(salt.utils.path, "which", MagicMock(return_value=True)):
            with patch.dict(
                core.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={
                            "pid": 78,
                            "retcode": 0,
                            "stderr": "",
                            "stdout": virt,
                        }
                    )
                },
            ):
                osdata = {
                    "kernel": "test",
                }
                ret = core._virtual(osdata)
                assert expected == ret


@pytest.mark.parametrize(
    "test_input,expected",
    [
        (
            {
                "/proc/device-tree/model": "fsl,MPC8349EMITX",
                "/proc/device-tree/system-id": "fsl,ABCDEF",
            },
            {
                "manufacturer": "fsl",
                "productname": "MPC8349EMITX",
                "serialnumber": "fsl,ABCDEF",
            },
        ),
        (
            {
                "/proc/device-tree/model": "MPC8349EMITX",
                "/proc/device-tree/system-id": "fsl,ABCDEF",
            },
            {"productname": "MPC8349EMITX", "serialnumber": "fsl,ABCDEF"},
        ),
        (
            {"/proc/device-tree/model": "IBM,123456,789"},
            {"manufacturer": "IBM", "productname": "123456,789"},
        ),
        (
            {"/proc/device-tree/system-id": "IBM,123456,789"},
            {"serialnumber": "IBM,123456,789"},
        ),
        (
            {
                "/proc/device-tree/model": "Raspberry Pi 4 Model B Rev 1.1",
                "/proc/device-tree/serial-number": "100000000123456789",
            },
            {
                "serialnumber": "100000000123456789",
                "productname": "Raspberry Pi 4 Model B Rev 1.1",
            },
        ),
        (
            {
                "/proc/device-tree/serial-number": "100000000123456789",
                "/proc/device-tree/system-id": "fsl,ABCDEF",
            },
            {"serialnumber": "100000000123456789"},
        ),
    ],
)
def test_linux_devicetree_data(test_input, expected):
    def _mock_open(filename, *args, **kwargs):
        """
        Helper mock because we want to return arbitrary value based on the filename, rather than expecting we get the proper calls in order
        """

        def _raise_fnfe():
            raise FileNotFoundError()

        m = MagicMock()
        m.__enter__.return_value.read = (
            lambda: test_input.get(filename)  # pylint: disable=W0640
            if filename in test_input  # pylint: disable=W0640
            else _raise_fnfe()
        )

        return m

    with patch("os.path.isfile", return_value=True):
        with patch("salt.utils.files.fopen", new=_mock_open):
            assert expected == core._linux_devicetree_platform_data()


@pytest.mark.skip_on_windows
def test_linux_proc_files_with_non_utf8_chars():
    _salt_utils_files_fopen = salt.utils.files.fopen

    empty_mock = MagicMock(return_value={})
    os_release_mock = {"NAME": "Linux", "ID": "linux", "PRETTY_NAME": "Linux"}

    with tempfile.TemporaryDirectory() as tempdir:

        def _mock_open(filename, *args, **kwargs):
            return _salt_utils_files_fopen(
                os.path.join(tempdir, "cmdline-1"), *args, **kwargs
            )

        with salt.utils.files.fopen(
            os.path.join(tempdir, "cmdline-1"),
            "wb",
        ) as cmdline_fh, patch("os.path.isfile", return_value=False), patch(
            "salt.utils.files.fopen", _mock_open
        ), patch.dict(
            core.__salt__,
            {
                "cmd.retcode": salt.modules.cmdmod.retcode,
                "cmd.run": MagicMock(return_value=""),
            },
        ), patch.object(
            core, "_linux_bin_exists", return_value=False
        ), patch.object(
            core, "_parse_lsb_release", return_value=empty_mock
        ), patch.object(
            core, "_freedesktop_os_release", return_value=os_release_mock
        ), patch.object(
            core, "_hw_data", return_value=empty_mock
        ), patch.object(
            core, "_virtual", return_value=empty_mock
        ), patch.object(
            core, "_bsd_cpudata", return_value=empty_mock
        ), patch.object(
            os, "stat", side_effect=OSError()
        ):
            cmdline_fh.write(
                b"/usr/lib/systemd/systemd\x00--switched-root\x00--system\x00--deserialize\x0028\x80\x00"
            )
            cmdline_fh.close()
            os_grains = core.os_data()
            assert os_grains != {}


@pytest.mark.skip_on_windows
def test_virtual_linux_proc_files_with_non_utf8_chars():
    _salt_utils_files_fopen = salt.utils.files.fopen

    def _is_file_mock(filename):
        if filename == "/proc/1/environ":
            return True
        return False

    with tempfile.TemporaryDirectory() as tempdir:

        def _mock_open(filename, *args, **kwargs):
            return _salt_utils_files_fopen(
                os.path.join(tempdir, "environ"), *args, **kwargs
            )

        with salt.utils.files.fopen(
            os.path.join(tempdir, "environ"),
            "wb",
        ) as environ_fh, patch("os.path.isfile", _is_file_mock), patch(
            "salt.utils.files.fopen", _mock_open
        ), patch.object(
            salt.utils.path, "which", MagicMock(return_value=None)
        ), patch.dict(
            core.__salt__,
            {
                "cmd.run_all": MagicMock(
                    return_value={"retcode": 1, "stderr": "", "stdout": ""}
                ),
                "cmd.run": MagicMock(return_value=""),
            },
        ):
            environ_fh.write(b"KEY1=VAL1 KEY2=VAL2\x80 KEY2=VAL2")
            environ_fh.close()
            virt_grains = core._virtual({"kernel": "Linux"})
            assert virt_grains == {"virtual": "physical"}


@pytest.mark.skip_unless_on_linux
def test_virtual_set_virtual_ec2():
    osdata = {}

    (
        osdata["kernel"],
        osdata["nodename"],
        osdata["kernelrelease"],
        osdata["kernelversion"],
        osdata["cpuarch"],
        _,
    ) = platform.uname()

    which_mock = MagicMock(
        side_effect=[
            # Check with virt-what
            "/usr/sbin/virt-what",
            "/usr/sbin/virt-what",
            None,
            "/usr/sbin/dmidecode",
            # Check with systemd-detect-virt
            None,
            "/usr/bin/systemd-detect-virt",
            None,
            "/usr/sbin/dmidecode",
            # Check with systemd-detect-virt when no dmidecode available
            None,
            "/usr/bin/systemd-detect-virt",
            None,
            None,
            # Check with systemd-detect-virt returning amazon and no dmidecode available
            None,
            "/usr/bin/systemd-detect-virt",
            None,
            None,
        ]
    )
    cmd_run_all_mock = MagicMock(
        side_effect=[
            # Check with virt-what
            {"retcode": 0, "stderr": "", "stdout": "xen"},
            {
                "retcode": 0,
                "stderr": "",
                "stdout": "\n".join(
                    [
                        "dmidecode 3.2",
                        "Getting SMBIOS data from sysfs.",
                        "SMBIOS 2.7 present.",
                        "",
                        "Handle 0x0100, DMI type 1, 27 bytes",
                        "System Information",
                        "	Manufacturer: Xen",
                        "	Product Name: HVM domU",
                        "	Version: 4.11.amazon",
                        "	Serial Number: 12345678-abcd-4321-dcba-0123456789ab",
                        "	UUID: 01234567-dcba-1234-abcd-abcdef012345",
                        "	Wake-up Type: Power Switch",
                        "	SKU Number: Not Specified",
                        "	Family: Not Specified",
                        "",
                        "Handle 0x2000, DMI type 32, 11 bytes",
                        "System Boot Information",
                        "	Status: No errors detected",
                    ]
                ),
            },
            # Check with systemd-detect-virt
            {"retcode": 0, "stderr": "", "stdout": "kvm"},
            {
                "retcode": 0,
                "stderr": "",
                "stdout": "\n".join(
                    [
                        "dmidecode 3.2",
                        "Getting SMBIOS data from sysfs.",
                        "SMBIOS 2.7 present.",
                        "",
                        "Handle 0x0001, DMI type 1, 27 bytes",
                        "System Information",
                        "	Manufacturer: Amazon EC2",
                        "	Product Name: m5.large",
                        "	Version: Not Specified",
                        "	Serial Number: 01234567-dcba-1234-abcd-abcdef012345",
                        "	UUID: 12345678-abcd-4321-dcba-0123456789ab",
                        "	Wake-up Type: Power Switch",
                        "	SKU Number: Not Specified",
                        "	Family: Not Specified",
                    ]
                ),
            },
            # Check with systemd-detect-virt when no dmidecode available
            {"retcode": 0, "stderr": "", "stdout": "kvm"},
            # Check with systemd-detect-virt returning amazon and no dmidecode available
            {"retcode": 0, "stderr": "", "stdout": "amazon"},
        ]
    )

    def _mock_is_file(filename):
        if filename in (
            "/proc/1/cgroup",
            "/proc/cpuinfo",
            "/sys/devices/virtual/dmi/id/product_name",
            "/proc/xen/xsd_kva",
            "/proc/xen/capabilities",
        ):
            return False
        return True

    with patch("salt.utils.path.which", which_mock), patch.dict(
        core.__salt__,
        {
            "cmd.run": salt.modules.cmdmod.run,
            "cmd.run_all": cmd_run_all_mock,
            "cmd.retcode": salt.modules.cmdmod.retcode,
            "smbios.get": salt.modules.smbios.get,
        },
    ), patch("os.path.isfile", _mock_is_file), patch(
        "os.path.isdir", return_value=False
    ):

        virtual_grains = core._virtual(osdata.copy())

        assert virtual_grains["virtual"] == "xen"
        assert virtual_grains["virtual_subtype"] == "Amazon EC2"

        virtual_grains = core._virtual(osdata.copy())

        assert virtual_grains["virtual"] == "Nitro"
        assert virtual_grains["virtual_subtype"] == "Amazon EC2 (m5.large)"

        virtual_grains = core._virtual(osdata.copy())

        assert virtual_grains["virtual"] == "kvm"
        assert "virtual_subtype" not in virtual_grains

        virtual_grains = core._virtual(osdata.copy())

        assert virtual_grains["virtual"] == "Nitro"
        assert virtual_grains["virtual_subtype"] == "Amazon EC2"

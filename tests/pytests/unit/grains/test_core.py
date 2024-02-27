"""
tests.pytests.unit.grains.test_core
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: Erik Johnson <erik@saltstack.com>
    :codeauthor: David Murphy <damurphy@vmware.com>
"""

import errno
import locale
import logging
import os
import pathlib
import platform
import socket
import sys
import tempfile
import textwrap
import uuid
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

    with patch("salt.utils.platform.is_proxy", return_value=True):
        assert core.ip6_interfaces() == {}

    with patch("salt.utils.platform.is_proxy", return_value=True):
        assert core.ip4_interfaces() == {}

    with patch("salt.utils.platform.is_proxy", return_value=True):
        assert core.ip_interfaces() == {}


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
        (
            "cpe:2.3:o:microsoft:windows_xp:5.1.601",
            {
                "phase": None,
                "version": "5.1.601",
                "product": "windows_xp",
                "vendor": "microsoft",
                "part": "operating system",
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
        f"{built_in}.__import__", side_effect=_import_mock
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
        f"{built_in}.__import__", side_effect=_import_mock
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
        f"{built_in}.__import__", side_effect=_import_mock
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
def test_debian_12_os_grains():
    """
    Test if OS grains are parsed correctly in Debian 12 "bookworm"
    """
    # /etc/os-release data taken from base-files 12.4
    _os_release_data = {
        "PRETTY_NAME": "Debian GNU/Linux 12 (bookworm)",
        "NAME": "Debian GNU/Linux",
        "VERSION_ID": "12",
        "VERSION": "12 (bookworm)",
        "VERSION_CODENAME": "bookworm",
        "ID": "debian",
        "HOME_URL": "https://www.debian.org/",
        "SUPPORT_URL": "https://www.debian.org/support",
        "BUG_REPORT_URL": "https://bugs.debian.org/",
    }
    expectation = {
        "os": "Debian",
        "os_family": "Debian",
        "oscodename": "bookworm",
        "osfullname": "Debian GNU/Linux",
        "osrelease": "12",
        "osrelease_info": (12,),
        "osmajorrelease": 12,
        "osfinger": "Debian-12",
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
    cgroup_data = f"10:memory{cgroup_substr}a_long_sha256sum"
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
            side_effect=lambda x: (
                True if x in ("/proc/1/cgroup", "/proc/1/environ") else False
            )
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
            side_effect=lambda x: (
                True
                if x in ("/proc/cpuinfo", "/proc/1/cgroup", "/proc/1/environ")
                else False
            )
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
        mylogdebug = f"cmd.run_all: '{cmd}'"
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
        ip_method = f"is_ipv{ip_v}"
        assert getattr(salt.utils.network, ip_method)(val)


def _check_empty(key, value, empty):
    """
    if empty is False and value does not exist assert error
    if empty is True and value exists assert error
    """
    if not empty and not value:
        raise Exception(f"{key} is empty, expecting a value")
    elif empty and value:
        raise Exception(f"{key} is suppose to be empty. value: {value} exists")


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
def test_fqdn_proxy_return_empty():
    """
    test ip_fqdn returns empty for proxy minions
    """

    with patch.object(salt.utils.platform, "is_proxy", MagicMock(return_value=True)):
        assert core.ip_fqdn() == {}


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

        with patch("os.path.exists", return_value=False), patch.object(
            salt.utils.dns, "parse_resolv", MagicMock(return_value=resolv_mock)
        ):
            assert core.dns() == ret

    with patch.object(salt.utils.platform, "is_windows", MagicMock(return_value=True)):
        assert core.dns() == {}

    with patch.object(
        salt.utils.platform, "is_windows", MagicMock(return_value=True)
    ), patch("salt.grains.core.__opts__", {"proxyminion": True}):
        assert core.dns() == {}


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
@pytest.mark.timeout(60)
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
                        "stdout": f"\n\n{virt}",
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

    def _cmd_side_effect_megabyte(cmd):
        if "hw.memsize" in cmd:
            return "4294967296"
        elif "vm.swapusage" in cmd:
            return "total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)"

    with patch.dict(
        core.__salt__, {"cmd.run": MagicMock(side_effect=_cmd_side_effect_megabyte)}
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/sysctl")):
        ret = core._osx_memdata()
        assert ret["swap_total"] == 0
        assert ret["mem_total"] == 4096

    def _cmd_side_effect_kilobyte(cmd):
        if "hw.memsize" in cmd:
            return "4294967296"
        elif "vm.swapusage" in cmd:
            return "total = 0.00K  used = 0.00K  free = 0.00K  (encrypted)"

    with patch.dict(
        core.__salt__, {"cmd.run": MagicMock(side_effect=_cmd_side_effect_kilobyte)}
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/sysctl")):
        ret = core._osx_memdata()
        assert ret["swap_total"] == 0
        assert ret["mem_total"] == 4096

    def _cmd_side_effect_gigabyte(cmd):
        if "hw.memsize" in cmd:
            return "4294967296"
        elif "vm.swapusage" in cmd:
            return "total = 0.00G  used = 0.00G  free = 0.00G  (encrypted)"

    with patch.dict(
        core.__salt__, {"cmd.run": MagicMock(side_effect=_cmd_side_effect_gigabyte)}
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/sysctl")):
        ret = core._osx_memdata()
        assert ret["swap_total"] == 0
        assert ret["mem_total"] == 4096

    with patch.dict(
        core.__salt__, {"cmd.run": MagicMock(side_effect=_cmd_side_effect_gigabyte)}
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/sysctl")):
        ret = core._memdata({"kernel": "Darwin"})
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


def test_locale_info_proxy_empty():
    with patch.object(salt.utils.platform, "is_proxy", return_value=True):
        ret = core.locale_info()
        assert ret == {"locale_info": {}}


@pytest.mark.skipif(not core._DATEUTIL_TZ, reason="Missing dateutil.tz")
def test_locale_getlocale_exception():
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
    ) as is_proxy, patch.object(
        locale, "getlocale", side_effect=Exception()
    ):
        ret = core.locale_info()

        assert ret["locale_info"]["defaultlanguage"] == "unknown"
        assert ret["locale_info"]["defaultencoding"] == "unknown"


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


def test__windows_platform_data():
    pass


@pytest.mark.skip_unless_on_windows
@pytest.mark.parametrize(
    ("osdata", "expected"),
    [
        ({"kernel": "Not Windows"}, {}),
        ({"kernel": "Windows"}, {"virtual": "physical"}),
        ({"kernel": "Windows", "manufacturer": "QEMU"}, {"virtual": "kvm"}),
        ({"kernel": "Windows", "biosstring": "VRTUAL"}, {"virtual": "HyperV"}),
        ({"kernel": "Windows", "biosstring": "A M I"}, {"virtual": "VirtualPC"}),
        (
            {"kernel": "Windows", "biosstring": "Xen", "productname": "HVM domU"},
            {"virtual": "Xen", "virtual_subtype": "HVM domU"},
        ),
        ({"kernel": "Windows", "biosstring": "AMAZON"}, {"virtual": "EC2"}),
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
        ({"kernel": "Windows", "productname": "OpenStack"}, {"virtual": "OpenStack"}),
        (
            {"kernel": "Windows", "manufacturer": "Parallels Software"},
            {"virtual": "Parallels"},
        ),
        (
            {"kernel": "Windows", "manufacturer": None, "productname": None},
            {"virtual": "physical"},
        ),
        (
            {"kernel": "Windows", "productname": "CloudStack KVM Hypervisor"},
            {"virtual": "kvm", "virtual_subtype": "cloudstack"},
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

    virtual_grains = core._windows_virtual(osdata)

    assert "virtual" in virtual_grains


@pytest.mark.skip_unless_on_windows
def test_osdata_virtual_key_win():
    osdata_grains = core.os_data()
    assert "virtual" in osdata_grains


@pytest.mark.skip_unless_on_linux
def test_linux_cpu_data():
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
        assert "cpu_flags" in ret
        assert "cpu_model" in ret

    cpuinfo_list = []
    cpuinfo_dict = {
        "processors": 20,
        "cpu_family": 6,
        "model_name": "Intel(R) Core(TM) i7-7700HQ CPU @ 2.80GHz",
        "Features": "fpu vme de pse tsc msr pae mce cx8 apic sep mtrr",
    }

    cpuinfo_list.append(cpuinfo_dict)
    cpuinfo_content = ""
    for item in cpuinfo_list:
        cpuinfo_content += (
            "# processors: {}\n" "cpu family: {}\n" "vendor_id: {}\n" "Features: {}\n\n"
        ).format(
            item["processors"], item["cpu_family"], item["model_name"], item["Features"]
        )

    with patch.object(os.path, "isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", mock_open(read_data=cpuinfo_content)
    ):
        ret = core._linux_cpudata()
        assert "num_cpus" in ret
        assert "cpu_flags" in ret
        assert "cpu_model" in ret

    cpuinfo_dict = {
        "Processor": "ARMv6-compatible processor rev 7 (v6l)",
        "BogoMIPS": "697.95",
        "Features": "swp half thumb fastmult vfp edsp java tls",
        "CPU implementer": "0x41",
        "CPU architecture": "7",
        "CPU variant": "0x0",
        "CPU part": "0xb76",
        "CPU revision": "7",
        "Hardware": "BCM2708",
        "Revision": "0002",
        "Serial": "00000000",
    }

    cpuinfo_content = ""
    for item in cpuinfo_dict:
        cpuinfo_content += f"{item}: {cpuinfo_dict[item]}\n"
    cpuinfo_content += "\n\n"

    with patch.object(os.path, "isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", mock_open(read_data=cpuinfo_content)
    ):
        ret = core._linux_cpudata()
        assert "num_cpus" in ret
        assert "cpu_flags" in ret
        assert "cpu_model" in ret


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


def test_saltversion():
    """
    test saltversion core grain.
    """
    ret = core.saltversion()
    info = ret["saltversion"]
    assert isinstance(ret, dict)
    assert isinstance(info, str)


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


@pytest.mark.skip_unless_on_linux
def test_kernelparams_file_not_found_error():
    with patch("salt.utils.files.fopen", MagicMock()) as fopen_mock:
        fopen_mock.side_effect = FileNotFoundError()
        ret = core.kernelparams()
        assert ret == {}


@pytest.mark.skip_unless_on_linux
def test_kernelparams_oserror(caplog):
    with patch("salt.utils.files.fopen", MagicMock()) as fopen_mock:
        with caplog.at_level(logging.DEBUG):
            fopen_mock.side_effect = OSError()
            ret = core.kernelparams()
            assert ret == {}
            assert "Failed to read /proc/cmdline: " in caplog.messages


def test_linux_gpus(caplog):
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

    with patch("salt.grains.core.__opts__", {"enable_lspci": False}):
        ret = core._linux_gpu_data()
        assert ret == {}

    with patch("salt.grains.core.__opts__", {"enable_gpu_grains": False}):
        ret = core._linux_gpu_data()
        assert ret == {}

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

    with patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/sbin/lspci")
    ), patch.dict(core.__salt__, {"cmd.run": MagicMock(side_effect=OSError)}):
        ret = core._linux_gpu_data()
        assert ret == {"num_gpus": 0, "gpus": []}

    bad_gpu_data = textwrap.dedent(
        """
        Class: VGA compatible controller
        Vendor:	Advanced Micro Devices, Inc. [AMD/ATI]
        Device:	Vega [Radeon RX Vega]]
        SVendor; Evil Corp.
        SDevice: Graphics XXL
        Rev: c1
        NUMANode:	0"""
    )

    with patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/sbin/lspci")
    ), patch.dict(
        core.__salt__, {"cmd.run": MagicMock(return_value=bad_gpu_data)}
    ), caplog.at_level(
        logging.WARN
    ):
        core._linux_gpu_data()
        assert (
            "Error loading grains, unexpected linux_gpu_data output, "
            "check that you have a valid shell configured and permissions "
            "to run lspci command" in caplog.messages
        )


def test_get_server_id():
    expected = {"server_id": 94889706}
    with patch.dict(core.__opts__, {"id": "anid"}):
        assert core.get_server_id() == expected

    with patch.dict(core.__opts__, {"id": "otherid"}):
        assert core.get_server_id() != expected

    with patch.object(salt.utils.platform, "is_proxy", MagicMock(return_value=True)):
        assert core.get_server_id() == {}


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
        m.__enter__.return_value.read = lambda: (
            test_input.get(filename)  # pylint: disable=W0640
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


def test_append_domain():
    """
    test append_domain
    """

    assert core.append_domain() == {}

    with patch.object(salt.utils.platform, "is_proxy", MagicMock(return_value=True)):
        assert core.append_domain() == {}

    with patch("salt.grains.core.__opts__", {"append_domain": "example.com"}):
        assert core.append_domain() == {"append_domain": "example.com"}


def test_hostname():
    """
    test append_domain
    """

    with patch.object(salt.utils.platform, "is_proxy", MagicMock(return_value=True)):
        assert core.hostname() == {}

    with patch("salt.grains.core.__FQDN__", None), patch(
        "socket.gethostname", MagicMock(return_value=None)
    ), patch("salt.utils.network.get_fqhostname", MagicMock(return_value=None)):
        assert core.hostname() == {
            "localhost": None,
            "fqdn": "localhost.localdomain",
            "host": "localhost",
            "domain": "localdomain",
        }


def test_zmqversion():
    """
    test zmqversion
    """

    ret = core.zmqversion()
    assert "zmqversion" in ret

    with patch.dict("sys.modules", {"zmq": None}):
        ret = core.zmqversion()
        assert "zmqversion" not in ret


def test_saltpath():
    """
    test saltpath
    """

    ret = core.saltpath()
    assert "saltpath" in ret


def test_pythonexecutable():
    """
    test pythonexecutable
    """
    python_executable = sys.executable

    ret = core.pythonexecutable()
    assert "pythonexecutable" in ret
    assert ret["pythonexecutable"] == python_executable


def test_pythonpath():
    """
    test pythonpath
    """
    python_path = sys.path

    ret = core.pythonpath()
    assert "pythonpath" in ret
    assert ret["pythonpath"] == python_path


def test_pythonversion():
    """
    test pythonversion
    """
    python_version = [*sys.version_info]

    ret = core.pythonversion()
    assert "pythonversion" in ret
    assert ret["pythonversion"] == python_version


@pytest.mark.skip_unless_on_linux
def test_get_machine_id():
    """
    test get_machine_id
    """

    ret = core.get_machine_id()
    assert "machine_id" in ret

    with patch.object(os.path, "exists", return_value=False):
        ret = core.get_machine_id()
        assert ret == {}

    with patch.object(platform, "system", return_value="AIX"):
        with patch.object(core, "_aix_get_machine_id", return_value="AIX-MACHINE-ID"):
            ret = core.get_machine_id()
            assert ret == "AIX-MACHINE-ID"


def test_hwaddr_interfaces():
    """
    test hwaddr_interfaces
    """

    mock_get_interfaces = {
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
        "eth1": {
            "up": True,
            "hwaddr": "00:00:00:00:00:00",
            "inet": [
                {
                    "address": "0.0.0.0",
                    "netmask": "255.255.255.0",
                    "broadcast": "0.0.0.0",
                    "label": "wlo1",
                }
            ],
            "inet6": [],
        },
    }
    with patch.object(core, "_get_interfaces", return_value=mock_get_interfaces):
        ret = core.hwaddr_interfaces()
        assert "hwaddr_interfaces" in ret
        assert ret["hwaddr_interfaces"] == {
            "lo": "00:00:00:00:00:00",
            "eth1": "00:00:00:00:00:00",
        }


def test_id():
    """
    test id
    """
    ret = core.id_()
    assert "id" in ret

    with patch("salt.grains.core.__opts__", {"id": "test_id_minion_id"}):
        ret = core.id_()
        assert "id" in ret
        assert ret["id"] == "test_id_minion_id"


def test__linux_bin_exists():
    """
    test __linux_bin_exists
    """
    mock_retcode = [salt.exceptions.CommandExecutionError, 0]
    with patch.dict(
        core.__salt__, {"cmd.retcode": MagicMock(side_effect=mock_retcode)}
    ):
        ret = core._linux_bin_exists("ls")
        assert ret

    mock_retcode = salt.exceptions.CommandExecutionError
    mock_runall = [
        {"pid": 100, "retcode": 0, "stdout": "ls: /usr/bin/ls", "stderr": ""}
    ]
    with patch.dict(
        core.__salt__, {"cmd.retcode": MagicMock(side_effect=mock_retcode)}
    ):
        with patch.dict(
            core.__salt__, {"cmd.run_all": MagicMock(side_effect=mock_runall)}
        ):
            ret = core._linux_bin_exists("ls")
            assert ret

    mock_retcode = salt.exceptions.CommandExecutionError
    mock_runall = salt.exceptions.CommandExecutionError

    with patch.dict(
        core.__salt__, {"cmd.retcode": MagicMock(side_effect=mock_retcode)}
    ):
        with patch.dict(
            core.__salt__, {"cmd.run_all": MagicMock(side_effect=mock_runall)}
        ):
            ret = core._linux_bin_exists("ls")
            assert not ret


def test__parse_lsb_release():
    """
    test __parse_lsb_release
    """
    mock_lsb_file = """
DISTRIB_ID="ManjaroLinux"
DISTRIB_RELEASE="23.0.2"
DISTRIB_CODENAME="Uranos"
DISTRIB_DESCRIPTION="Manjaro Linux"
"""

    with patch("salt.utils.files.fopen", mock_open(read_data=mock_lsb_file)):
        ret = core._parse_lsb_release()
        assert ret == {
            "lsb_distrib_id": "ManjaroLinux",
            "lsb_distrib_release": "23.0.2",
            "lsb_distrib_codename": "Uranos",
            "lsb_distrib_description": "Manjaro Linux",
        }

    with patch("salt.utils.files.fopen", side_effect=OSError):
        ret = core._parse_lsb_release()
        assert ret == {}


def test__osx_gpudata():
    """
    test __osx_gpudata
    """
    mock_gpudata = """
Graphics/Displays:

    NVIDIA GeForce 320M:

      Chipset Model: NVIDIA GeForce 320M
      Type: GPU
      VRAM (Total): 256 MB
      Vendor: NVIDIA (0x10de)
      Device ID: 0x08a0
      Revision ID: 0x00a2
      ROM Revision: 3533
      Displays:
        Color LCD:
          Display Type: LCD
          Resolution: 1280 x 800
          UI Looks like: 1280 x 800
          Framebuffer Depth: 24-Bit Color (ARGB8888)
          Main Display: Yes
          Mirror: Off
          Online: Yes
          Automatically Adjust Brightness: Yes
          Connection Type: Internal

"""
    with patch.dict(core.__salt__, {"cmd.run": MagicMock(return_value=mock_gpudata)}):
        ret = core._osx_gpudata()
        assert ret["num_gpus"] == 1
        assert ret["gpus"] == [{"vendor": "nvidia", "model": "GeForce 320M"}]

    with patch.dict(core.__salt__, {"cmd.run": MagicMock(side_effect=OSError)}):
        ret = core._osx_gpudata()
        assert ret == {"num_gpus": 0, "gpus": []}


def test_get_master():
    """
    test get_master
    """
    ret = core.get_master()
    assert "master" in ret

    with patch("salt.grains.core.__opts__", {"master": "test_master_id"}):
        ret = core.get_master()
        assert "master" in ret
        assert ret["master"] == "test_master_id"


def test__selinux():
    """
    test _selinux
    """
    with patch.dict(
        core.__salt__,
        {
            "cmd.run": MagicMock(return_value="Enforcing"),
            "cmd.retcode": MagicMock(return_value=1),
        },
    ), patch.object(core, "_linux_bin_exists", MagicMock(return_value=False)):
        ret = core._selinux()
        assert ret == {"enabled": False}

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": MagicMock(return_value="Enforcing"),
            "cmd.retcode": MagicMock(return_value=0),
        },
    ), patch.object(core, "_linux_bin_exists", MagicMock(return_value=True)):
        ret = core._selinux()
        assert ret == {"enabled": True, "enforced": "Enforcing"}

    with patch.dict(
        core.__salt__,
        {
            "cmd.run": MagicMock(return_value="Disabled"),
            "cmd.retcode": MagicMock(return_value=0),
        },
    ), patch.object(core, "_linux_bin_exists", MagicMock(return_value=True)):
        ret = core._selinux()
        assert ret == {"enabled": True, "enforced": "Disabled"}


def test__systemd():
    """
    test _systemd
    """
    with patch.dict(
        core.__salt__,
        {
            "cmd.run": MagicMock(
                return_value=(
                    "systemd 254 (254.3-1)\n+PAM +AUDIT -SELINUX -APPARMOR -IMA +SMACK "
                    "+SECCOMP +GCRYPT +GNUTLS +OPENSSL +ACL +BLKID +CURL +ELFUTILS "
                    "+FIDO2 +IDN2 -IDN +IPTC +KMOD +LIBCRYPTSETUP +LIBFDISK +PCRE2 "
                    "-PWQUALITY +P11KIT -QRENCODE +TPM2 +BZIP2 +LZ4 +XZ +ZLIB +ZSTD "
                    "+BPF_FRAMEWORK +XKBCOMMON +UTMP -SYSVINIT default-hierarchy=unified"
                )
            ),
        },
    ):
        ret = core._systemd()
        assert "version" in ret
        assert "features" in ret
        assert ret["version"] == "254"
        assert ret["features"] == (
            "+PAM +AUDIT -SELINUX -APPARMOR -IMA +SMACK +SECCOMP +GCRYPT +GNUTLS +OPENSSL "
            "+ACL +BLKID +CURL +ELFUTILS +FIDO2 +IDN2 -IDN +IPTC +KMOD +LIBCRYPTSETUP "
            "+LIBFDISK +PCRE2 -PWQUALITY +P11KIT -QRENCODE +TPM2 +BZIP2 +LZ4 +XZ "
            "+ZLIB +ZSTD +BPF_FRAMEWORK +XKBCOMMON +UTMP -SYSVINIT default-hierarchy=unified"
        )


def test__clean_value_uuid(caplog):
    """
    test _clean_value uuid
    """
    ret = core._clean_value("key", None)
    assert not ret

    ret = core._clean_value("uuid", "49e40e2a-63b4-11ee-8c99-0242ac120002")
    assert ret == "49e40e2a-63b4-11ee-8c99-0242ac120002"

    with patch.object(uuid, "UUID", MagicMock()) as mock_uuid:
        with caplog.at_level(logging.TRACE):
            mock_uuid.side_effect = ValueError()
            ret = core._clean_value("uuid", "49e40e2a-63b4-11ee-8c99-0242ac120002")
            assert not ret
            assert (
                "HW uuid value 49e40e2a-63b4-11ee-8c99-0242ac120002 is an invalid UUID"
                in caplog.messages
            )


@pytest.mark.parametrize(
    "grain,value,expected",
    (
        ("kernelrelease", "10.0.14393", "10.0.14393"),
        ("kernelversion", "10.0.14393", "10.0.14393"),
        ("osversion", "10.0.14393", "10.0.14393"),
        ("osrelease", "2016Server", "2016Server"),
        ("osrelease", "to be filled", None),
        ("osmanufacturer", "Microsoft Corporation", "Microsoft Corporation"),
        ("manufacturer", "innotek GmbH", "innotek GmbH"),
        ("manufacturer", "to be filled", None),
        ("productname", "VirtualBox", "VirtualBox"),
        ("biosversion", "Default System BIOS", "Default System BIOS"),
        ("serialnumber", "0", None),
        (
            "osfullname",
            "Microsoft Windows Server 2016 Datacenter",
            "Microsoft Windows Server 2016 Datacenter",
        ),
        (
            "timezone",
            "(UTC-08:00) Pacific Time (US & Canada)",
            "(UTC-08:00) Pacific Time (US & Canada)",
        ),
        (
            "uuid",
            "d013f373-7331-4a9f-848b-72e379fbe7bf",
            "d013f373-7331-4a9f-848b-72e379fbe7bf",
        ),
        ("windowsdomain", "WORKGROUP", "WORKGROUP"),
        ("windowsdomaintype", "Workgroup", "Workgroup"),
        ("motherboard.productname", "VirtualBox", "VirtualBox"),
        ("motherboard.serialnumber", "0", None),
        ("model_name", "Macbook Pro", "Macbook Pro"),
        ("system_serialnumber", "W80322MWATM", "W80322MWATM"),
    ),
)
def test__clean_value_multiple_values(grain, value, expected):
    """
    test _clean_value multiple values
    """
    ret = core._clean_value(grain, value)
    assert ret == expected


def test__linux_init_system(caplog):
    """
    test _linux_init_system
    """
    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch("salt.utils.files.fopen", MagicMock()) as mock_fopen:
            mock_fopen.side_effect = OSError()
            ret = core._linux_init_system()
            assert ret == "unknown"

    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch("salt.utils.files.fopen", mock_open(read_data="init-not-found")):
            mock_fopen.side_effect = OSError()
            ret = core._linux_init_system()
            assert ret == "unknown"

    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch(
            "salt.utils.files.fopen", mock_open(read_data="/usr/sbin/supervisord")
        ):
            with patch("salt.utils.path.which", return_value="/usr/sbin/supervisord"):
                ret = core._linux_init_system()
                assert ret == "supervisord"

    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch(
            "salt.utils.files.fopen", mock_open(read_data="/usr/sbin/dumb-init")
        ):
            with patch(
                "salt.utils.path.which",
                side_effect=["/usr/sbin/dumb-init", "", "/usr/sbin/dumb-init"],
            ):
                ret = core._linux_init_system()
                assert ret == "dumb-init"

    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch("salt.utils.files.fopen", mock_open(read_data="/usr/sbin/tini")):
            with patch(
                "salt.utils.path.which",
                side_effect=["/usr/sbin/tini", "", "", "/usr/sbin/tini"],
            ):
                ret = core._linux_init_system()
                assert ret == "tini"

    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch("salt.utils.files.fopen", mock_open(read_data="runit")):
            with patch("salt.utils.path.which", side_effect=["", "", "", ""]):
                ret = core._linux_init_system()
                assert ret == "runit"

    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch("salt.utils.files.fopen", mock_open(read_data="/sbin/my_init")):
            with patch("salt.utils.path.which", side_effect=["", "", "", ""]):
                ret = core._linux_init_system()
                assert ret == "runit"

    with patch("os.stat", MagicMock()) as mock_os_stat:
        mock_os_stat.side_effect = OSError()
        with patch("salt.utils.files.fopen", mock_open(read_data="systemd")):
            with patch("salt.utils.path.which", side_effect=[IndexError(), "", "", ""]):
                with caplog.at_level(logging.WARNING):
                    ret = core._linux_init_system()
                    assert ret == "unknown"
                    assert (
                        "Unable to fetch data from /proc/1/cmdline" in caplog.messages
                    )


def test_default_gateway():
    """
    test default_gateway
    """

    with patch("salt.utils.path.which", return_value=""):
        ret = core.default_gateway()
        assert ret == {}

    with patch("salt.utils.path.which", return_value="/usr/sbin/ip"):
        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(return_value="")},
        ):

            ret = core.default_gateway()
            assert ret == {"ip_gw": False, "ip4_gw": False, "ip6_gw": False}

    with patch("salt.utils.path.which", return_value="/usr/sbin/ip"):
        ip4_route = """default via 172.23.5.3 dev enp7s0u2u4 proto dhcp src 172.23.5.173 metric 100
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1
172.19.0.0/16 dev docker_gwbridge proto kernel scope link src 172.19.0.1
172.23.5.0/24 dev enp7s0u2u4 proto kernel scope link src 172.23.5.173 metric 100
192.168.56.0/24 dev vboxnet0 proto kernel scope link src 192.168.56.1"""

        ip6_route = """2603:8001:b402:cc00::/64 dev enp7s0u2u4 proto ra metric 100 pref medium
fe80::/64 dev enp7s0u2u4 proto kernel metric 1024 pref medium
default via fe80::20d:b9ff:fe37:e65c dev enp7s0u2u4 proto ra metric 100 pref medium"""

        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=[ip4_route, ip6_route])},
        ):

            ret = core.default_gateway()
            assert ret == {
                "ip4_gw": "172.23.5.3",
                "ip6_gw": "fe80::20d:b9ff:fe37:e65c",
                "ip_gw": True,
            }

    with patch("salt.utils.path.which", return_value="/usr/sbin/ip"):

        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=[ip4_route, ip6_route])},
        ):

            ret = core.default_gateway()
            assert ret == {
                "ip4_gw": "172.23.5.3",
                "ip6_gw": "fe80::20d:b9ff:fe37:e65c",
                "ip_gw": True,
            }

    with patch("salt.utils.path.which", return_value="/usr/sbin/ip"):
        ip_route = """default
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1
172.19.0.0/16 dev docker_gwbridge proto kernel scope link src 172.19.0.1
172.23.5.0/24 dev enp7s0u2u4 proto kernel scope link src 172.23.5.173 metric 100
192.168.56.0/24 dev vboxnet0 proto kernel scope link src 192.168.56.1"""

        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=[ip_route])},
        ):

            ret = core.default_gateway()
            assert ret == {"ip_gw": True, "ip4_gw": True, "ip6_gw": False}


def test__osx_platform_data():
    """
    test _osx_platform_data
    """
    osx_platform_data = """Hardware:

    Hardware Overview:

      Model Name: MacBook Pro
      Model Identifier: MacBookPro7,1
      Processor Name: Intel Core 2 Duo
      Processor Speed: 2.4 GHz
      Number of Processors: 1
      Total Number of Cores: 2
      L2 Cache: 3 MB
      Memory: 16 GB
      System Firmware Version: 68.0.0.0.0
      OS Loader Version: 540.120.3~22
      SMC Version (system): 1.62f7
      Serial Number (system): W80322MWATM
      Hardware UUID: 3FA5BDA2-A740-5DF3-8A97-D9D4DB1CE24A
      Provisioning UDID: 3FA5BDA2-A740-5DF3-8A97-D9D4DB1CE24A
      Sudden Motion Sensor:
          State: Enabled"""

    with patch.dict(
        core.__salt__,
        {"cmd.run": MagicMock(return_value=osx_platform_data)},
    ):

        ret = core._osx_platform_data()
        assert ret == {
            "model_name": "MacBook Pro",
            "smc_version": "1.62f7",
            "system_serialnumber": "W80322MWATM",
        }

    osx_platform_data = """Hardware:

    Hardware Overview:

      Model Name: MacBook Pro
      Model Identifier: MacBookPro7,1
      Processor Name: Intel Core 2 Duo
      Processor Speed: 2.4 GHz
      Number of Processors: 1
      Total Number of Cores: 2
      L2 Cache: 3 MB
      Memory: 16 GB
      System Firmware Version: 68.0.0.0.0
      Boot ROM Version: 139.0.0.0.0
      OS Loader Version: 540.120.3~22
      SMC Version (system): 1.62f7
      Serial Number (system): W80322MWATM
      Hardware UUID: 3FA5BDA2-A740-5DF3-8A97-D9D4DB1CE24A
      Provisioning UDID: 3FA5BDA2-A740-5DF3-8A97-D9D4DB1CE24A
      Sudden Motion Sensor:
          State: Enabled"""

    with patch.dict(
        core.__salt__,
        {"cmd.run": MagicMock(return_value=osx_platform_data)},
    ):

        ret = core._osx_platform_data()
        assert ret == {
            "model_name": "MacBook Pro",
            "smc_version": "1.62f7",
            "system_serialnumber": "W80322MWATM",
            "boot_rom_version": "139.0.0.0.0",
        }


def test__parse_junos_showver():
    """
    test _parse_junos_showver
    """

    txt = b"""Hostname: R1-MX960-re0
Model: mx960
Junos: 18.2R3-S2.9
JUNOS Software Release [18.2R3-S2.9]"""

    ret = core._parse_junos_showver(txt)
    assert ret == {
        "model": "mx960",
        "osrelease": "18.2R3-S2.9",
        "osmajorrelease": "Junos: 18",
        "osrelease_info": ["Junos: 18", "2R3-S2", "9"],
    }

    txt = b"""Model: mx240
Junos: 15.1F2.8
JUNOS OS Kernel 64-bit  [20150814.313820_builder_stable_10]
JUNOS OS runtime [20150814.313820_builder_stable_10]
JUNOS OS time zone information [20150814.313820_builder_stable_10]
JUNOS OS 32-bit compatibility [20150814.313820_builder_stable_10]
JUNOS py base [20150814.204717_builder_junos_151_f2]
JUNOS OS crypto [20150814.313820_builder_stable_10]
JUNOS network stack and utilities [20150814.204717_builder_junos_151_f2]
JUNOS libs compat32 [20150814.204717_builder_junos_151_f2]
JUNOS runtime [20150814.204717_builder_junos_151_f2]
JUNOS platform support [20150814.204717_builder_junos_151_f2]
JUNOS modules [20150814.204717_builder_junos_151_f2]
JUNOS libs [20150814.204717_builder_junos_151_f2]
JUNOS daemons [20150814.204717_builder_junos_151_f2]
JUNOS FIPS mode utilities [20150814.204717_builder_junos_151_f2]"""

    ret = core._parse_junos_showver(txt)
    assert ret == {
        "model": "mx240",
        "osrelease": "15.1F2.8",
        "osmajorrelease": "Junos: 15",
        "osrelease_info": ["Junos: 15", "1F2", "8"],
        "kernelversion": "JUNOS OS Kernel 64-bit  [20150814.313820_builder_stable_10]",
        "kernelrelease": "20150814.313820_builder_stable_10",
    }


def test__bsd_cpudata_freebsd():
    """
    test _bsd_cpudata for FreeBSD
    """
    osdata = {"kernel": "FreeBSD"}
    mock_cmd_run = ["1", "amd64", "Intel(R) Core(TM) i7-10850H CPU @ 2.7.0GHz"]

    dmesg_mock = """Copyright (c) 1992-2021 The FreeBSD Project.
Copyright (c) 1979, 1980, 1983, 1986, 1988, 1989, 1991, 1992, 1993, 1994
    The Regents of the University of California. All rights reserved.
FreeBSD is a registered trademark of The FreeBSD Foundation.
FreeBSD 13.2-RELEASE releng/13.2-n254617-525ecfdad597 GENERIC amd64
FreeBSD clang version 14.0.5 (https://github.com/llvm/llvm-project.git llvmorg-14.0.5-0-gc12386ae247c)
VT(vga): text 80x25
CPU: Intel(R) Core(TM) i7-10850H CPU @ 2.70GHz (2712.13-MHz K8-class CPU)
  Origin="GenuineIntel"  Id=0xa0652  Family=0x6  Model=0xa5  Stepping=2
  Features=0x1783fbff<FPU,VME,DE,PSE,TSC,MSR,PAE,MCE,CX8,APIC,SEP,MTRR,PGE,MCA,CMOV,PAT,PSE36,MMX,FXSR,SSE,SSE2,HTT>
  Features2=0x5eda220b<SSE3,PCLMULQDQ,MON,SSSE3,CX16,PCID,SSE4.1,SSE4.2,MOVBE,POPCNT,AESNI,XSAVE,OSXSAVE,AVX,RDRAND>
  AMD Features=0x28100800<SYSCALL,NX,RDTSCP,LM>
  AMD Features2=0x121<LAHF,ABM,Prefetch>
  Structured Extended Features=0x842529<FSGSBASE,BMI1,AVX2,BMI2,INVPCID,NFPUSG,RDSEED,CLFLUSHOPT>
  Structured Extended Features3=0x30000400<MD_CLEAR,L1DFL,ARCH_CAP>
  TSC: P-state invariant
real memory  = 1073676288 (1023 MB)
avail memory = 995774464 (949 MB)
Event timer "LAPIC" quality 100
ACPI APIC Table: <VBOX   VBOXAPIC>
random: registering fast source Intel Secure Key RNG
random: fast provider: "Intel Secure Key RNG"
random: unblocking device.
ioapic0: MADT APIC ID 1 != hw id 0
ioapic0 <Version 2.0> irqs 0-23
random: entropy device external interface
kbd1 at kbdmux0
vtvga0: <VT VGA driver>
smbios0: <System Management BIOS> at iomem 0xfff60-0xfff7e
smbios0: Version: 2.5, BCD Revision: 2.5
aesni0: <AES-CBC,AES-CCM,AES-GCM,AES-ICM,AES-XTS>
acpi0: <VBOX VBOXXSDT>
acpi0: Power Button (fixed)
acpi0: Sleep Button (fixed)
cpu0: <ACPI CPU> on acpi0
attimer0: <AT timer> port 0x40-0x43,0x50-0x53 on acpi0
Timecounter "i8254" frequency 1193182 Hz quality 0
Event timer "i8254" frequency 1193182 Hz quality 100
Timecounter "ACPI-fast" frequency 3579545 Hz quality 900
acpi_timer0: <32-bit timer at 3.579545MHz> port 0x4008-0x400b on acpi0
pcib0: <ACPI Host-PCI bridge> port 0xcf8-0xcff on acpi0
pci0: <ACPI PCI bus> on pcib0
isab0: <PCI-ISA bridge> at device 1.0 on pci0
isa0: <ISA bus> on isab0
atapci0: <Intel PIIX4 UDMA33 controller> port 0x1f0-0x1f7,0x3f6,0x170-0x177,0x376,0xd000-0xd00f at device 1.1 on pci0
ata0: <ATA channel> at channel 0 on atapci0
ata1: <ATA channel> at channel 1 on atapci0
vgapci0: <VGA-compatible display> port 0xd010-0xd01f mem 0xe0000000-0xe3ffffff,0xf0000000-0xf01fffff irq 18 at device 2.0 on pci0
vgapci0: Boot video device
em0: <Intel(R) Legacy PRO/1000 MT 82540EM> port 0xd020-0xd027 mem 0xf0200000-0xf021ffff irq 19 at device 3.0 on pci0
em0: Using 1024 TX descriptors and 1024 RX descriptors
em0: Ethernet address: 08:00:27:ae:76:42
em0: netmap queues/slots: TX 1/1024, RX 1/1024
pcm0: <Intel ICH (82801AA)> port 0xd100-0xd1ff,0xd200-0xd23f irq 21 at device 5.0 on pci0
pcm0: <SigmaTel STAC9700/83/84 AC97 Codec>
ohci0: <Apple KeyLargo/Intrepid USB controller> mem 0xf0804000-0xf0804fff irq 22 at device 6.0 on pci0
usbus0 on ohci0
pci0: <bridge> at device 7.0 (no driver attached)
ehci0: <Intel 82801FB (ICH6) USB 2.0 controller> mem 0xf0805000-0xf0805fff irq 19 at device 11.0 on pci0
usbus1: EHCI version 1.0
usbus1 on ehci0
battery0: <ACPI Control Method Battery> on acpi0
acpi_acad0: <AC Adapter> on acpi0
atkbdc0: <Keyboard controller (i8042)> port 0x60,0x64 irq 1 on acpi0
atkbd0: <AT Keyboard> irq 1 on atkbdc0
kbd0 at atkbd0
atkbd0: [GIANT-LOCKED]
psm0: <PS/2 Mouse> irq 12 on atkbdc0
psm0: [GIANT-LOCKED]
WARNING: Device "psm" is Giant locked and may be deleted before FreeBSD 14.0.
psm0: model IntelliMouse Explorer, device ID 4
orm0: <ISA Option ROM> at iomem 0xc0000-0xc7fff pnpid ORM0000 on isa0
vga0: <Generic ISA VGA> at port 0x3c0-0x3df iomem 0xa0000-0xbffff pnpid PNP0900 on isa0
atrtc0: <AT realtime clock> at port 0x70 irq 8 on isa0
atrtc0: registered as a time-of-day clock, resolution 1.000000s
Event timer "RTC" frequency 32768 Hz quality 0
atrtc0: non-PNP ISA device will be removed from GENERIC in FreeBSD 14.
Timecounter "TSC-low" frequency 1356006904 Hz quality 1000
Timecounters tick every 10.000 msec
ZFS filesystem version: 5
ZFS storage pool version: features support (5000)
usbus0: 12Mbps Full Speed USB v1.0
usbus1: 480Mbps High Speed USB v2.0
pcm0: measured ac97 link rate at 44717 Hz
ugen1.1: <Intel EHCI root HUB> at usbus1
uhub0 on usbus1
uhub0: <Intel EHCI root HUB, class 9/0, rev 2.00/1.00, addr 1> on usbus1
ugen0.1: <Apple OHCI root HUB> at usbus0
uhub1 on usbus0
uhub1: <Apple OHCI root HUB, class 9/0, rev 1.00/1.00, addr 1> on usbus0
Trying to mount root from zfs:zroot/ROOT/default []...
uhub1: 12 ports with 12 removable, self powered
ada0 at ata0 bus 0 scbus0 target 0 lun 0
ada0: <VBOX HARDDISK 1.0> ATA-6 device
ada0: Serial Number VBf824a3f1-4ad9d778
ada0: 33.300MB/s transfers (UDMA2, PIO 65536bytes)
ada0: 16384MB (33554432 512 byte sectors)
Root mount waiting for: usbus1
Root mount waiting for: usbus1
Root mount waiting for: usbus1
Root mount waiting for: usbus1
Root mount waiting for: usbus1
uhub0: 12 ports with 12 removable, self powered
intsmb0: <Intel PIIX4 SMBUS Interface> irq 23 at device 7.0 on pci0
intsmb0: intr IRQ 9 enabled revision 0
smbus0: <System Management Bus> on intsmb0
lo0: link state changed to UP
em0: link state changed to UP"""

    with patch("salt.utils.path.which", return_value="/sbin/sysctl"):
        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            with patch("os.path.isfile", return_value=True):
                with patch("salt.utils.files.fopen", mock_open(read_data=dmesg_mock)):
                    ret = core._bsd_cpudata(osdata)
                    assert "num_cpus" in ret
                    assert ret["num_cpus"] == 1

                    assert "cpuarch" in ret
                    assert ret["cpuarch"] == "amd64"

                    assert "cpu_model" in ret
                    assert (
                        ret["cpu_model"] == "Intel(R) Core(TM) i7-10850H CPU @ 2.7.0GHz"
                    )

                    assert "cpu_flags" in ret
                    assert ret["cpu_flags"] == [
                        "FPU",
                        "VME",
                        "DE",
                        "PSE",
                        "TSC",
                        "MSR",
                        "PAE",
                        "MCE",
                        "CX8",
                        "APIC",
                        "SEP",
                        "MTRR",
                        "PGE",
                        "MCA",
                        "CMOV",
                        "PAT",
                        "PSE36",
                        "MMX",
                        "FXSR",
                        "SSE",
                        "SSE2",
                        "HTT",
                        "SSE3",
                        "PCLMULQDQ",
                        "MON",
                        "SSSE3",
                        "CX16",
                        "PCID",
                        "SSE4.1",
                        "SSE4.2",
                        "MOVBE",
                        "POPCNT",
                        "AESNI",
                        "XSAVE",
                        "OSXSAVE",
                        "AVX",
                        "RDRAND",
                        "SYSCALL",
                        "NX",
                        "RDTSCP",
                        "LM",
                        "LAHF",
                        "ABM",
                        "Prefetch",
                        "FSGSBASE",
                        "BMI1",
                        "AVX2",
                        "BMI2",
                        "INVPCID",
                        "NFPUSG",
                        "RDSEED",
                        "CLFLUSHOPT",
                        "MD_CLEAR",
                        "L1DFL",
                        "ARCH_CAP",
                    ]


def test__bsd_cpudata_netbsd():
    """
    test _bsd_cpudata for NetBSD
    """
    osdata = {"kernel": "NetBSD"}
    mock_cpuctl_identify = """cpu0: highest basic info 00000016
cpu0: highest extended info 80000008
cpu0: "Intel(R) Core(TM) i7-10850H CPU @ 2.70GHz"
cpu0: Intel 10th gen Core (Comet Lake) (686-class), 2753.71 MHz
cpu0: family 0x6 model 0xa5 stepping 0x2 (id 0xa0652)
cpu0: features 0x178bfbff<FPU,VME,DE,PSE,TSC,MSR,PAE,MCE,CX8,APIC,SEP,MTRR,PGE>
cpu0: features 0x178bfbff<MCA,CMOV,PAT,PSE36,CLFSH,MMX,FXSR,SSE,SSE2,HTT>
cpu0: features1 0x5eda220b<SSE3,PCLMULQDQ,MONITOR,SSSE3,CX16,PCID,SSE41,SSE42>
cpu0: features1 0x5eda220b<MOVBE,POPCNT,AES,XSAVE,OSXSAVE,AVX,RDRAND>
cpu0: features2 0x28100800<SYSCALL/SYSRET,XD,RDTSCP,EM64T>
cpu0: features3 0x121<LAHF,LZCNT,PREFETCHW>
cpu0: features5 0x842529<FSGSBASE,BMI1,AVX2,BMI2,INVPCID,FPUCSDS,RDSEED>
cpu0: features5 0x842529<CLFLUSHOPT>
cpu0: features7 0x30000400<MD_CLEAR,L1D_FLUSH,ARCH_CAP>
cpu0: xsave features 0x7<x87,SSE,AVX>
cpu0: xsave area size: current 832, maximum 832, xgetbv enabled
cpu0: enabled xsave 0x7<x87,SSE,AVX>
cpu0: I-cache: 32KB 64B/line 8-way, D-cache: 32KB 64B/line 8-way
cpu0: L2 cache: 256KB 64B/line 4-way
cpu0: L3 cache: 12MB 64B/line 16-way
cpu0: 64B prefetching
cpu0: ITLB: 64 4KB entries 8-way, 8 2M/4M entries
cpu0: DTLB: 64 4KB entries 4-way, 4 1GB entries 4-way
cpu0: L2 STLB: 1536 4KB entries 6-way
cpu0: Initial APIC ID 0
cpu0: Cluster/Package ID 0
cpu0: Core ID 0
cpu0: SMT ID 0
cpu0: monitor-line size 64
cpu0: SEF highest subleaf 00000000
cpu0: Power Management features: 0x100<ITSC>
cpu0: microcode version 0x0, platform ID 0"""
    mock_cmd_run = [
        "1",
        "amd64",
        "Intel(R) Core(TM) i7-10850H CPU @ 2.7.0GHz",
        mock_cpuctl_identify,
    ]

    with patch("salt.utils.path.which", return_value="/sbin/sysctl"):
        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._bsd_cpudata(osdata)
            assert "num_cpus" in ret
            assert ret["num_cpus"] == 1

            assert "cpuarch" in ret
            assert ret["cpuarch"] == "amd64"

            assert "cpu_model" in ret
            assert ret["cpu_model"] == "Intel(R) Core(TM) i7-10850H CPU @ 2.7.0GHz"


def test__bsd_cpudata_darwin():
    """
    test _bsd_cpudata for Darwin
    """
    osdata = {"kernel": "Darwin"}
    mock_cmd_run = [
        "1",
        "x86_64",
        "Intel(R) Core(TM)2 Duo CPU     P8600  @ 2.40GHz",
        "FPU VME DE PSE TSC MSR PAE MCE CX8 APIC SEP MTRR PGE MCA CMOV PAT PSE36 CLFSH DS ACPI MMX FXSR SSE SSE2 SS HTT TM PBE SSE3 DTES64 MON DSCPL VMX SMX EST TM2 SSSE3 CX16 TPR PDCM SSE4.1 XSAVE",
    ]

    with patch("salt.utils.path.which", return_value="/sbin/sysctl"):
        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._bsd_cpudata(osdata)
            assert "num_cpus" in ret
            assert ret["num_cpus"] == 1

            assert "cpuarch" in ret
            assert ret["cpuarch"] == "x86_64"

            assert "cpu_model" in ret
            assert ret["cpu_model"] == "Intel(R) Core(TM)2 Duo CPU     P8600  @ 2.40GHz"

            assert "cpu_flags" in ret
            assert ret["cpu_flags"] == [
                "FPU",
                "VME",
                "DE",
                "PSE",
                "TSC",
                "MSR",
                "PAE",
                "MCE",
                "CX8",
                "APIC",
                "SEP",
                "MTRR",
                "PGE",
                "MCA",
                "CMOV",
                "PAT",
                "PSE36",
                "CLFSH",
                "DS",
                "ACPI",
                "MMX",
                "FXSR",
                "SSE",
                "SSE2",
                "SS",
                "HTT",
                "TM",
                "PBE",
                "SSE3",
                "DTES64",
                "MON",
                "DSCPL",
                "VMX",
                "SMX",
                "EST",
                "TM2",
                "SSSE3",
                "CX16",
                "TPR",
                "PDCM",
                "SSE4.1",
                "XSAVE",
            ]


def test__bsd_cpudata_openbsd():
    """
    test _bsd_cpudata for OpenBSD
    """
    osdata = {"kernel": "OpenBSD"}
    mock_cmd_run = ["1", "amd64", "Intel(R) Core(TM) i7-10850H CPU @ 2.7.0GHz", "amd64"]

    with patch("salt.utils.path.which", return_value="/sbin/sysctl"):
        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._bsd_cpudata(osdata)
            assert "num_cpus" in ret
            assert ret["num_cpus"] == 1

            assert "cpuarch" in ret
            assert ret["cpuarch"] == "amd64"

            assert "cpu_model" in ret
            assert ret["cpu_model"] == "Intel(R) Core(TM) i7-10850H CPU @ 2.7.0GHz"


def test__netbsd_gpu_data():
    """
    test _netbsd_gpu_data
    """
    mock_pcictl = """000:00:0: Intel 82441FX (PMC) PCI and Memory Controller (host bridge, revision 0x02)
000:01:0: Intel 82371SB (PIIX3) PCI-ISA Bridge (ISA bridge)
000:01:1: Intel 82371AB (PIIX4) IDE Controller (IDE mass storage, interface 0x8a, revision 0x01)
000:02.0: VGA compatible controller: Intel Corporation CometLake-H GT2 [UHD Graphics] (rev 05)
000:02:0: Intel CometLake-H GT2 [UHD Graphics] (VGA display)
000:03:0: Intel i82540EM 1000baseT Ethernet (ethernet network, revision 0x02)
000:04:0: VirtualBox Guest Service (miscellaneous system)
000:05:0: Intel 82801AA AC-97 Audio Controller (audio multimedia, revision 0x01)
000:06:0: Apple Computer Intrepid USB Controller (USB serial bus, OHCI)
000:07:0: Intel 82371AB (PIIX4) Power Management Controller (miscellaneous bridge, revision 0x08)
000:11:0: Intel 82801FB/FR USB EHCI Controller (USB serial bus, EHCI)"""

    with patch.dict(
        core.__salt__,
        {"cmd.run": MagicMock(return_value=mock_pcictl)},
    ):
        ret = core._netbsd_gpu_data()
        assert ret == {
            "num_gpus": 1,
            "gpus": [{"vendor": "Intel", "model": "CometLake-H GT2 [UHD Graphics]"}],
        }

    with patch.dict(core.__salt__, {"cmd.run": MagicMock(side_effect=OSError)}):
        ret = core._netbsd_gpu_data()
        assert ret == {"gpus": [], "num_gpus": 0}


def test__bsd_memdata():
    """
    test _bsd_memdata
    """
    osdata = {"kernel": "OpenBSD"}

    with patch("salt.utils.path.which", side_effect=["/sbin/sysctl", "/sbin/swapctl"]):

        mock_cmd_run = [
            "1073278976",
            "total: 1048559 KBytes allocated, 0 KBytes used, 1048559 KBytes available",
        ]
        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._bsd_memdata(osdata)
            assert ret == {"mem_total": 1023, "swap_total": 0}

    osdata = {"kernel": "NetBSD"}

    with patch("salt.utils.path.which", side_effect=["/sbin/sysctl", "/sbin/swapctl"]):

        mock_cmd_run = [
            "1073278976",
            "total: 1048559 KBytes allocated, 0 KBytes used, 1048559 KBytes available",
        ]

        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._bsd_memdata(osdata)
            assert ret == {"mem_total": 1023, "swap_total": 0}

    with patch("salt.utils.path.which", side_effect=["/sbin/sysctl", "/sbin/swapctl"]):

        mock_cmd_run = [
            "-",
            "1073278976",
            "total: 1048559 KBytes allocated, 0 KBytes used, 1048559 KBytes available",
        ]

        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._bsd_memdata(osdata)
            assert ret == {"mem_total": 1023, "swap_total": 0}

    with patch("salt.utils.path.which", side_effect=["/sbin/sysctl", "/sbin/swapctl"]):

        mock_cmd_run = ["-", "1073278976", "no swap devices configured"]

        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._bsd_memdata(osdata)
            assert ret == {"mem_total": 1023, "swap_total": 0}

    with patch("salt.utils.path.which", side_effect=["/sbin/sysctl", "/sbin/swapctl"]):

        mock_cmd_run = ["-", "1073278976", "no swap devices configured"]

        with patch.dict(
            core.__salt__,
            {"cmd.run": MagicMock(side_effect=mock_cmd_run)},
        ):
            ret = core._memdata(osdata)
            assert ret == {"mem_total": 1023, "swap_total": 0}


def test__ps():
    """
    test _ps
    """
    osdata = {"os_family": ""}

    for bsd in ["FreeBSD", "NetBSD", "OpenBSD", "MacOS"]:
        osdata = {"os": bsd}
        ret = core._ps(osdata)
        assert ret == {"ps": "ps auxwww"}

    osdata = {"os_family": "Solaris", "os": ""}
    ret = core._ps(osdata)
    assert ret == {"ps": "/usr/ucb/ps auxwww"}

    osdata = {"os": "Windows", "os_family": ""}
    ret = core._ps(osdata)
    assert ret == {"ps": "tasklist.exe"}

    osdata = {"os": "", "os_family": "AIX"}
    ret = core._ps(osdata)
    assert ret == {"ps": "/usr/bin/ps auxww"}

    osdata = {"os": "", "os_family": "NILinuxRT"}
    ret = core._ps(osdata)
    assert ret == {"ps": "ps -o user,pid,ppid,tty,time,comm"}

    osdata = {"os": "", "os_family": "", "virtual": "openvzhn"}
    ret = core._ps(osdata)
    assert ret == {
        "ps": (
            'ps -fH -p $(grep -l "^envID:[[:space:]]*0\\$" '
            '/proc/[0-9]*/status | sed -e "s=/proc/\\([0-9]*\\)/.*=\\1=")  '
            "| awk '{ $7=\"\"; print }'"
        )
    }

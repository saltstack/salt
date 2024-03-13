"""
    Test for the salt.modules.tuned
"""

import pytest

from salt.modules import tuned
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {tuned: {}}


def test_v_241():
    """
    Test the list_ function for older tuned-adm (v2.4.1)
    as shipped with CentOS-6
    """
    tuned_list = """Available profiles:
- throughput-performance
- virtual-guest
- latency-performance
- laptop-battery-powersave
- laptop-ac-powersave
- virtual-host
- desktop-powersave
- server-powersave
- spindown-disk
- sap
- enterprise-storage
- default
Current active profile: throughput-performance"""
    mock_cmd = MagicMock(return_value=tuned_list)
    with patch.dict(tuned.__salt__, {"cmd.run": mock_cmd}):
        assert tuned.list_() == [
            "throughput-performance",
            "virtual-guest",
            "latency-performance",
            "laptop-battery-powersave",
            "laptop-ac-powersave",
            "virtual-host",
            "desktop-powersave",
            "server-powersave",
            "spindown-disk",
            "sap",
            "enterprise-storage",
            "default",
        ]


def test_v_271():
    """
    Test the list_ function for newer tuned-adm (v2.7.1)
    as shipped with CentOS-7
    """
    tuned_list = """Available profiles:
- balanced                    - General non-specialized tuned profile
- desktop                     - Optmize for the desktop use-case
- latency-performance         - Optimize for deterministic performance
- network-latency             - Optimize for deterministic performance
- network-throughput          - Optimize for streaming network throughput.
- powersave                   - Optimize for low power-consumption
- throughput-performance      - Broadly applicable tuning that provides--
- virtual-guest               - Optimize for running inside a virtual-guest.
- virtual-host                - Optimize for running KVM guests
Current active profile: virtual-guest
"""
    mock_cmd = MagicMock(return_value=tuned_list)
    with patch.dict(tuned.__salt__, {"cmd.run": mock_cmd}):
        assert tuned.list_() == [
            "balanced",
            "desktop",
            "latency-performance",
            "network-latency",
            "network-throughput",
            "powersave",
            "throughput-performance",
            "virtual-guest",
            "virtual-host",
        ]


def test_v_2110_with_warnings():
    """
    Test the list_ function for newer tuned-adm (v2.11.0)
    as shipped with CentOS-7.8 when warnings are emitted
    """
    tuned_list = """Available profiles:
- balanced                    - General non-specialized tuned profile
- desktop                     - Optmize for the desktop use-case
- latency-performance         - Optimize for deterministic performance
- network-latency             - Optimize for deterministic performance
- network-throughput          - Optimize for streaming network throughput.
- powersave                   - Optimize for low power-consumption
- throughput-performance      - Broadly applicable tuning that provides--
- virtual-guest               - Optimize for running inside a virtual-guest.
- virtual-host                - Optimize for running KVM guests
Current active profile: virtual-guest

** COLLECTED WARNINGS **
No SMBIOS nor DMI entry point found, sorry.
** END OF WARNINGS **
"""
    mock_cmd = MagicMock(return_value=tuned_list)
    with patch.dict(tuned.__salt__, {"cmd.run": mock_cmd}):
        assert tuned.list_() == [
            "balanced",
            "desktop",
            "latency-performance",
            "network-latency",
            "network-throughput",
            "powersave",
            "throughput-performance",
            "virtual-guest",
            "virtual-host",
        ]


def test_none():
    """ """
    ret = {
        "pid": 12345,
        "retcode": 1,
        "stderr": (
            "stderr: Cannot talk to Tuned daemon via DBus. Is Tuned daemon running?"
        ),
        "stdout": "No current active profile.",
    }
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(tuned.__salt__, {"cmd.run_all": mock_cmd}):
        assert tuned.active()["retcode"] != 0


def test_active_balanced():
    ret = {
        "pid": 12345,
        "retcode": 0,
        "stderr": "",
        "stdout": "Current active profile: balanced",
    }
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(tuned.__salt__, {"cmd.run_all": mock_cmd}):
        assert tuned.active()["stdout"] == "balanced"


def test_off():
    ret = {
        "pid": 12345,
        "retcode": 0,
        "stderr": "",
        "stdout": "",
    }
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(tuned.__salt__, {"cmd.run_all": mock_cmd}):
        assert tuned.off()["retcode"] == 0


def test_profile_valid():
    ret = {
        "pid": 12345,
        "retcode": 0,
        "stderr": "",
        "stdout": "",
    }
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(tuned.__salt__, {"cmd.run_all": mock_cmd}):
        assert tuned.profile("balanced")["stdout"] == "balanced"


def test_profile_noexist():
    ret = {
        "pid": 12345,
        "retcode": 1,
        "stderr": "Requested profile 'noexist' doesn't exist.",
        "stdout": "",
    }
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(tuned.__salt__, {"cmd.run_all": mock_cmd}):
        assert (
            tuned.profile("noexist")["stderr"]
            == "Requested profile 'noexist' doesn't exist."
        )


def test_profile_invalid():
    ret = {
        "pid": 12345,
        "retcode": 1,
        "stderr": """Cannot load profile(s) 'invalid':
         ("Cannot parse '/usr/lib/tuned/invalid/tuned.conf'.",
          DuplicateError('Duplicate keyword name at line 4.'))""",
        "stdout": "",
    }
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(tuned.__salt__, {"cmd.run_all": mock_cmd}):
        assert (
            tuned.profile("invalid")["stderr"].startswith("Cannot load profile") is True
        )

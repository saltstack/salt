import pytest

import salt.modules.dnfmodule as dnfmodule
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.fixture
def configure_loader_modules():
    return {
        dnfmodule: {
            "__grains__": {"os_family": "RedHat"},
            "__context__": {},
            "__salt__": {},
        },
    }


# A representative ``dnf module list`` table, including the per-repository
# headers, metadata noise and trailing hint that the parser must ignore.
MODULE_LIST = """\
Updating Subscription Management repositories.
Last metadata expiration check: 0:10:00 ago on Sun 01 Jun 2025 12:00:00 AM UTC.
Rocky Linux 8 - AppStream
Name             Stream     Profiles               Summary
nodejs           18 [d][e]  common [d] [i]         Javascript runtime
postgresql       15         client, server [d]     PostgreSQL server

Rocky Linux 8 - PowerTools
Name      Stream    Profiles    Summary
ruby      2.5 [x]   common      An interpreter of object-oriented scripting

Hint: [d]efault, [e]nabled, [x]disabled, [i]nstalled, [a]ctive
"""


def _dnf_result(stdout="", retcode=0, stderr=""):
    return {"stdout": stdout, "stderr": stderr, "retcode": retcode}


def test_virtual_requires_redhat():
    with patch.dict(dnfmodule.__grains__, {"os_family": "Debian"}):
        ret = dnfmodule.__virtual__()
    assert ret[0] is False


def test_virtual_requires_dnf_binary():
    with patch.object(dnfmodule, "_dnf", MagicMock(return_value=None)):
        ret = dnfmodule.__virtual__()
    assert ret[0] is False


def test_virtual_available():
    with patch.object(dnfmodule, "_dnf", MagicMock(return_value="/usr/bin/dnf")):
        assert dnfmodule.__virtual__() == "dnfmodule"


def test_parse_module_list_ignores_noise_and_extracts_flags():
    modules = dnfmodule._parse_module_list(MODULE_LIST)
    by_name = {m["name"]: m for m in modules}

    # Repository headers and metadata lines must not appear as modules.
    assert set(by_name) == {"nodejs", "postgresql", "ruby"}

    assert by_name["nodejs"]["stream"] == "18"
    assert by_name["nodejs"]["default"] is True
    assert by_name["nodejs"]["enabled"] is True
    assert by_name["nodejs"]["installed"] is True
    assert by_name["nodejs"]["disabled"] is False

    assert by_name["postgresql"]["enabled"] is False
    assert by_name["postgresql"]["default"] is False

    assert by_name["ruby"]["disabled"] is True
    assert by_name["ruby"]["enabled"] is False


def test_list_passes_filters_and_module_name():
    mock = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    with patch.object(dnfmodule, "_call_dnf", mock):
        dnfmodule.list_(name="nodejs:18", enabled=True)
    args = mock.call_args[0][0]
    assert "--enabled" in args
    # The stream suffix is stripped from the module name.
    assert args[-1] == "nodejs"


def test_is_enabled_true():
    mock = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    with patch.object(dnfmodule, "_call_dnf", mock):
        assert dnfmodule.is_enabled("nodejs:18") is True
        assert dnfmodule.is_enabled("nodejs") is True


def test_is_enabled_wrong_stream():
    mock = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    with patch.object(dnfmodule, "_call_dnf", mock):
        assert dnfmodule.is_enabled("nodejs:14") is False


def test_is_disabled_true():
    mock = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    with patch.object(dnfmodule, "_call_dnf", mock):
        assert dnfmodule.is_disabled("ruby") is True
        assert dnfmodule.is_disabled("nodejs") is False


def test_is_installed_true():
    mock = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    with patch.object(dnfmodule, "_call_dnf", mock):
        assert dnfmodule.is_installed("nodejs") is True
        assert dnfmodule.is_installed("postgresql") is False


def test_enabled_stream():
    mock = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    with patch.object(dnfmodule, "_call_dnf", mock):
        assert dnfmodule.enabled_stream("nodejs") == "18"
        assert dnfmodule.enabled_stream("nodejs:18") == "18"
        assert dnfmodule.enabled_stream("postgresql") is None


def test_split_name_requires_name():
    with pytest.raises(SaltInvocationError):
        dnfmodule._split_name("")


def test_split_name_variants():
    assert dnfmodule._split_name("nodejs") == ("nodejs", None)
    assert dnfmodule._split_name("nodejs:18") == ("nodejs", "18")
    assert dnfmodule._split_name("nodejs:18/common") == ("nodejs", "18")


def test_enable_builds_command():
    mock = MagicMock(return_value=_dnf_result(retcode=0))
    with patch.object(dnfmodule, "_call_dnf", mock):
        assert dnfmodule.enable("nodejs:18") is True
    assert mock.call_args[0][0] == ["-y", "module", "enable", "nodejs:18"]


def test_enable_conflict_raises_clean_error():
    # nodejs:18 is enabled in MODULE_LIST; enabling a different stream conflicts.
    mock = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    with patch.object(dnfmodule, "_call_dnf", mock):
        with pytest.raises(CommandExecutionError) as exc:
            dnfmodule.enable("nodejs:14")
    assert "already has stream '18' enabled" in str(exc.value)


def test_enable_switch_resets_then_enables():
    calldnf = MagicMock(return_value=_dnf_result(stdout=MODULE_LIST))
    reset = MagicMock(return_value=True)
    with patch.object(dnfmodule, "_call_dnf", calldnf), patch.object(
        dnfmodule, "reset", reset
    ):
        assert dnfmodule.enable("nodejs:14", switch=True) is True
    reset.assert_called_once_with("nodejs")
    # The final dnf invocation is the enable action for the requested stream.
    assert calldnf.call_args[0][0] == ["-y", "module", "enable", "nodejs:14"]


def test_disable_and_reset_actions():
    mock = MagicMock(return_value=_dnf_result(retcode=0))
    with patch.object(dnfmodule, "_call_dnf", mock):
        dnfmodule.disable("nodejs")
        assert mock.call_args[0][0] == ["-y", "module", "disable", "nodejs"]
        dnfmodule.reset("nodejs")
        assert mock.call_args[0][0] == ["-y", "module", "reset", "nodejs"]


def test_action_raises_on_failure():
    mock = MagicMock(return_value=_dnf_result(retcode=1, stderr="boom"))
    with patch.object(dnfmodule, "_call_dnf", mock):
        with pytest.raises(CommandExecutionError):
            dnfmodule.enable("nodejs:18")

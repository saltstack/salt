import pytest

import salt.modules.file as filemod
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock

EQUIV_ERR = (
    "ValueError: File spec /etc/systemd/system/tmp.mount.d/options.conf "
    "conflicts with equivalency rule '/etc/systemd/system /usr/lib/systemd/system'"
)


@pytest.fixture
def configure_loader_modules():
    return {filemod: {"__salt__": {}, "__opts__": {"test": False}}}


def _salt(add_result):
    return {
        "selinux.fcontext_add_policy": MagicMock(return_value=add_result),
        "cmd.retcode": MagicMock(return_value=0),
        "cmd.run_all": MagicMock(
            return_value={
                "retcode": 0,
                "stdout": "system_u:object_r:systemd_unit_file_t:s0",
            }
        ),
    }


def test_set_selinux_context_persist_equivalency_rule():
    """
    An equivalency rule must not abort the label change (issue #62875)
    """
    salt_mock = _salt({"retcode": 1, "stdout": "", "stderr": EQUIV_ERR})
    filemod.__salt__.update(salt_mock)
    ret = filemod.set_selinux_context(
        "/etc/systemd/system/tmp.mount.d/options.conf",
        user="system_u",
        role="object_r",
        type="systemd_unit_file_t",
        range="s0",
        persist=True,
    )
    assert ret == "system_u:object_r:systemd_unit_file_t:s0"
    salt_mock["cmd.retcode"].assert_called_once()


def test_set_selinux_context_persist_other_error_raises():
    filemod.__salt__.update(_salt({"retcode": 1, "stdout": "", "stderr": "boom"}))
    with pytest.raises(CommandExecutionError):
        filemod.set_selinux_context("/tmp/x", type="etc_t", persist=True)

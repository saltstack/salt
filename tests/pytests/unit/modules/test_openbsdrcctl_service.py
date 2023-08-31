import pytest

import salt.modules.openbsdrcctl_service as openbsdrcctl
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def rcctl():
    cmd = "rcctl"
    with patch.object(openbsdrcctl, "_cmd", return_value=cmd):
        yield cmd


@pytest.fixture
def retcode_mock():
    return MagicMock()


@pytest.fixture
def configure_loader_modules(retcode_mock):
    return {
        openbsdrcctl: {
            "__salt__": {"cmd.retcode": retcode_mock},
        },
    }


def test_available(retcode_mock, rcctl):
    retcode_mock.return_value = 0
    assert openbsdrcctl.available("test") is True
    retcode_mock.assert_called_with("{} get test".format(rcctl), ignore_retcode=True)
    retcode_mock.return_value = 2
    assert openbsdrcctl.available("test") is False
    retcode_mock.assert_called_with("{} get test".format(rcctl), ignore_retcode=True)


def test_status(retcode_mock, rcctl):
    retcode_mock.return_value = 0
    assert openbsdrcctl.status("test") is True
    retcode_mock.assert_called_with("{} check test".format(rcctl), ignore_retcode=True)
    retcode_mock.return_value = 2
    assert openbsdrcctl.status("test") is False
    retcode_mock.assert_called_with("{} check test".format(rcctl), ignore_retcode=True)


def test_disabled(retcode_mock, rcctl):
    retcode_mock.return_value = 0
    assert openbsdrcctl.disabled("test") is False
    retcode_mock.assert_called_with(
        "{} get test status".format(rcctl), ignore_retcode=True
    )
    retcode_mock.return_value = 2
    assert openbsdrcctl.disabled("test") is True
    retcode_mock.assert_called_with(
        "{} get test status".format(rcctl), ignore_retcode=True
    )


def test_enabled(retcode_mock, rcctl):
    retcode_mock.return_value = 0
    flags_return = {"flag1": "value1"}
    stdout_mock = MagicMock(return_value=flags_return)
    salt_mock = {
        "cmd.run_stdout": stdout_mock,
        "config.option": MagicMock(),
    }
    with patch.dict(openbsdrcctl.__salt__, salt_mock):
        assert openbsdrcctl.enabled("test", flags=flags_return) is True
        retcode_mock.assert_called_with(
            "{} get test status".format(rcctl), ignore_retcode=True
        )
        retcode_mock.return_value = 2
        stdout_mock.reset_mock()
        assert openbsdrcctl.enabled("test") is False
        retcode_mock.assert_called_with(
            "{} get test status".format(rcctl), ignore_retcode=True
        )

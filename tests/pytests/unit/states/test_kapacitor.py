"""
   Test cases for salt.states.kapacitor
"""

import pytest

import salt.states.kapacitor as kapacitor
from tests.support.mock import Mock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {kapacitor: {"__opts__": {"test": False}, "__env__": "test"}}


def _present(
    name="testname",
    tick_script="/tmp/script.tick",
    task_type="stream",
    database="testdb",
    retention_policy="default",
    dbrps=None,
    enable=True,
    task=None,
    define_result=True,
    enable_result=True,
    disable_result=True,
    script="testscript",
):
    """
    Run a "kapacitor.present" state after setting up mocks, and return the
    state return value as well as the mocks to make assertions.
    """
    get_mock = Mock(return_value=task)

    if isinstance(define_result, bool):
        define_result = {"success": define_result}
    define_mock = Mock(return_value=define_result)

    if isinstance(enable_result, bool):
        enable_result = {"success": enable_result}
    enable_mock = Mock(return_value=enable_result)

    if isinstance(disable_result, bool):
        disable_result = {"success": disable_result}
    disable_mock = Mock(return_value=disable_result)

    with patch.dict(
        kapacitor.__salt__,
        {
            "kapacitor.get_task": get_mock,
            "kapacitor.define_task": define_mock,
            "kapacitor.enable_task": enable_mock,
            "kapacitor.disable_task": disable_mock,
        },
    ):
        with patch("salt.utils.files.fopen", mock_open(read_data=script)) as open_mock:
            retval = kapacitor.task_present(
                name,
                tick_script,
                task_type=task_type,
                database=database,
                retention_policy=retention_policy,
                enable=enable,
                dbrps=dbrps,
            )

    return retval, get_mock, define_mock, enable_mock, disable_mock


def _task(
    script="testscript", enabled=True, task_type="stream", db="testdb", rp="default"
):
    return {
        "script": script,
        "enabled": enabled,
        "type": task_type,
        "dbrps": [{"db": db, "rp": rp}],
    }


def test_task_present_new_task():
    ret, get_mock, define_mock, enable_mock, _ = _present(dbrps=["testdb2.default_rp"])
    get_mock.assert_called_once_with("testname")
    define_mock.assert_called_once_with(
        "testname",
        "/tmp/script.tick",
        database="testdb",
        retention_policy="default",
        task_type="stream",
        dbrps=["testdb2.default_rp", "testdb.default"],
    )
    enable_mock.assert_called_once_with("testname")
    assert "TICKscript diff" in ret["changes"]
    assert "enabled" in ret["changes"]
    assert ret["changes"]["enabled"]["new"] is True


def test_task_present_existing_task_updated_script():
    ret, get_mock, define_mock, enable_mock, _ = _present(
        task=_task(script="oldscript")
    )
    get_mock.assert_called_once_with("testname")
    define_mock.assert_called_once_with(
        "testname",
        "/tmp/script.tick",
        database="testdb",
        retention_policy="default",
        task_type="stream",
        dbrps=["testdb.default"],
    )
    assert enable_mock.called is False
    assert "TICKscript diff" in ret["changes"]
    assert "enabled" not in ret["changes"]


def test_task_present_existing_task_not_enabled():
    ret, get_mock, define_mock, enable_mock, _ = _present(task=_task(enabled=False))
    get_mock.assert_called_once_with("testname")
    assert define_mock.called is False
    enable_mock.assert_called_once_with("testname")
    assert "diff" not in ret["changes"]
    assert "enabled" in ret["changes"]
    assert ret["changes"]["enabled"]["new"] is True


def test_task_present_disable_existing_task():
    ret, get_mock, define_mock, _, disable_mock = _present(task=_task(), enable=False)
    get_mock.assert_called_once_with("testname")
    assert define_mock.called is False
    disable_mock.assert_called_once_with("testname")
    assert "diff" not in ret["changes"]
    assert "enabled" in ret["changes"]
    assert ret["changes"]["enabled"]["new"] is False

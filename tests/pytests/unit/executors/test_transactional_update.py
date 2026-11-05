import pytest

import salt.executors.transactional_update as transactional_update_executor
from tests.support.mock import MagicMock, patch


@pytest.fixture
def mods():
    call = MagicMock(return_value={"ret": 1})
    direct = MagicMock(return_value="direct")
    with patch.object(
        transactional_update_executor,
        "__salt__",
        {"transactional_update.call": call},
        create=True,
    ), patch.object(
        transactional_update_executor,
        "__executors__",
        {"direct_call.execute": direct},
        create=True,
    ):
        yield call, direct


def test_state_pkg_is_delegated_to_transaction(mods):
    call, direct = mods
    with patch.dict("os.environ", {}, clear=True):
        ret = transactional_update_executor.execute(
            {}, {"fun": "state.pkg"}, MagicMock(), ["/tmp/x.tgz"], {"pkg_sum": "a"}
        )
    assert ret == {"ret": 1}
    call.assert_called_once_with("state.pkg", "/tmp/x.tgz", pkg_sum="a")
    direct.assert_not_called()


def test_state_pkg_not_delegated_inside_transaction(mods):
    call, direct = mods
    with patch.dict("os.environ", {"TRANSACTIONAL_UPDATE": "true"}):
        ret = transactional_update_executor.execute(
            {}, {"fun": "state.pkg"}, MagicMock(), [], {}
        )
    assert ret == "direct"
    call.assert_not_called()


def test_state_pkg_failure_is_reported_as_failed_state(mods):
    call, _ = mods
    call.return_value = {"result": False, "retcode": 1, "comment": "not btrfs"}
    with patch.dict("os.environ", {}, clear=True):
        ret = transactional_update_executor.execute(
            {}, {"fun": "state.pkg"}, MagicMock(), ["/tmp/x.tgz"], {}
        )
    assert len(ret) == 1
    entry = next(iter(ret.values()))
    assert entry["result"] is False
    assert "not btrfs" in entry["comment"]

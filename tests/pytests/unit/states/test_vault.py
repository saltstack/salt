import pytest

import salt.modules.vault as vaultexe
import salt.states.vault as vault
from tests.support.mock import Mock, patch


@pytest.fixture()
def configure_loader_modules():
    return {vault: {}}


@pytest.fixture()
def policy_fetch():
    fetch = Mock(return_value="test-rules", spec=vaultexe.policy_fetch)
    with patch.dict(vault.__salt__, {"vault.policy_fetch": fetch}):
        yield fetch


@pytest.fixture()
def policy_write():
    write = Mock(return_value=True, spec=vaultexe.policy_write)
    with patch.dict(vault.__salt__, {"vault.policy_write": write}):
        yield write


@pytest.mark.parametrize("test", [False, True])
def test_policy_present_no_changes(policy_fetch, test):
    with patch.dict(vault.__opts__, {"test": test}):
        res = vault.policy_present("test-policy", "test-rules")
    assert res["result"]
    assert not res["changes"]


@pytest.mark.parametrize("test", [False, True])
def test_policy_present_create(policy_fetch, policy_write, test):
    policy_fetch.return_value = None
    with patch.dict(vault.__opts__, {"test": test}):
        res = vault.policy_present("test-policy", "test-rules")
    assert res["changes"]
    if test:
        assert res["result"] is None
        assert "would be created" in res["comment"]
        policy_write.assert_not_called()
    else:
        assert res["result"]
        assert "has been created" in res["comment"]
        policy_write.assert_called_once_with("test-policy", "test-rules")


@pytest.mark.parametrize("test", [False, True])
def test_policy_present_changes(policy_fetch, policy_write, test):
    with patch.dict(vault.__opts__, {"test": test}):
        res = vault.policy_present("test-policy", "new-test-rules")
    assert res["changes"]
    if test:
        assert res["result"] is None
        assert "would be updated" in res["comment"]
        policy_write.assert_not_called()
    else:
        assert res["result"]
        assert "has been updated" in res["comment"]
        policy_write.assert_called_once_with("test-policy", "new-test-rules")


@pytest.mark.parametrize("test", [False, True])
def test_policy_absent_no_changes(policy_fetch, test):
    policy_fetch.return_value = None
    with patch.dict(vault.__opts__, {"test": test}):
        res = vault.policy_absent("test-policy")
    assert res["result"]
    assert not res["changes"]


@pytest.mark.parametrize("test", [False, True])
def test_policy_absent_changes(policy_fetch, test):
    delete = Mock(spec=vaultexe.policy_delete)
    with patch.dict(vault.__salt__, {"vault.policy_delete": delete}):
        with patch.dict(vault.__opts__, {"test": test}):
            res = vault.policy_absent("test-policy")
        assert res["changes"]
        if test:
            assert res["result"] is None
            assert "would be deleted" in res["comment"]
            delete.assert_not_called()
        else:
            assert res["result"]
            assert "has been deleted" in res["comment"]
            delete.assert_called_once_with("test-policy")

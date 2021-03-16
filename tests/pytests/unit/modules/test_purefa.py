# pylint: disable=unexpected-keyword-arg
import pytest
import salt.modules.purefa as purefa
from tests.support.mock import MagicMock, call, create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    fake_pure_storage = MagicMock()
    fake_pure_storage.PureError = Exception
    return {
        purefa: {
            "_get_host": create_autospec(purefa._get_host, return_value=None),
            "purestorage": fake_pure_storage,
        }
    }


@pytest.fixture
def patch_get_system():
    with patch("salt.modules.purefa._get_system", autospec=True) as fake_sys:
        yield fake_sys


@pytest.fixture
def fake_set_host(patch_get_system):
    fake_set_host = MagicMock()
    patch_get_system.return_value.set_host = fake_set_host
    yield fake_set_host


@pytest.fixture
def fake_delete_host(patch_get_system):
    fake_delete_host = MagicMock()
    patch_get_system.return_value.delete_host = fake_delete_host
    yield fake_delete_host


@pytest.mark.parametrize(
    "nqn", [None, "", [], ()],
)
def test_when_nqn_is_not_anything_set_host_should_not_have_addnqnlist_called(
    nqn, fake_set_host
):
    purefa.host_create("fnord", nqn=nqn)

    for call in fake_set_host.mock_calls:
        assert "addnqnlist" not in call.kwargs


def test_when_nqn_is_provided_and_adding_is_successful_then_set_host_should_have_addqnlist(
    fake_set_host,
):
    nqn = "fnord"
    host = "fnord-host"
    expected_calls = [call(host, addnqnlist=[nqn])]
    purefa.host_create(host, nqn=nqn)

    fake_set_host.assert_has_calls(expected_calls)


def test_when_nqn_is_provided_and_adding_is_successful_then_result_should_be_True(
    fake_set_host,
):

    result = purefa.host_create("fnord", nqn="fnordqn")

    assert result is True


def test_when_nqn_is_provided_but_set_host_fails_then_creation_should_be_rolled_back(
    fake_set_host, fake_delete_host
):
    expected_host = "fnord"
    fake_set_host.side_effect = purefa.purestorage.PureError("oops!")
    result = purefa.host_create(expected_host, nqn="badness or whatever")

    assert result is False
    fake_delete_host.assert_called_with(expected_host)

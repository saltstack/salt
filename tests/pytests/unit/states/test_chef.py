"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.chef
import salt.states.chef as chef
from tests.support.mock import MagicMock, create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {chef: {"__salt__": {}}}


@pytest.fixture(
    params=[
        ("chef.client", chef.client, create_autospec(salt.modules.chef.client)),
        ("chef.solo", chef.solo, create_autospec(salt.modules.chef.solo)),
    ]
)
def chef_state_and_mock_mod(request):
    mod_name, state, mock_mod = request.param
    with patch.dict(chef.__salt__, {mod_name: mock_mod}):
        yield state, mock_mod


@pytest.fixture
def test_mode():
    with patch.dict(chef.__opts__, {"test": True}):
        yield


@pytest.fixture
def not_test_mode():
    with patch.dict(chef.__opts__, {"test": False}):
        yield


@pytest.fixture(
    params=[
        "Chef Client finished, 1",
        "Chef Infra Client finished, 1",
        "Infra Phase complete, 1",
    ]
)
def changed_output(request):
    yield request.param


@pytest.fixture(
    params=[
        "Chef Client finished, 0",
        "Chef Infra Client finished, 0",
        "Infra Phase complete, 0",
    ]
)
def unchanged_output(request):
    yield request.param


@pytest.fixture
def successful_changed_output(changed_output, chef_state_and_mock_mod):
    _, mock_mod = chef_state_and_mock_mod
    mock_mod.return_value = {"retcode": 0, "stderr": "", "stdout": changed_output}
    yield


@pytest.fixture
def successful_unchanged_output(unchanged_output, chef_state_and_mock_mod):
    _, mock_mod = chef_state_and_mock_mod
    mock_mod.return_value = {"retcode": 0, "stderr": "", "stdout": unchanged_output}
    yield


@pytest.fixture
def unsuccessful_output(chef_state_and_mock_mod):
    _, mock_mod = chef_state_and_mock_mod
    mock_mod.return_value = {"retcode": 1, "stderr": "", "stdout": ""}
    yield


def test_client():
    """
    Test to run chef-client
    """
    name = "my-chef-run"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value={"retcode": 1, "stdout": "", "stderr": "error"})
    with patch.dict(chef.__salt__, {"chef.client": mock}):
        with patch.dict(chef.__opts__, {"test": True}):
            comt = "\nerror"
            ret.update({"comment": comt})
            assert chef.client(name) == ret


def test_solo():
    """
    Test to run chef-solo
    """
    name = "my-chef-run"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value={"retcode": 1, "stdout": "", "stderr": "error"})
    with patch.dict(chef.__salt__, {"chef.solo": mock}):
        with patch.dict(chef.__opts__, {"test": True}):
            comt = "\nerror"
            ret.update({"comment": comt})
            assert chef.solo(name) == ret


def test_when_testing_and_successful_changed_output_result_should_be_None(
    test_mode, successful_changed_output, chef_state_and_mock_mod
):
    state, _ = chef_state_and_mock_mod
    ret = state(name="fnord")
    assert ret["result"] is None


def test_when_testing_and_successful_unchanged_output_result_should_be_True(
    test_mode, successful_unchanged_output, chef_state_and_mock_mod
):
    state, _ = chef_state_and_mock_mod
    ret = state(name="fnord")
    assert ret["result"] is True


def test_when_not_testing_and_successful_changed_output_result_should_be_True(
    not_test_mode, successful_changed_output, chef_state_and_mock_mod
):
    state, _ = chef_state_and_mock_mod
    ret = state(name="fnord")
    assert ret["result"] is True


def test_when_not_testing_and_successful_unchanged_output_result_should_be_True(
    not_test_mode, successful_unchanged_output, chef_state_and_mock_mod
):
    state, _ = chef_state_and_mock_mod
    ret = state(name="fnord")
    assert ret["result"] is True


def test_when_not_testing_and_unsuccessful_output_result_should_be_False(
    not_test_mode, unsuccessful_output, chef_state_and_mock_mod
):
    state, _ = chef_state_and_mock_mod
    ret = state(name="fnord")
    assert ret["result"] is False

import pytest

import salt.modules.restconf as restconf
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {restconf: {}}


@pytest.fixture
def mocking_dunder_salt_restconf_getdata_response_always_200():
    fake_response = OrderedDict()
    fake_response["fjord"] = "meow"
    fake_restconf_response = dict(status=200, dict=fake_response)
    with patch.dict(
        restconf.__salt__,
        {"restconf.get_data": MagicMock(return_value=fake_restconf_response)},
    ) as opt_dunder_mock:
        yield opt_dunder_mock


def test_module_path_check_primary_success(
    mocking_dunder_salt_restconf_getdata_response_always_200,
):
    result = restconf.path_check("fakeprimarypath", "fakeinitpath")

    assert type(result) is dict
    assert "request_restponse" in result
    assert "fjord" in result["request_restponse"]
    assert "request_path" in result
    assert "request_path" in result
    assert "path_used" in result
    assert "result" in result
    assert result["result"] is True
    assert result["request_path"] == "fakeprimarypath"
    assert result["path_used"] == "primary"


@pytest.fixture
def mocking_dunder_salt_restconf_getdata_response_always_404():
    fake_restconf_response = dict(status=404)
    with patch.dict(
        restconf.__salt__,
        {"restconf.get_data": MagicMock(return_value=fake_restconf_response)},
    ) as opt_dunder_mock:
        yield opt_dunder_mock


def test_module_path_check_always_fail(
    mocking_dunder_salt_restconf_getdata_response_always_404,
):
    result = restconf.path_check("fakeprimarypath", "fakeinitpath")

    assert result["result"] is False
    assert type(result) is dict


@pytest.fixture
def mocking_dunder_salt_restconf_getdata_response_first404_then_200():
    fake_response = OrderedDict()
    fake_response["fjord"] = "meow"
    fake_restconf_response_1 = dict(status=404)
    fake_restconf_response_2 = dict(status=200, dict=fake_response)
    with patch.dict(
        restconf.__salt__,
        {
            "restconf.get_data": MagicMock(
                side_effect=[fake_restconf_response_1, fake_restconf_response_2]
            )
        },
    ) as opt_dunder_mock:
        yield opt_dunder_mock


def test_module_path_check_primary_init(
    mocking_dunder_salt_restconf_getdata_response_first404_then_200,
):
    result = restconf.path_check("fakeprimarypath", "fakeinitpath")

    assert type(result) is dict
    assert "request_restponse" in result
    assert "fjord" in result["request_restponse"]
    assert "request_path" in result
    assert "request_path" in result
    assert "path_used" in result
    assert "result" in result
    assert result["result"] is True
    assert result["request_path"] == "fakeinitpath"
    assert result["path_used"] == "init"

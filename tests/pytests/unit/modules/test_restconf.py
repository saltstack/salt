import pytest
import salt.modules.restconf as restconf
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {restconf: {}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


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


def test_module_uri_check_primary_success(
    mocking_dunder_salt_restconf_getdata_response_always_200,
):
    result = restconf.uri_check("fakeprimaryuri", "fakeinituri")

    assert result[0] is True
    assert type(result[1]) is dict
    assert "request_restponse" in result[1]
    assert "fjord" in result[1]["request_restponse"]
    assert "request_uri" in result[1]
    assert "request_uri" in result[1]
    assert "uri_used" in result[1]
    assert result[1]["request_uri"] == "fakeprimaryuri"
    assert result[1]["uri_used"] == "primary"


@pytest.fixture
def mocking_dunder_salt_restconf_getdata_response_always_404():
    fake_restconf_response = dict(status=404)
    with patch.dict(
        restconf.__salt__,
        {"restconf.get_data": MagicMock(return_value=fake_restconf_response)},
    ) as opt_dunder_mock:
        yield opt_dunder_mock


def test_module_uri_check_always_fail(
    mocking_dunder_salt_restconf_getdata_response_always_404,
):
    result = restconf.uri_check("fakeprimaryuri", "fakeinituri")

    assert result[0] is False
    assert type(result[1]) is dict


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


def test_module_uri_check_primary_init(
    mocking_dunder_salt_restconf_getdata_response_first404_then_200,
):
    result = restconf.uri_check("fakeprimaryuri", "fakeinituri")

    assert result[0] is True
    assert type(result[1]) is dict
    assert "request_restponse" in result[1]
    assert "fjord" in result[1]["request_restponse"]
    assert "request_uri" in result[1]
    assert "request_uri" in result[1]
    assert "uri_used" in result[1]
    assert result[1]["request_uri"] == "fakeinituri"
    assert result[1]["uri_used"] == "init"

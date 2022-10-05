import pytest

import salt.states.restconf as restconf
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {restconf: {}}


def test_fail_config_manage_blank_path():
    # config_manage(name, path, method, config ):
    result = restconf.config_manage("name", "", "POST", "BLANKCONFIG")
    assert result["result"] is False
    assert "CRITICAL: path must not be blank" in result["comment"]


def test_fail_config_manage_blank_method():
    # config_manage(name, path, method, config ):
    result = restconf.config_manage("name", "restconf/test", "", "BLANKCONFIG")
    assert result["result"] is False
    assert "CRITICAL: method is required" in result["comment"]


def test_fail_config_manage_blank_config():
    # config_manage(name, path, method, config ):
    result = restconf.config_manage("name", "restconf/test", "POST", "")
    assert result["result"] is False
    assert "CRITICAL: config must be an OrderedDict type" in result["comment"]


def test_fail_config_manage_blank_name():
    # config_manage(name, path, method, config ):
    result = restconf.config_manage("", "restconf/test", "POST", "BLANKBADCONFIG")
    assert result["result"] is False
    assert "CRITICAL: name is required" in result["comment"]


@pytest.fixture
def mocking_dunder_opts_test_mode_true():
    with patch.dict(restconf.__opts__, {"test": True}) as dunder_mock:
        yield dunder_mock


@pytest.fixture
def mocking_dunder_opts_test_mode_false():
    with patch.dict(restconf.__opts__, {"test": False}) as dunder_mock:
        yield dunder_mock


@pytest.fixture
def fake_path_response_primary_blank():
    fake_path_response_primary_blank = {
        "result": True,
        "path_used": "primary",
        "request_path": "restconf/fakepath",
        "request_restponse": {},
    }
    with patch.dict(
        restconf.__salt__,
        {
            "restconf.path_check": MagicMock(
                return_value=fake_path_response_primary_blank
            )
        },
    ):
        yield fake_path_response_primary_blank


def test_config_manage_nochanges_testmode(
    mocking_dunder_opts_test_mode_true, fake_path_response_primary_blank
):
    result = restconf.config_manage("name", "restconf/test", "POST", OrderedDict())
    assert result["result"] is True


def test_config_manage_nochanges_realmode(
    mocking_dunder_opts_test_mode_false, fake_path_response_primary_blank
):
    result = restconf.config_manage("name", "restconf/test", "POST", OrderedDict())
    assert result["result"] is True


def test_config_manage_haschanges_testmode(
    mocking_dunder_opts_test_mode_true, fake_path_response_primary_blank
):
    fake_changes = OrderedDict()
    fake_changes["fjord"] = "meow"
    result = restconf.config_manage("name", "restconf/test", "POST", fake_changes)

    assert result["result"] is None
    assert "fjord" in str(result["changes"])
    assert result["comment"] == "Config will be added"


@pytest.fixture
def mocking_dunder_salt_restconf_setdata_response_404():
    fake_restconf_response = dict(status=404)
    with patch.dict(
        restconf.__salt__,
        {"restconf.set_data": MagicMock(return_value=fake_restconf_response)},
    ) as opt_dunder_mock:
        yield opt_dunder_mock


def test_config_manage_haschanges_realmode_404(
    mocking_dunder_opts_test_mode_false,
    fake_path_response_primary_blank,
    mocking_dunder_salt_restconf_setdata_response_404,
):
    fake_changes = OrderedDict()
    fake_changes["fjord"] = "meow"
    result = restconf.config_manage("name", "restconf/test", "POST", fake_changes)

    assert not result["result"]
    assert len(result["changes"]) == 0
    assert type(result["changes"]) is dict
    assert "failed to add / modify config" in result["comment"]
    assert "404" in result["comment"]
    assert "restconf/fakepath" in result["comment"]


@pytest.fixture
def mocking_dunder_salt_restconf_setdata_response_200():
    fake_changes = OrderedDict()
    fake_changes["fjord"] = "meow"
    fake_restconf_response = dict(status=200, dict=fake_changes)
    with patch.dict(
        restconf.__salt__,
        {"restconf.set_data": MagicMock(return_value=fake_restconf_response)},
    ) as opt_dunder_mock:
        yield opt_dunder_mock


def test_config_manage_haschanges_realmode_200(
    mocking_dunder_opts_test_mode_false,
    fake_path_response_primary_blank,
    mocking_dunder_salt_restconf_setdata_response_200,
):
    fake_changes = OrderedDict()
    fake_changes["fjord"] = "meow"
    result = restconf.config_manage("name", "restconf/test", "POST", fake_changes)

    assert result["result"] is True
    assert type(result["changes"]) is dict
    assert "fjord" in str(result["changes"])
    assert "Successfully added config" in result["comment"]

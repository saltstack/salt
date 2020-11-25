import pytest
import salt.states.restconf as restconf
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {restconf: {}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


# @pytest.fixture
# def test_mocking_dunder_salt():
#     with patch.dict(restconf.__salt__, {"restconf.get_data": MagicMock(return_value="fnordy")}):
#         yield dunder_mock


def test_fail_config_manage_blank_uri():
    # config_manage(name, uri, method, config ):
    result = restconf.config_manage("name", "", "POST", "BLANKCONFIG")
    assert result is False


def test_fail_config_manage_blank_method():
    # config_manage(name, uri, method, config ):
    result = restconf.config_manage("name", "restconf/test", "", "BLANKCONFIG")
    assert result is False


def test_fail_config_manage_blank_config():
    # config_manage(name, uri, method, config ):
    result = restconf.config_manage("name", "restconf/test", "POST", "")
    assert result is False


def test_fail_config_manage_blank_name():
    # config_manage(name, uri, method, config ):
    result = restconf.config_manage("", "restconf/test", "POST", "BLANKCONFIG")
    assert result is False


# ordered_dict = OrderedDict()

# def test_config_manage_ordered_dict(setup_loader, test_mocking_dunder_salt):
#     # config_manage(name, uri, method, config ):
#     result = restconf.config_manage("name", "restconf/test", "POST", ordered_dict)
#     assert result is True

"""
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>

    TestCase for salt.modules.servicenow
"""

import pytest

import salt.modules.servicenow as servicenow
from tests.support.mock import MagicMock


class MockServiceNowClient:
    def __init__(self, instance_name, username, password):
        pass

    def get(self, query):
        return [{"query_size": len(query), "query_value": query}]


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "Client": MockServiceNowClient,
        "__salt__": {
            "config.option": MagicMock(
                return_value={
                    "instance_name": "test",
                    "username": "mr_test",
                    "password": "test123",
                }
            )
        },
    }
    if servicenow.HAS_LIBS is False:
        module_globals["sys.modules"] = {"servicenow_rest": MagicMock()}
        module_globals["sys.modules"][
            "servicenow_rest"
        ].api.Client = MockServiceNowClient
    return {servicenow: module_globals}


def test_module_creation():
    client = servicenow._get_client()
    assert client is not None


def test_non_structured_query():
    result = servicenow.non_structured_query("tests", "role=web")
    assert result is not None
    assert result[0]["query_size"] == 8
    assert result[0]["query_value"] == "role=web"


def test_non_structured_query_kwarg():
    result = servicenow.non_structured_query("tests", role="web")
    assert result is not None
    assert result[0]["query_size"] == 8
    assert result[0]["query_value"] == "role=web"


def test_non_structured_query_kwarg_multi():
    result = servicenow.non_structured_query("tests", role="web", type="computer")
    assert result is not None
    assert result[0]["query_size"] == 22

"""
    Test cases for salt.modules.uptime
"""

import pytest

import salt.modules.uptime as uptime
from salt.exceptions import CommandExecutionError
from tests.support.mock import Mock


class RequestMock(Mock):
    """
    Request Mock
    """

    def get(self, *args, **kwargs):
        return RequestResponseMock()

    def put(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return RequestPutResponseMock()

    def delete(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return RequestResponseMock()


class RequestResponseMock(Mock):
    def json(self):
        return [
            {"url": "http://example.org", "_id": 1234},
        ]


class RequestPutResponseMock(Mock):

    ok = True

    def json(self):
        return {"_id": 4321}


@pytest.fixture
def request_mock():
    return RequestMock()


@pytest.fixture
def configure_loader_modules(request_mock):
    return {
        uptime: {
            "__salt__": {
                "pillar.get": Mock(return_value="http://localhost:5000"),
                "requests.put": Mock(),
            },
            "requests": request_mock,
        }
    }


def test_checks_list():
    ret = uptime.checks_list()
    assert ret == ["http://example.org"]


def test_checks_exists():
    assert uptime.check_exists("http://example.org") is True


def test_checks_create(request_mock):
    pytest.raises(CommandExecutionError, uptime.create, "http://example.org")
    assert uptime.create("http://example.com") == 4321
    assert request_mock.args == ("http://localhost:5000/api/checks",)


def test_checks_delete(request_mock):
    pytest.raises(CommandExecutionError, uptime.delete, "http://example.com")
    assert uptime.delete("http://example.org") is True
    assert request_mock.args == ("http://localhost:5000/api/checks/1234",)

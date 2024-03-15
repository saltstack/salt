"""
    :codeauthor: :email:`Roald Nefs (info@roaldnefs.com)`

    Test cases for salt.modules.telegram.
"""

import pytest

import salt.modules.telegram as telegram
from tests.support.mock import MagicMock, Mock


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
    """
    Request Response Mock
    """

    def json(self):
        return [
            {"url": "http://example.org", "_id": 1234},
        ]


class RequestPutResponseMock(Mock):
    """
    Request Put Response Mock
    """

    ok = True

    def json(self):
        return {"_id": 4321}


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {
            "config.get": MagicMock(
                return_value={
                    "telegram": {
                        "chat_id": "123456789",
                        "token": "000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    }
                }
            ),
            "requests.put": Mock(),
        },
        "requests": RequestMock(),
    }
    return {telegram: module_globals}


def test_post_message():
    """
    Test the post_message function.
    """
    message = "Hello World!"
    assert telegram.post_message(message)

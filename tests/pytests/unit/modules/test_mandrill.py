"""
Tests for the Mandrill execution module.
"""


import pytest

import salt.modules.mandrill as mandrill
from tests.support.mock import MagicMock, patch


@pytest.fixture
def fn_test_send():
    return {
        "result": True,
        "comment": "",
        "out": [
            {
                "status": "sent",
                "_id": "c4353540a3c123eca112bbdd704ab6",
                "email": "recv@example.com",
                "reject_reason": None,
            }
        ],
    }


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        mandrill: {
            "__salt__": {
                "config.merge": MagicMock(
                    return_value={"mandrill": {"key": "2orgk34kgk34g"}}
                )
            }
        }
    }
    if mandrill.HAS_REQUESTS is False:
        module_globals["sys.modules"] = {"requests": MagicMock()}
    return module_globals


def test_send(fn_test_send):
    """
    Test the send function.
    """
    mock_cmd = MagicMock(return_value=fn_test_send)
    with patch.object(mandrill, "send", mock_cmd) as send:
        assert (
            send(
                message={
                    "subject": "Hi",
                    "from_email": "test@example.com",
                    "to": [{"email": "recv@example.com", "type": "to"}],
                }
            )
            == fn_test_send
        )


def test_deprecation_58640():
    # check that type error will be raised
    message = {
        "subject": "Hi",
        "from_email": "test@example.com",
        "to": [{"email": "recv@example.com", "type": "to"}],
    }
    pytest.raises(TypeError, mandrill.send, **{"message": message, "async": True})

    # check that async will raise an error
    try:
        mandrill.send(  # pylint: disable=unexpected-keyword-arg
            **{"message": message, "async": True}
        )
    except TypeError as no_async:
        assert str(no_async) == "send() got an unexpected keyword argument 'async'"

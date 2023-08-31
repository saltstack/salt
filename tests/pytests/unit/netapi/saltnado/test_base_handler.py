import time

import pytest

import salt.netapi.rest_tornado.saltnado as saltnado_app
from tests.support.mock import MagicMock, patch


@pytest.fixture
def arg_mock():
    mock = MagicMock()
    mock.opts = {
        "syndic_wait": 0.1,
        "cachedir": "/tmp/testing/cachedir",
        "sock_dir": "/tmp/testing/sock_drawer",
        "transport": "zeromq",
        "extension_modules": "/tmp/testing/moduuuuules",
        "order_masters": False,
        "gather_job_timeout": 10.001,
    }
    return mock


def test__verify_auth(arg_mock):
    base_handler = saltnado_app.BaseSaltAPIHandler(arg_mock, arg_mock)
    with patch.object(base_handler, "get_cookie", return_value="ABCDEF"):
        with patch.object(
            base_handler.application.auth,
            "get_tok",
            return_value={"expire": time.time() + 60},
        ):
            assert base_handler._verify_auth()


def test__verify_auth_expired(arg_mock):
    base_handler = saltnado_app.BaseSaltAPIHandler(arg_mock, arg_mock)
    with patch.object(base_handler, "get_cookie", return_value="ABCDEF"):
        with patch.object(
            base_handler.application.auth,
            "get_tok",
            return_value={"expire": time.time() - 60},
        ):
            assert not base_handler._verify_auth()

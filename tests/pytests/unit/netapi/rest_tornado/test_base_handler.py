import time

import salt.netapi.rest_tornado.saltnado as saltnado_app
from tests.support.mock import patch


def test__verify_auth(app_mock):
    base_handler = saltnado_app.BaseSaltAPIHandler(app_mock, app_mock)
    with patch.object(base_handler, "get_cookie", return_value="ABCDEF"):
        with patch.object(
            base_handler.application.auth,
            "get_tok",
            return_value={"expire": time.time() + 60},
        ):
            assert base_handler._verify_auth()


def test__verify_auth_expired(app_mock):
    base_handler = saltnado_app.BaseSaltAPIHandler(app_mock, app_mock)
    with patch.object(base_handler, "get_cookie", return_value="ABCDEF"):
        with patch.object(
            base_handler.application.auth,
            "get_tok",
            return_value={"expire": time.time() - 60},
        ):
            assert not base_handler._verify_auth()

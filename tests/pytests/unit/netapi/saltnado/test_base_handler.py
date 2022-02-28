import time

import pytest
import salt.netapi.rest_tornado.saltnado as saltnado_app
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {saltnado_app: {}}


def test__verify_auth():
    base_handler = saltnado_app.BaseSaltAPIHandler(MagicMock(), MagicMock())
    with patch.object(base_handler, "get_cookie", return_value="ABCDEF"):
        with patch.object(
            base_handler.application.auth,
            "get_tok",
            return_value={"expire": time.time() + 60},
        ):
            assert base_handler._verify_auth()


def test__verify_auth_expired():
    base_handler = saltnado_app.BaseSaltAPIHandler(MagicMock(), MagicMock())
    with patch.object(base_handler, "get_cookie", return_value="ABCDEF"):
        with patch.object(
            base_handler.application.auth,
            "get_tok",
            return_value={"expire": time.time() - 60},
        ):
            assert not base_handler._verify_auth()

import time

import pytest

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


@pytest.mark.parametrize(
    "line, main, param_key",
    [
        ("application/json", "application/json", None),
        ("application/json; charset=utf-8", "application/json", "charset"),
        (
            " application/x-www-form-urlencoded ",
            "application/x-www-form-urlencoded",
            None,
        ),
        ("text/yaml; boundary=foo", "text/yaml", "boundary"),
    ],
)
def test_parse_header_replaces_cgi(line, main, param_key):
    got_main, got_params = saltnado_app._parse_header(line)
    assert got_main == main
    if param_key is None:
        assert got_params == {}
    else:
        assert param_key in got_params

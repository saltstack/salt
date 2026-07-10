import sys

import pytest

import salt.netapi.rest_tornado.saltnado as saltnado
from tests.support.mock import MagicMock


@pytest.fixture
def io_loop(io_loop):
    """
    Fail tests on exceptions raised inside IOLoop callbacks.

    The legacy AsyncTestCase harness rethrew exceptions raised in scheduled
    callbacks; the plain IOLoop only logs them, which would let a broken
    completer callback pass a test that no longer exercises anything.
    Capture such exceptions and re-raise them at teardown.
    """
    captured = []

    def capture_callback_exception(callback):
        captured.append(sys.exc_info()[1])

    io_loop.handle_callback_exception = capture_callback_exception
    yield io_loop
    if captured:
        raise captured[0]


@pytest.fixture
def app_mock():
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


@pytest.fixture
def salt_api_handler(io_loop, app_mock):
    # io_loop is requested first so the fresh loop is current before the
    # handler is constructed, matching the setUp ordering the legacy
    # AsyncTestCase suite relied on.
    return saltnado.SaltAPIHandler(app_mock, app_mock)

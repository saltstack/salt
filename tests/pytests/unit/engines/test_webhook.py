"""
unit tests for the webhook engine
"""

from pytest import fixture

import salt.engines.webhook as webhook
from tests.support.mock import MagicMock, patch


@fixture
def configure_loader_modules(master_opts):
    return {webhook: {"__opts__": master_opts}}


def test_start_uses_listen_false_for_master(configure_loader_modules):
    with patch("salt.utils.event.get_master_event") as get_master_event, patch(
        "tornado.httpserver.HTTPServer"
    ) as fake_http_server, patch("tornado.ioloop.IOLoop") as fake_io_loop:
        get_master_event.return_value.fire_event = MagicMock()

        webhook.start()

        get_master_event.assert_called_once_with(
            webhook.__opts__, webhook.__opts__["sock_dir"], listen=False
        )
        fake_io_loop.return_value.start.assert_called_once()

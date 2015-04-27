# encoding: utf-8
import logging
import salt.client.netapi
from .test_handlers import SaltnadoTestCase

import salttesting.mock as mock

logger = logging.getLogger(__name__)


class StubHandler(object):
    """
    Stub Handler to test the import module below
    """


class TestNetapiStartup(object):

    @mock.patch("tornado.web.Application")
    @mock.patch("tornado.httpserver.HTTPServer")
    @mock.patch("tornado.ioloop.IOLoop.instance")
    def test_url_extensions_start(self, mock_ioloop, mock_http_server, mock_application):
        '''
        Test that url extensions are properly imported and included in paths
        '''
        opts = self.opts
        opts['rest_tornado'] = {
                "port": "55555",
                "disable_ssl": True,
                "extension_urls": {
                    "/foo": {
                        "module": "unit.netapi.rest_tornado",
                        "class": "StubHandler"
                    }
                }
            }
        client = salt.client.netapi.NetapiClient(opts)
        client.netapi['rest_tornado.start']()
        app_args, app_kwargs = mock_application.call_args
        paths = app_args[0]
        added_url = paths[-1]
        self.assertEqual(added_url[0], "/foo")
        self.assertEqual(added_url[1], StubHandler)
        self.assertTrue(mock_http_server.called)
        self.assertTrue(mock_ioloop.called)

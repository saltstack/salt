# flake8: noqa
# pylint: skip-file
from __future__ import absolute_import, division, print_function
from salt.ext.tornado.test.util import unittest


class ImportTest(unittest.TestCase):
    def test_import_everything(self):
        # Some of our modules are not otherwise tested.  Import them
        # all (unless they have external dependencies) here to at
        # least ensure that there are no syntax errors.
        import salt.ext.tornado.auth
        import salt.ext.tornado.autoreload
        import salt.ext.tornado.concurrent
        import salt.ext.tornado.escape
        import salt.ext.tornado.gen
        import salt.ext.tornado.http1connection
        import salt.ext.tornado.httpclient
        import salt.ext.tornado.httpserver
        import salt.ext.tornado.httputil
        import salt.ext.tornado.ioloop
        import salt.ext.tornado.iostream
        import salt.ext.tornado.locale
        import salt.ext.tornado.log
        import salt.ext.tornado.netutil
        import salt.ext.tornado.options
        import salt.ext.tornado.process
        import salt.ext.tornado.simple_httpclient
        import salt.ext.tornado.stack_context
        import salt.ext.tornado.tcpserver
        import salt.ext.tornado.tcpclient
        import salt.ext.tornado.template
        import salt.ext.tornado.testing
        import salt.ext.tornado.util
        import salt.ext.tornado.web
        import salt.ext.tornado.websocket
        import salt.ext.tornado.wsgi

    # for modules with dependencies, if those dependencies can be loaded,
    # load them too.

    def test_import_pycurl(self):
        try:
            import pycurl  # type: ignore
        except ImportError:
            pass
        else:
            import salt.ext.tornado.curl_httpclient

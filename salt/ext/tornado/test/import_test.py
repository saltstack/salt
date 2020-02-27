# flake8: noqa
# pylint: skip-file
from __future__ import absolute_import, division, print_function
from salt.ext.tornado.test.util import unittest


class ImportTest(unittest.TestCase):
    def test_import_everything(self):
        # Some of our modules are not otherwise tested.  Import them
        # all (unless they have external dependencies) here to at
        # least ensure that there are no syntax errors.
        import tornado.auth
        import tornado.autoreload
        import tornado.concurrent
        import tornado.escape
        import tornado.gen
        import tornado.http1connection
        import tornado.httpclient
        import tornado.httpserver
        import tornado.httputil
        import tornado.ioloop
        import tornado.iostream
        import tornado.locale
        import tornado.log
        import tornado.netutil
        import tornado.options
        import tornado.process
        import tornado.simple_httpclient
        import tornado.stack_context
        import tornado.tcpserver
        import tornado.tcpclient
        import tornado.template
        import tornado.testing
        import tornado.util
        import tornado.web
        import tornado.websocket
        import tornado.wsgi

    # for modules with dependencies, if those dependencies can be loaded,
    # load them too.

    def test_import_pycurl(self):
        try:
            import pycurl  # type: ignore
        except ImportError:
            pass
        else:
            import tornado.curl_httpclient

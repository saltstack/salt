# -*- coding: utf-8 -*-

# Import Pytohn libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import Mock, patch

# Import Salt Module
import salt.modules.nginx as nginx

MOCK_STATUS_OUTPUT = """Active connections: 7
server accepts handled requests
 46756 46756 89318
Reading: 0 Writing: 7 Waiting: 0"""


class MockUrllibStatus(object):
    """Mock of urllib2 call for Nginx status"""
    def read(self):
        return MOCK_STATUS_OUTPUT

    def close(self):
        pass


class NginxTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        patcher = patch('salt.utils.path.which', Mock(return_value='/usr/bin/nginx'))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {nginx: {'_urlopen': Mock(return_value=MockUrllibStatus())}}

    def test_nginx_status(self):
        result = nginx.status()
        nginx._urlopen.assert_called_once_with('http://127.0.0.1/status')
        self.assertEqual(result, {
            'active connections': 7,
            'accepted': 46756,
            'handled': 46756,
            'requests': 89318,
            'reading': 0,
            'writing': 7,
            'waiting': 0,
        })

    def test_nginx_status_with_arg(self):
        other_path = 'http://localhost/path'
        result = nginx.status(other_path)
        nginx._urlopen.assert_called_once_with(other_path)

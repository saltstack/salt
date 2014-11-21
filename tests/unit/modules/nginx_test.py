# -*- coding: utf-8 -*-

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch
ensure_in_syspath('../../')

# Import Salt Module
from salt.modules import nginx

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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.utils.which', Mock(return_value='/usr/bin/nginx'))
class NginxTestCase(TestCase):

    @patch('salt.modules.nginx._urlopen', Mock(return_value=MockUrllibStatus()))
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

    @patch('salt.modules.nginx._urlopen', Mock(return_value=MockUrllibStatus()))
    def test_nginx_status_with_arg(self):
        other_path = 'http://localhost/path'
        result = nginx.status(other_path)
        nginx._urlopen.assert_called_once_with(other_path)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NginxTestCase, needs_daemon=False)

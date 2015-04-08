# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch
ensure_in_syspath('../../')
ensure_in_syspath('../../../')

# Import salt libs
from salt.exceptions import CommandExecutionError
from salt.modules import uptime

uptime.__grains__ = None  # in order to stub it w/patch below
uptime.__salt__ = None  # in order to stub it w/patch below

if NO_MOCK is False:
    SALT_STUB = {
        'pillar.get': Mock(return_value='http://localhost:5000'),
        'requests.put': Mock(),
    }
else:
    SALT_STUB = {}


class RequestMock(Mock):
    ''' Request Mock'''

    def get(self, *args, **kwargs):
        return RequestResponseMock()

    def put(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return RequestPutResponseMock()

    def delete(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return RequestResponseMock()


class RequestResponseMock(Mock):

    def json(self):
        return [{'url': 'http://example.org',
                 '_id': 1234}, ]


class RequestPutResponseMock(Mock):

    ok = True

    def json(self):
        return {'_id': 4321}

REQUEST_MOCK = RequestMock()


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(uptime,
                requests=REQUEST_MOCK,
                __salt__=SALT_STUB)
class UptimeTestCase(TestCase):
    ''' UptimeTestCase'''

    def test_checks_list(self):
        ret = uptime.checks_list()
        self.assertListEqual(ret, ['http://example.org'])

    def test_checks_exists(self):
        self.assertTrue(uptime.check_exists('http://example.org') is True)

    def test_checks_create(self):
        self.assertRaises(CommandExecutionError, uptime.create,
                          'http://example.org')
        self.assertEqual(4321, uptime.create('http://example.com'))
        self.assertEqual(('http://localhost:5000/api/checks',),
                         REQUEST_MOCK.args)

    def test_checks_delete(self):
        self.assertRaises(CommandExecutionError, uptime.delete,
                          'http://example.com')
        self.assertTrue(uptime.delete('http://example.org') is True)
        self.assertEqual(('http://localhost:5000/api/checks/1234',),
                         REQUEST_MOCK.args)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(UptimeTestCase, needs_daemon=False)

# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, Mock

# Import salt libs
from salt.exceptions import CommandExecutionError
import salt.modules.uptime as uptime


class RequestMock(Mock):
    '''
    Request Mock
    '''

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
class UptimeTestCase(TestCase, LoaderModuleMockMixin):
    '''
    UptimeTestCase
    '''

    def setup_loader_modules(self):
        return {
            uptime: {
                '__salt__': {
                    'pillar.get': Mock(return_value='http://localhost:5000'),
                    'requests.put': Mock(),
                },
                'requests': REQUEST_MOCK
            }
        }

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

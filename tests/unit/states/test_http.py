# -*- coding: utf-8 -*-
'''
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.http as http

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HttpTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the HTTP state
    '''
    def setup_loader_modules(self):
        return {http: {}}

    def test_query(self):
        '''
            Test to perform an HTTP query and statefully return the result
        '''
        ret = [{'changes': {},
                'comment': ' Either match text (match) or a '
                'status code (status) is required.', 'data': {},
                'name': 'salt', 'result': False},
               {'changes': {}, 'comment': ' (TEST MODE)', 'data': True, 'name': 'salt',
                'result': None}]
        self.assertDictEqual(http.query("salt"), ret[0])

        with patch.dict(http.__opts__, {'test': True}):
            mock = MagicMock(return_value=True)
            with patch.dict(http.__salt__, {'http.query': mock}):
                self.assertDictEqual(http.query("salt", "Dude", "stack"),
                                     ret[1])


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestCaseHttp(TestCase):
    def test_http_downloaded_module_import_failed(self):
        ret = {'name': 'myFile',
               'result': False,
               'comment': "'http.download' module is not available on this minion.",
               'changes': {}}
        self.assertEqual(http.downloaded('myFile', 'http:/fake/url/file.tar.gz'), ret)

    def test_http_downloaded_is_testing(self):
        mock_http_modules = {'http.download': MagicMock(return_value=True)}
        with patch.dict(http.__salt__, mock_http_modules):
            mock__opts__ = {'test': MagicMock(return_value=True)}
            with patch.dict(http.__opts__, mock__opts__):
                ret = {'name': 'myFile',
                       'result': None,
                       'comment': '{} would have been downloaded to {}'.format('http:/fake/url/file.tar.gz', 'myFile'),
                       'changes': {}}
                self.assertEqual(http.downloaded('myFile', 'http:/fake/url/file.tar.gz'), ret)

    def test_http_downloaded_Success(self):
        mock_http_modules = {'http.download': MagicMock(return_value={'Success': 'Success'})}
        with patch.dict(http.__salt__, mock_http_modules):
            ret = {'name': 'myFile',
                   'result': True,
                   'comment': 'Success',
                   'changes': {}}
            self.assertEqual(http.downloaded('myFile', 'http:/fake/url/file.tar.gz'), ret)

    def test_http_downloaded_Success_Changes(self):
        mock_http_modules = {'http.download': MagicMock(return_value={'Success': 'Success', 'Changes': 'Changes'})}
        with patch.dict(http.__salt__, mock_http_modules):
            ret = {'name': 'myFile',
                   'result': True,
                   'comment': 'Success',
                   'changes': {'new file': 'Changes'}}
            self.assertEqual(http.downloaded('myFile', 'http:/fake/url/file.tar.gz'), ret)

    def test_http_downloaded_Error(self):
        mock_http_modules = {'http.download': MagicMock(return_value={'Error': 'Error'})}
        with patch.dict(http.__salt__, mock_http_modules):
            ret = {'name': 'myFile',
                   'result': False,
                   'comment': 'Error',
                   'changes': {}}
            self.assertEqual(http.downloaded('myFile', 'http:/fake/url/file.tar.gz'), ret)

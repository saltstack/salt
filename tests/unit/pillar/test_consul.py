# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt Libs
import salt.pillar.consul_pillar as consul_pillar

# Import 3rd-party libs
from salt.ext import six

OPTS = {'consul_config': {'consul.port': 8500, 'consul.host': '172.17.0.15'}}

PILLAR_DATA = [
    {'Value': '/path/to/certs/testsite1.crt', 'Key': 'test-shared/sites/testsite1/ssl/certs/SSLCertificateFile'},
    {'Value': '/path/to/certs/testsite1.key', 'Key': 'test-shared/sites/testsite1/ssl/certs/SSLCertificateKeyFile'},
    {'Value': None, 'Key': 'test-shared/sites/testsite1/ssl/certs/'},
    {'Value': 'True', 'Key': 'test-shared/sites/testsite1/ssl/force'},
    {'Value': None, 'Key': 'test-shared/sites/testsite1/ssl/'},
    {'Value': 'salt://sites/testsite1.tmpl', 'Key': 'test-shared/sites/testsite1/template'},
    {'Value': 'test.example.com', 'Key': 'test-shared/sites/testsite1/uri'},
    {'Value': None, 'Key': 'test-shared/sites/testsite1/'},
    {'Value': None, 'Key': 'test-shared/sites/'},
    {'Value': 'Test User', 'Key': 'test-shared/user/full_name'},
    {'Value': 'adm\nwww-data\nmlocate', 'Key': 'test-shared/user/groups'},
    {'Value': '"adm\nwww-data\nmlocate"', 'Key': 'test-shared/user/dontsplit'},
    {'Value': None, 'Key': 'test-shared/user/blankvalue'},
    {'Value': 'test', 'Key': 'test-shared/user/login'},
    {'Value': None, 'Key': 'test-shared/user/'}
]

SIMPLE_DICT = {'key1': {'key2': 'val1'}}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not consul_pillar.HAS_CONSUL, 'python-consul module not installed')
class ConsulPillarTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.pillar.consul_pillar
    '''
    def setup_loader_modules(self):
        return {
            consul_pillar: {
                '__opts__': OPTS,
                'get_conn': MagicMock(return_value='consul_connection')
            }
        }

    def test_connection(self):
        with patch.dict(consul_pillar.__salt__, {'grains.get': MagicMock(return_value=({}))}):
            with patch.object(consul_pillar, 'consul_fetch', MagicMock(return_value=('2232', PILLAR_DATA))):
                consul_pillar.ext_pillar('testminion', {}, 'consul_config root=test-shared/')
                consul_pillar.get_conn.assert_called_once_with(OPTS, 'consul_config')

    def test_pillar_data(self):
        with patch.dict(consul_pillar.__salt__, {'grains.get': MagicMock(return_value=({}))}):
            with patch.object(consul_pillar, 'consul_fetch', MagicMock(return_value=('2232', PILLAR_DATA))):
                pillar_data = consul_pillar.ext_pillar('testminion', {}, 'consul_config root=test-shared/')
                consul_pillar.consul_fetch.assert_called_once_with('consul_connection', 'test-shared/')
                assert sorted(pillar_data) == ['sites', 'user']
                self.assertNotIn('blankvalue', pillar_data['user'])

    def test_value_parsing(self):
        with patch.dict(consul_pillar.__salt__, {'grains.get': MagicMock(return_value=({}))}):
            with patch.object(consul_pillar, 'consul_fetch', MagicMock(return_value=('2232', PILLAR_DATA))):
                pillar_data = consul_pillar.ext_pillar('testminion', {}, 'consul_config root=test-shared/')
                assert isinstance(pillar_data['user']['dontsplit'], six.string_types)

    def test_dict_merge(self):
        test_dict = {}
        with patch.dict(test_dict, SIMPLE_DICT):
            self.assertDictEqual(consul_pillar.dict_merge(test_dict, SIMPLE_DICT), SIMPLE_DICT)
        with patch.dict(test_dict, {'key1': {'key3': {'key4': 'value'}}}):
            self.assertDictEqual(consul_pillar.dict_merge(test_dict, SIMPLE_DICT),
                                 {'key1': {'key2': 'val1', 'key3': {'key4': 'value'}}})

# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt Libs
import salt.pillar.consul_pillar as consul_pillar

OPTS = {'consul_config': {'consul.port': 8500, 'consul.host': '172.17.0.15'}}

consul_pillar.__opts__ = OPTS
consul_pillar.__salt__ = {}

PILLAR_DATA = [
    {'Value': '/path/to/certs/testsite1.crt', 'Key': u'test-shared/sites/testsite1/ssl/certs/SSLCertificateFile'},
    {'Value': '/path/to/certs/testsite1.key', 'Key': u'test-shared/sites/testsite1/ssl/certs/SSLCertificateKeyFile'},
    {'Value': None, 'Key': u'test-shared/sites/testsite1/ssl/certs/'},
    {'Value': 'True', 'Key': u'test-shared/sites/testsite1/ssl/force'},
    {'Value': None, 'Key': u'test-shared/sites/testsite1/ssl/'},
    {'Value': 'salt://sites/testsite1.tmpl', 'Key': u'test-shared/sites/testsite1/template'},
    {'Value': 'test.example.com', 'Key': u'test-shared/sites/testsite1/uri'},
    {'Value': None, 'Key': u'test-shared/sites/testsite1/'},
    {'Value': None, 'Key': u'test-shared/sites/'},
    {'Value': 'Test User', 'Key': u'test-shared/user/full_name'},
    {'Value': 'adm\nwww-data\nmlocate', 'Key': u'test-shared/user/groups'},
    {'Value': '"adm\nwww-data\nmlocate"', 'Key': u'test-shared/user/dontsplit'},
    {'Value': None, 'Key': u'test-shared/user/blankvalue'},
    {'Value': 'test', 'Key': u'test-shared/user/login'},
    {'Value': None, 'Key': u'test-shared/user/'}
]

SIMPLE_DICT = {'key1': {'key2': 'val1'}}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not consul_pillar.HAS_CONSUL, 'no consul-python')
class ConsulPillarTestCase(TestCase):
    '''
    Test cases for salt.pillar.consul_pillar
    '''
    def get_pillar(self):
        consul_pillar.get_conn = MagicMock(return_value='consul_connection')
        pillar = consul_pillar
        return pillar

    def test_connection(self):
        pillar = self.get_pillar()
        with patch.dict(consul_pillar.__salt__, {'grains.get': MagicMock(return_value=({}))}):
            with patch.object(consul_pillar, 'consul_fetch', MagicMock(return_value=('2232', PILLAR_DATA))):
                pillar.ext_pillar('testminion', {}, 'consul_config root=test-shared/')
                pillar.get_conn.assert_called_once_with(OPTS, 'consul_config')

    def test_pillar_data(self):
        pillar = self.get_pillar()
        with patch.dict(consul_pillar.__salt__, {'grains.get': MagicMock(return_value=({}))}):
            with patch.object(consul_pillar, 'consul_fetch', MagicMock(return_value=('2232', PILLAR_DATA))):
                pillar_data = pillar.ext_pillar('testminion', {}, 'consul_config root=test-shared/')
                pillar.consul_fetch.assert_called_once_with('consul_connection', 'test-shared/')
                assert pillar_data.keys() == [u'user', u'sites']
                self.assertNotIn('blankvalue', pillar_data[u'user'])

    def test_value_parsing(self):
        pillar = self.get_pillar()
        with patch.dict(consul_pillar.__salt__, {'grains.get': MagicMock(return_value=({}))}):
            with patch.object(consul_pillar, 'consul_fetch', MagicMock(return_value=('2232', PILLAR_DATA))):
                pillar_data = pillar.ext_pillar('testminion', {}, 'consul_config root=test-shared/')
                assert isinstance(pillar_data[u'user'][u'dontsplit'], str)

    def test_dict_merge(self):
        pillar = self.get_pillar()
        test_dict = {}
        with patch.dict(test_dict, SIMPLE_DICT):
            self.assertDictEqual(pillar.dict_merge(test_dict, SIMPLE_DICT), SIMPLE_DICT)
        with patch.dict(test_dict, {'key1': {'key3': {'key4': 'value'}}}):
            self.assertDictEqual(pillar.dict_merge(test_dict, SIMPLE_DICT),
                                 {'key1': {'key2': 'val1', 'key3': {'key4': 'value'}}})

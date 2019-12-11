
# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Libs
import salt.config
import salt.loader
import salt.modules.azurearm_dns as azurearm_dns

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

# Azure libs
# pylint: disable=import-error
HAS_LIBS = False
try:
    import azure.mgmt.dns.models
    HAS_LIBS = True
except ImportError:
    pass

# pylint: enable=import-error

log = logging.getLogger(__name__)

MOCK_CREDENTIALS = {
    'client_id': 'CLIENT_ID',
    'secret': 'SECRET',
    'subscription_id': 'SUBSCRIPTION_ID',
    'tenant': 'TENANT'
}


class AzureObjMock(object):
    '''
    mock azure object for as_dict calls
    '''
    args = None
    kwargs = None

    def __init__(self, args, kwargs, return_value=None):
        self.args = args
        self.kwargs = kwargs
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()

    def as_dict(self, *args, **kwargs):
        return self.args, self.kwargs


class AzureFuncMock(object):
    '''
    mock azure client function calls
    '''
    def __init__(self, return_value=None):
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()

    def create_or_update(self, *args, **kwargs):
        azure_obj = AzureObjMock(args, kwargs)
        return azure_obj


class AzureSubMock(object):
    '''
    mock azure client sub-modules
    '''
    record_sets = AzureFuncMock()
    zones = AzureFuncMock()

    def __init__(self, return_value=None):
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()


class AzureClientMock(object):
    '''
    mock azure client
    '''
    def __init__(self, return_value=AzureSubMock):
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_LIBS is False, 'The azure.mgmt.dns module must be installed.')
class AzureRmDnsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.azurearm_dns module
    '''
    def setup_loader_modules(self):
        '''
        setup loader modules and override the azurearm.get_client utility
        '''
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(self.opts)
        funcs = salt.loader.minion_mods(self.opts, utils=utils, whitelist=['azurearm_dns', 'config'])
        utils['azurearm.get_client'] = AzureClientMock()
        return {
            azurearm_dns: {
                '__opts__': self.opts,
                '__utils__': utils,
                '__salt__': funcs
            },
        }

    def setUp(self):
        '''
        setup
        '''
        TestCase.setUp(self)
        azurearm_dns.__virtual__()

    def tearDown(self):
        '''
        tear down
        '''
        del self.opts

    def test_record_set_create_or_update(self):  # pylint: disable=invalid-name
        '''
        tests record set object creation
        '''
        expected = {
            'if_match': None,
            'if_none_match': None,
            'parameters': {
                'arecords': [{'ipv4_address': '10.0.0.1'}],
                'ttl': 300
            },
            'record_type': 'A',
            'relative_record_set_name': 'myhost',
            'resource_group_name': 'testgroup',
            'zone_name': 'myzone'
        }

        record_set_args, record_set_kwargs = azurearm_dns.record_set_create_or_update(
            'myhost',
            'myzone',
            'testgroup',
            'A',
            arecords=[{'ipv4_address': '10.0.0.1'}],
            ttl=300,
            **MOCK_CREDENTIALS
        )

        for key, val in record_set_kwargs.items():
            if isinstance(val, azure.mgmt.dns.models.RecordSet):
                record_set_kwargs[key] = val.as_dict()

        self.assertEqual(record_set_kwargs, expected)

    def test_zone_create_or_update(self):
        '''
        tests zone object creation
        '''
        expected = {
            'if_match': None,
            'if_none_match': None,
            'parameters': {
                'location': 'global',
                'zone_type': 'Public'
            },
            'resource_group_name': 'testgroup',
            'zone_name': 'myzone'
        }

        zone_args, zone_kwargs = azurearm_dns.zone_create_or_update(
            'myzone',
            'testgroup',
            **MOCK_CREDENTIALS
        )

        for key, val in zone_kwargs.items():
            if isinstance(val, azure.mgmt.dns.models.Zone):
                zone_kwargs[key] = val.as_dict()

        self.assertEqual(zone_kwargs, expected)

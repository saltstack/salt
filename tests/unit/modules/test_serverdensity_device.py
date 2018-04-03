# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils.json
import salt.modules.serverdensity_device as serverdensity_device
from salt.exceptions import CommandExecutionError


class MockRequests(object):
    '''
    Mock smtplib class
    '''
    flag = None
    content = '''{"message": "Invalid token", "errors": [{"type": "invalid_token", "subject": "token"}]}'''
    status_code = None

    def __init__(self):
        self.url = None
        self.data = None
        self.kwargs = None

    def return_request(self, url, data=None, **kwargs):
        '''
        Mock request method.
        '''
        self.url = url
        self.data = data
        self.kwargs = kwargs
        requests = MockRequests()
        if self.flag == 1:
            requests.status_code = 401
        else:
            requests.status_code = 200
        return requests

    def post(self, url, data=None, **kwargs):
        '''
        Mock post method.
        '''
        return self.return_request(url, data, **kwargs)

    def delete(self, url, **kwargs):
        '''
        Mock delete method.
        '''
        return self.return_request(url, **kwargs)

    def get(self, url, **kwargs):
        '''
        Mock get method.
        '''
        return self.return_request(url, **kwargs)

    def put(self, url, data=None, **kwargs):
        '''
        Mock put method.
        '''
        return self.return_request(url, data, **kwargs)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServerdensityDeviceTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.serverdensity_device
    '''
    def setup_loader_modules(self):
        return {
            serverdensity_device: {
                'requests': MockRequests()
            }
        }

    def setUp(self):
        self.mock_json_loads = MagicMock(side_effect=ValueError())

    # 'get_sd_auth' function tests: 1

    def test_get_sd_auth(self):
        '''
        Tests if it returns requested Server Density
        authentication value from pillar.
        '''
        with patch.dict(serverdensity_device.__pillar__, {'serverdensity':
                                                          False}):
            self.assertRaises(CommandExecutionError,
                              serverdensity_device.get_sd_auth, '1')

        with patch.dict(serverdensity_device.__pillar__, {'serverdensity':
                                                          {'1': 'salt'}}):
            self.assertEqual(serverdensity_device.get_sd_auth('1'), 'salt')

            self.assertRaises(CommandExecutionError,
                              serverdensity_device.get_sd_auth, '2')

    # 'create' function tests: 1

    def test_create(self):
        '''
        Tests if it create device in Server Density.
        '''
        with patch.dict(serverdensity_device.__pillar__,
                        {'serverdensity': {'api_token': 'salt'}}):
            self.assertTrue(serverdensity_device.create('rich_lama',
                                                        group='lama_band'))

            with patch.object(salt.utils.json, 'loads', self.mock_json_loads):
                self.assertRaises(CommandExecutionError,
                                  serverdensity_device.create, 'rich_lama',
                                  group='lama_band')

            MockRequests.flag = 1
            self.assertIsNone(serverdensity_device.create('rich_lama',
                                                          group='lama_band'))

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Tests if it delete a device from Server Density.
        '''
        with patch.dict(serverdensity_device.__pillar__,
                        {'serverdensity': {'api_token': 'salt'}}):
            MockRequests.flag = 0
            self.assertTrue(serverdensity_device.delete('51f7eaf'))

            with patch.object(salt.utils.json, 'loads', self.mock_json_loads):
                self.assertRaises(CommandExecutionError,
                                  serverdensity_device.delete, '51f7eaf')

            MockRequests.flag = 1
            self.assertIsNone(serverdensity_device.delete('51f7eaf'))

    # 'ls' function tests: 1

    def test_ls(self):
        '''
        Tests if it list devices in Server Density.
        '''
        with patch.dict(serverdensity_device.__pillar__,
                        {'serverdensity': {'api_token': 'salt'}}):
            MockRequests.flag = 0
            self.assertTrue(serverdensity_device.ls(name='lama'))

            with patch.object(salt.utils.json, 'loads', self.mock_json_loads):
                self.assertRaises(CommandExecutionError,
                                  serverdensity_device.ls, name='lama')

            MockRequests.flag = 1
            self.assertIsNone(serverdensity_device.ls(name='lama'))

    # 'update' function tests: 1

    def test_update(self):
        '''
        Tests if it updates device information in Server Density.
        '''
        with patch.dict(serverdensity_device.__pillar__,
                        {'serverdensity': {'api_token': 'salt'}}):
            MockRequests.flag = 0
            self.assertTrue(serverdensity_device.update('51f7eaf', name='lama'))

            with patch.object(salt.utils.json, 'loads', self.mock_json_loads):
                self.assertRaises(CommandExecutionError,
                                  serverdensity_device.update, '51f7eaf',
                                  name='lama')

            MockRequests.flag = 1
            self.assertIsNone(serverdensity_device.update('51f7eaf',
                                                          name='lama'))

    # 'install_agent' function tests: 1

    def test_install_agent(self):
        '''
        Tests if it downloads Server Density installation agent,
        and installs sd-agent with agent_key.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(serverdensity_device.__pillar__,
                        {'serverdensity': {'account_url': 'salt'}}):
            with patch.dict(serverdensity_device.__salt__, {'cmd.run': mock}):
                with patch.dict(serverdensity_device.__opts__,
                                {'cachedir': '/'}):
                    self.assertTrue(serverdensity_device.install_agent('51f7e'))

    # 'install_agent_v2' function tests: 1

    def test_install_agent_v2(self):
        '''
        Tests if it downloads Server Density installation agent,
        and installs sd-agent with agent_key.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(serverdensity_device.__pillar__,
                        {'serverdensity': {'account_name': 'salt'}}):
            with patch.dict(serverdensity_device.__salt__, {'cmd.run': mock}):
                with patch.dict(serverdensity_device.__opts__,
                                {'cachedir': '/'}):
                    self.assertTrue(
                        serverdensity_device.install_agent(
                            '51f7e', agent_version=2))

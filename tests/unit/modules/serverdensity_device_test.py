# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import serverdensity_device
from salt.exceptions import CommandExecutionError

serverdensity_device.__salt__ = {}
serverdensity_device.__pillar__ = {}
serverdensity_device.__opts__ = {}


class MockJson(Exception):
    '''
    Mock SMTP_SSL class
    '''
    flag = None

    def loads(self, content):
        '''
        Mock loads method.
        '''
        if self.flag == 1:
            raise ValueError
        return content

    def dumps(self, dumps):
        '''
        Mock dumps method.
        '''
        if self.flag == 1:
            return None
        return dumps


class MockRequests(object):
    '''
    Mock smtplib class
    '''
    flag = None
    content = {"message": "Invalid token",
               "errors": [{"type": "invalid_token", "subject": "token"}]}
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


serverdensity_device.requests = MockRequests()
serverdensity_device.json = MockJson()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServerdensityDeviceTestCase(TestCase):
    '''
    TestCase for salt.modules.serverdensity_device
    '''
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

            MockJson.flag = 1
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
            MockJson.flag = 0
            self.assertTrue(serverdensity_device.delete('51f7eaf'))

            MockJson.flag = 1
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
            MockJson.flag = 0
            self.assertTrue(serverdensity_device.ls(name='lama'))

            MockJson.flag = 1
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
            MockJson.flag = 0
            self.assertTrue(serverdensity_device.update('51f7eaf', name='lama'))

            MockJson.flag = 1
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ServerdensityDeviceTestCase, needs_daemon=False)

# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Eric Radman <ericshane@eradman.com>`
'''

# Import Salt Libs
from __future__ import absolute_import

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
from salt.cloud.clouds import joyent


# Stubs
def fake_wait_for_ip(check_for_ip_fn,
                     interval=None,
                     timeout=None,
                     interval_multiplier=None):
    '''
    Callback that returns immediately instead of waiting
    '''
    assert isinstance(interval, int)
    assert isinstance(timeout, int)
    assert isinstance(interval_multiplier, int)
    return check_for_ip_fn()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class JoyentTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Unit TestCase for the salt.cloud.clouds.joyent module
    '''
    def setup_loader_modules(self):
        return {
            joyent: {
                '__utils__': {
                    'cloud.fire_event': MagicMock(),
                    'cloud.bootstrap': MagicMock()
                },
                '__opts__': {
                    'sock_dir': True,
                    'transport': True,
                    'providers': {'my_joyent': {}},
                    'profiles': {'my_joyent': {}}
                },
                '__active_provider_name__': 'my_joyent:joyent'
            }
        }

    def setUp(self):
        self.vm_ = {
            'profile': 'my_joyent',
            'name': 'vm3',
            'driver': 'joyent',
            'size': 'k4-highcpu-kvm-750M',
            'image': 'freebsd10',
            'location': 'us-east-1'
        }

    def tearDown(self):
        del self.vm_

    @patch('salt.utils.cloud.wait_for_ip', fake_wait_for_ip)
    def test_query_instance_init(self):
        '''
        Initial provisioning, no IP assigned
        '''
        # Not yet reachable
        reply = (200, {'state': 'provisioning'})
        with patch.object(joyent, 'show_instance', return_value=reply):
            result = joyent.query_instance(self.vm_)
        self.assertTrue(joyent.__utils__['cloud.fire_event'].called_once())
        self.assertEqual(result, None)

    @patch('salt.utils.cloud.wait_for_ip', fake_wait_for_ip)
    def test_query_instance_has_ip(self):
        '''
        IP address assigned but not yet ready
        '''
        reply = (200, {'primaryIp': '1.1.1.1', 'state': 'provisioning'})
        with patch.object(joyent, 'show_instance', return_value=reply):
            result = joyent.query_instance(self.vm_)
        self.assertTrue(joyent.__utils__['cloud.fire_event'].called_once())
        self.assertEqual(result, None)

    @patch('salt.utils.cloud.wait_for_ip', fake_wait_for_ip)
    def test_query_instance_ready(self):
        '''
        IP address assigned, and VM is ready
        '''
        reply = (200, {'primaryIp': '1.1.1.1', 'state': 'running'})
        with patch.object(joyent, 'show_instance', return_value=reply):
            result = joyent.query_instance(self.vm_)
        self.assertTrue(joyent.__utils__['cloud.fire_event'].called_once())
        self.assertEqual(result, '1.1.1.1')

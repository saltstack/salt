# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Eric Radman <ericshane@eradman.com>`
'''

# Import Salt Libs
from __future__ import absolute_import
import json

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    mock_open,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.cloud.clouds import joyent

ensure_in_syspath('../../../')

# Globals
joyent.__utils__ = dict()
joyent.__opts__ = dict()


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
class JoyentTestCase(TestCase):
    '''
    Unit TestCase for the salt.cloud.clouds.joyent module
    '''
    joyent.__utils__ = {
        'cloud.fire_event': MagicMock(),
        'cloud.bootstrap': MagicMock()
    }
    joyent.__opts__ = {
        'sock_dir': True,
        'transport': True,
        'providers': {'my_joyent': {}},
        'profiles': {'my_joyent': {}}
    }
    vm_ = {
        'profile': 'my_joyent',
        'name': 'vm3',
        'driver': 'joyent',
        'size': 'k4-highcpu-kvm-750M',
        'image': 'freebsd10',
        'location': 'us-east-1'
    }
    joyent.__active_provider_name__ = 'my_joyent:joyent'

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

    @patch('salt.config.is_profile_configured', MagicMock(return_value=True))
    @patch('salt.utils.fopen', mock_open())
    @patch('Crypto.PublicKey.RSA.importKey', MagicMock())
    @patch('Crypto.Signature.PKCS1_v1_5.new', MagicMock())
    @patch('base64.b64encode', MagicMock())
    def test_create_fail(self):
        '''
        Test behavior when node creation failed because of an invalid profile
        option
        '''
        image = {'name': '39a87f12-034c-11e6-84f5-4316cc1fcaa0'}
        size = {'name': 'k4-highcpu-kvm-750M'}
        show_reply = {}
        query_ret = {'error': 'Unable to create machine', 'status': 0}
        with patch.object(joyent, 'get_image', return_value=image):
            with patch.object(joyent, 'get_size', return_value=size):
                with patch.object(joyent, 'show_instance', return_value=show_reply):
                    with patch('salt.utils.http.query', return_value=query_ret) as http_mock:
                        result = joyent.create(self.vm_)
        self.assertEqual(http_mock.call_args[0],
            ('https://us-east-1.api.joyentcloud.com//my/machines', 'POST'))
        self.assertDictEqual(json.loads(http_mock.call_args[1]['data']), {
            'image': '39a87f12-034c-11e6-84f5-4316cc1fcaa0',
            'name': 'vm3',
            'package': 'k4-highcpu-kvm-750M'
        })
        self.assertEqual(http_mock.call_args[1]['header_dict']['Content-Type'],
            'application/json')
        self.assertEqual(result, False)  # Deploy failed

if __name__ == '__main__':
    from integration import run_tests
    run_tests(JoyentTestCase, needs_daemon=False)

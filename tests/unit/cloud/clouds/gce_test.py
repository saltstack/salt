# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.gce_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import libcloud.security
import platform
import os

# Import Salt Libs
from salt.cloud.clouds import gce
from salt.exceptions import SaltCloudSystemExit

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../../')

# Global Variables
gce.__active_provider_name__ = ''
gce.__opts__ = {
    'providers': {
        'my-google-cloud': {
            'gce': {
                'project': 'daenerys-cloud',
                'service_account_email_address': 'dany@targaryen.westeros.cloud',
                'service_account_private_key': '/home/dany/PRIVKEY.pem',
                'driver': 'gce',
                'ssh_interface': 'public_ips'
            }
        }
    }
}
VM_NAME = 'kings_landing'
DUMMY_TOKEN = {
    'refresh_token': None,
    'client_id': 'dany123',
    'client_secret': 'lalalalalalala',
    'grant_type': 'refresh_token'
}

HAS_CERTS = True
ON_SUSE = True if 'SuSE' in platform.dist() else False
ON_MAC = True if 'Darwin' in platform.system() else False

if not os.path.exists('/etc/ssl/certs/YaST-CA.pem') and ON_SUSE:
    if os.path.isfile('/etc/ssl/ca-bundle.pem'):
        libcloud.security.CA_CERTS_PATH.append('/etc/ssl/ca-bundle.pem')
    else:
        HAS_CERTS = False
elif ON_MAC:
    if os.path.isfile('/opt/local/share/curl/curl-ca-bundle.crt'):
        pass  # libcloud will already find this file
    elif os.path.isfile('/usr/local/etc/openssl/cert.pem'):
        pass  # libcloud will already find this file
    else:
        HAS_CERTS = False


class ExtendedTestCase(TestCase):
    '''
    Extended TestCase class containing additional helper methods.
    '''

    def assertRaisesWithMessage(self, exc_type, exc_msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            self.assertFail()
        except Exception as exc:
            self.assertEqual(type(exc), exc_type)
            self.assertEqual(exc.message, exc_msg)


@skipIf(not HAS_CERTS, 'Cannot find CA cert bundle')
@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.cloud.clouds.gce.__virtual__', MagicMock(return_value='gce'))
@patch('libcloud.common.google.GoogleInstalledAppAuthConnection.get_new_token', MagicMock(return_value=DUMMY_TOKEN))
@patch('libcloud.compute.drivers.gce.GCENodeDriver.ex_list_zones', MagicMock(return_value=[]))
@patch('libcloud.compute.drivers.gce.GCENodeDriver.ex_list_regions', MagicMock(return_value=[]))
class GCETestCase(ExtendedTestCase):
    '''
    Unit TestCase for salt.cloud.clouds.gce module.
    '''

    def test_destroy_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call destroy
        with --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            gce.destroy,
            vm_name=VM_NAME,
            call='function'
        )

    @patch('libcloud.compute.drivers.gce.GCENodeDriver.list_sizes', MagicMock(return_value=[]))
    def test_avail_sizes(self):
        '''
        Tests that avail_sizes returns an empty dictionary.
        '''
        sizes = gce.avail_sizes()
        self.assertEqual(
            sizes,
            []
            )

    @patch('libcloud.compute.drivers.gce.GCENodeDriver.list_nodes', MagicMock(return_value=[]))
    def test_list_nodes(self):
        nodes = gce.list_nodes()
        self.assertEqual(
            nodes,
            {}
        )

    @patch('libcloud.compute.drivers.gce.GCENodeDriver.list_locations', MagicMock(return_value=[]))
    def test_list_locations(self):
        locations = gce.avail_locations()
        self.assertEqual(
            locations,
            {}
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GCETestCase, needs_daemon=False)

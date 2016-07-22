# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.gce_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import libcloud.security


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

# Use certifi if installed
try:
    import certifi
except ImportError:
    libcloud.security.CA_CERTS_PATH.append(certifi.where())



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

    def test_virtual(self):
        v = gce.__virtual__()
        self.assertEqual(v, 'gce')

    def test_provider_matches(self):
        """
        Test that the first configured instance of a gce driver is matched
        """
        p = gce.get_configured_provider()
        self.assertNotNone(p)

if __name__ == '__main__':
    from unit import run_tests
    run_tests(GCETestCase, needs_daemon=False)

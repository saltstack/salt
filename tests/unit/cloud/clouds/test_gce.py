# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.gce_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
from distutils.version import LooseVersion

try:
    import libcloud.security
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Import Salt Libs
from salt.cloud.clouds import gce
from salt.exceptions import SaltCloudSystemExit

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, __version__ as mock_version

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

# Use certifi if installed
try:
    if HAS_LIBCLOUD:
        import certifi
        libcloud.security.CA_CERTS_PATH.append(certifi.where())
except ImportError:
    pass


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GCETestCase(TestCase):
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

    def test_fail_virtual_missing_deps(self):
        # Missing deps
        with patch('salt.config.check_driver_dependencies', return_value=False):
            v = gce.__virtual__()
            self.assertEqual(v, False)

    def test_fail_virtual_deps_missing_config(self):
        with patch('salt.config.check_driver_dependencies', return_value=True):
            with patch('salt.config.is_provider_configured', return_value=False):
                v = gce.__virtual__()
                self.assertEqual(v, False)

    def test_import(self):
        """
        Test that the module picks up installed deps
        """
        with patch('salt.config.check_driver_dependencies', return_value=True) as p:
            get_deps = gce.get_dependencies()
            self.assertEqual(get_deps, True)
            if LooseVersion(mock_version) >= LooseVersion('2.0.0'):
                p.assert_called_once()

    def test_provider_matches(self):
        """
        Test that the first configured instance of a gce driver is matched
        """
        p = gce.get_configured_provider()
        self.assertNotEqual(p, None)

# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.dimensiondata_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

try:
    import libcloud.security
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Import Salt Libs
from salt.cloud.clouds import dimensiondata
from salt.exceptions import SaltCloudSystemExit
from salt.utils.versions import LooseVersion

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch, __version__ as mock_version

# Global Variables
dimensiondata.__active_provider_name__ = ''
dimensiondata.__opts__ = {
    'providers': {
        'my-dimensiondata-cloud': {
            'dimensiondata': {
                'driver': 'dimensiondata',
                'region': 'dd-au',
                'user_id': 'jon_snow',
                'key': 'IKnowNothing'
            }
        }
    }
}
VM_NAME = 'winterfell'

# Use certifi if installed
try:
    if HAS_LIBCLOUD:
        import certifi
        libcloud.security.CA_CERTS_PATH.append(certifi.where())
except ImportError:
    pass


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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.cloud.clouds.dimensiondata.__virtual__', MagicMock(return_value='dimensiondata'))
class DimensionDataTestCase(ExtendedTestCase):
    '''
    Unit TestCase for salt.cloud.clouds.dimensiondata module.
    '''

    def test_avail_images_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_images
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            dimensiondata.avail_images,
            call='action'
        )

    def test_avail_locations_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_locations
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            dimensiondata.avail_locations,
            call='action'
        )

    def test_avail_sizes_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_sizes
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            dimensiondata.avail_sizes,
            call='action'
        )

    def test_list_nodes_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            dimensiondata.list_nodes,
            call='action'
        )

    def test_destroy_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call destroy
        with --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            dimensiondata.destroy,
            name=VM_NAME,
            call='function'
        )

    @skipIf(HAS_LIBCLOUD is False, 'libcloud not found')
    def test_avail_sizes(self):
        '''
        Tests that avail_sizes returns an empty dictionary.
        '''
        sizes = dimensiondata.avail_sizes(call='foo')
        self.assertEqual(
            len(sizes),
            1
        )
        self.assertEqual(
            sizes['default']['name'],
            'default'
        )

    def test_import(self):
        """
        Test that the module picks up installed deps
        """
        with patch('salt.config.check_driver_dependencies', return_value=True) as p:
            get_deps = dimensiondata.get_dependencies()
            self.assertEqual(get_deps, True)
            if LooseVersion(mock_version) >= LooseVersion('2.0.0'):
                self.assertTrue(p.call_count >= 1)

    def test_provider_matches(self):
        """
        Test that the first configured instance of a dimensiondata driver is matched
        """
        p = dimensiondata.get_configured_provider()
        self.assertNotEqual(p, None)

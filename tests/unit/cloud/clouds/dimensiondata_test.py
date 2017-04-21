# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.dimensiondata_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
from distutils.version import LooseVersion
import mock

try:
    import libcloud.security
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Import Salt Libs
from salt.cloud.clouds import dimensiondata
from salt.exceptions import SaltCloudSystemExit

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../../')

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
    import certifi
    libcloud.security.CA_CERTS_PATH.append(certifi.where())
except (ImportError, NameError):
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
            if LooseVersion(mock.__version__) >= LooseVersion('2.0.0'):
                p.assert_called_once()

    def test_provider_matches(self):
        """
        Test that the first configured instance of a dimensiondata driver is matched
        """
        p = dimensiondata.get_configured_provider()
        self.assertNotEqual(p, None)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(DimensionDataTestCase, needs_daemon=False)

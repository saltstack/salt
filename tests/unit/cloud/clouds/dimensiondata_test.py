# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.dimensiondata_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import libcloud.security
import platform
import os

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

ON_SUSE = False
if 'SuSE' in platform.dist():
    ON_SUSE = True

if not os.path.exists('/etc/ssl/certs/YaST-CA.pem') and ON_SUSE:
    libcloud.security.CA_CERTS_PATH.append('/etc/ssl/ca-bundle.pem')


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

    @patch('libcloud.compute.drivers.dimensiondata.DimensionDataNodeDriver.list_nodes', MagicMock(return_value=[]))
    def test_list_nodes(self):
        nodes = dimensiondata.list_nodes()
        self.assertEqual(
            nodes,
            {}
        )

    @patch('libcloud.compute.drivers.dimensiondata.DimensionDataNodeDriver.list_locations', MagicMock(return_value=[]))
    def test_list_locations(self):
        locations = dimensiondata.avail_locations()
        self.assertEqual(
            locations,
            {}
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DimensionDataTestCase, needs_daemon=False)

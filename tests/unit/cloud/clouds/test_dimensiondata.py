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
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch, __version__ as mock_version
from tests.unit.cloud.clouds import _preferred_ip

VM_NAME = 'winterfell'

# Use certifi if installed
try:
    if HAS_LIBCLOUD:
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
class DimensionDataTestCase(ExtendedTestCase, LoaderModuleMockMixin):
    '''
    Unit TestCase for salt.cloud.clouds.dimensiondata module.
    '''

    def setup_loader_modules(self):
        return {
            dimensiondata: {
                '__active_provider_name__': '',
                '__opts__': {
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
            }
        }

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

    @skipIf(HAS_LIBCLOUD is False, "Install 'libcloud' to be able to run this unit test.")
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

    PRIVATE_IPS = ['0.0.0.0', '1.1.1.1', '2.2.2.2']

    @patch('salt.cloud.clouds.dimensiondata.show_instance',
           MagicMock(return_value={'state': True,
                                   'name': 'foo',
                                   'public_ips': [],
                                   'private_ips': PRIVATE_IPS}))
    @patch('salt.cloud.clouds.dimensiondata.preferred_ip', _preferred_ip(PRIVATE_IPS, ['0.0.0.0']))
    @patch('salt.cloud.clouds.dimensiondata.ssh_interface', MagicMock(return_value='private_ips'))
    def test_query_node_data_filter_preferred_ip_addresses(self):
        '''
        Test if query node data is filtering out unpreferred IP addresses.
        '''
        dimensiondata.NodeState = MagicMock()
        dimensiondata.NodeState.RUNNING = True
        dimensiondata.__opts__ = {}

        vm = {'name': None}
        data = MagicMock()
        data.public_ips = []

        assert dimensiondata._query_node_data(vm, data).public_ips == ['0.0.0.0']

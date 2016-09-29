# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

Tests for datacenter related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging
# Import Salt testing libraries
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

from salt.exceptions import VMwareObjectRetrievalError

# Import Salt libraries
import salt.utils.vmware as vmware
# Import Third Party Libs
try:
    from pyVmomi import vim
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_mors_with_properties',
       MagicMock(return_value=[{'name': 'fake_dc', 'object': MagicMock()}]))
class GetDatacenterTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_datacenter'''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_properties = [MagicMock()]
        self.mock_dc1 = MagicMock()
        self.mock_dc2 = MagicMock()
        self.mock_entries = [{'name': 'fake_dc1',
                              'object': self.mock_dc1},
                             {'name': 'fake_dc2',
                              'object': self.mock_dc2}]

    def test_get_mors_with_properties_call(self):
        mock_get_mors_with_properties = MagicMock(
            return_value=[{'name': 'fake_dc', 'object': MagicMock()}])
        with patch('salt.utils.vmware.get_mors_with_properties',
                   mock_get_mors_with_properties):
            vmware.get_datacenter(self.mock_si, 'fake_dc')
        mock_get_mors_with_properties.assert_called_once_with(
            self.mock_si, vim.Datacenter, property_list=['name'])

    def test_get_mors_with_properties_returns_empty_array(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vmware.get_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(excinfo.exception.strerror,
                         'Datacenter \'fake_dc\' was not found')

    def test_datastore_not_found(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vmware.get_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(excinfo.exception.strerror,
                         'Datacenter \'fake_dc\' was not found')

    def test_datastore_found(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = vmware.get_datacenter(self.mock_si, 'fake_dc2')
        self.assertEqual(res, self.mock_dc2)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GetDatacenterTestCase, needs_daemon=False)

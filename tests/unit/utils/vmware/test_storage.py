# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for storage related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock
from salt.exceptions import VMwareObjectRetrievalError, VMwareApiError, \
        ArgumentValueError, VMwareRuntimeError

#i Import Salt libraries
import salt.utils.vmware
# Import Third Party Libs
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)

@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetStorageSystemTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_storage_system'''
    def setUp(self):
        self.mock_si = MagicMock(content=MagicMock())
        self.mock_host_ref = MagicMock()
        self.mock_get_managed_object_name = MagicMock(return_value='fake_host')
        self.mock_traversal_spec = MagicMock()
        self.mock_obj = MagicMock()
        self.mock_get_mors = \
             MagicMock(return_value=[{'object': self.mock_obj}])

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             self.mock_get_managed_object_name),
            ('salt.utils.vmware.get_mors_with_properties',
             self.mock_get_mors),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
             MagicMock(return_value=self.mock_traversal_spec)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_host_ref',
                     'mock_get_managed_object_name',
                     'mock_traversal_spec', 'mock_obj'):
            delattr(self, attr)

    def test_no_hostname_argument(self):
        salt.utils.vmware.get_storage_system(self.mock_si,
                                             self.mock_host_ref)
        self.mock_get_managed_object_name.assert_called_once_with(
            self.mock_host_ref)

    def test_hostname_argument(self):
        salt.utils.vmware.get_storage_system(self.mock_si,
                                             self.mock_host_ref,
                                             hostname='fake_host')
        self.assertEqual(self.mock_get_managed_object_name.call_count, 0)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value=[{'object':
                                                       self.mock_obj}])
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            salt.utils.vmware.get_storage_system(self.mock_si,
                                                 self.mock_host_ref)
        mock_traversal_spec.assert_called_once_with(
            path='configManager.storageSystem',
            type=vim.HostSystem,
            skip=False)

    def test_get_mors_with_properties(self):
        salt.utils.vmware.get_storage_system(self.mock_si,
                                             self.mock_host_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si,
            vim.HostStorageSystem,
            property_list=['systemFile'],
            container_ref=self.mock_host_ref,
            traversal_spec=self.mock_traversal_spec)

    def test_empty_mors_result(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                salt.utils.vmware.get_storage_system(self.mock_si,
                                                     self.mock_host_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Host\'s \'fake_host\' storage system was '
                         'not retrieved')

    def test_valid_mors_result(self):
        res = salt.utils.vmware.get_storage_system(self.mock_si,
                                                   self.mock_host_ref)
        self.assertEqual(res, self.mock_obj)

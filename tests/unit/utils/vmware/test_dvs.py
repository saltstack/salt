# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for dvs related functions in salt.utils.vmware
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
import salt.utils.vmware as vmware
# Import Third Party Libs
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


class FakeTaskClass(object):
    pass


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetDvssTestCase(TestCase):
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_dc_ref = MagicMock()
        self.mock_traversal_spec = MagicMock()
        self.mock_items = [{'object': MagicMock(),
                            'name': 'fake_dvs1'},
                           {'object': MagicMock(),
                            'name': 'fake_dvs2'},
                           {'object': MagicMock(),
                            'name': 'fake_dvs3'}]
        self.mock_get_mors = MagicMock(return_value=self.mock_items)

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock()),
            ('salt.utils.vmware.get_mors_with_properties',
             self.mock_get_mors),
            ('salt.utils.vmware.get_service_instance_from_managed_object',
             MagicMock(return_value=self.mock_si)),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
             MagicMock(return_value=self.mock_traversal_spec)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_dc_ref', 'mock_traversal_spec',
                     'mock_items', 'mock_get_mors'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.get_dvss(self.mock_dc_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            vmware.get_dvss(self.mock_dc_ref)
        mock_traversal_spec.assert_called(
            call(path='networkFolder', skip=True, type=vim.Datacenter,
                 selectSet=['traversal_spec']),
            call(path='childEntity', skip=False, type=vim.Folder))

    def test_get_mors_with_properties(self):
        vmware.get_dvss(self.mock_dc_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.DistributedVirtualSwitch,
            container_ref=self.mock_dc_ref, property_list=['name'],
            traversal_spec=self.mock_traversal_spec)

    def test_get_no_dvss(self):
        ret = vmware.get_dvss(self.mock_dc_ref)
        self.assertEqual(ret, [])

    def test_get_all_dvss(self):
        ret = vmware.get_dvss(self.mock_dc_ref, get_all_dvss=True)
        self.assertEqual(ret, [i['object'] for i in self.mock_items])

    def test_filtered_all_dvss(self):
        ret = vmware.get_dvss(self.mock_dc_ref,
                              dvs_names=['fake_dvs1', 'fake_dvs3', 'no_dvs'])
        self.assertEqual(ret, [self.mock_items[0]['object'],
                               self.mock_items[2]['object']])

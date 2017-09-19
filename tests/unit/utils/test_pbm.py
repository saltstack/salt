# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests functions in salt.utils.vsan
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, \
        PropertyMock

# Import Salt libraries
from salt.exceptions import VMwareApiError, VMwareRuntimeError
import salt.utils.pbm

try:
    from pyVmomi import vim, vmodl, pbm
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False


# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetProfileManagerTestCase(TestCase):
    '''Tests for salt.utils.pbm.get_profile_manager'''
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_stub = MagicMock()
        self.mock_prof_mgr = MagicMock()
        self.mock_content = MagicMock()
        self.mock_pbm_si = MagicMock(
            RetrieveContent=MagicMock(return_value=self.mock_content))
        type(self.mock_content).profileManager = \
                PropertyMock(return_value=self.mock_prof_mgr)
        patches = (
            ('salt.utils.vmware.get_new_service_instance_stub',
             MagicMock(return_value=self.mock_stub)),
            ('salt.utils.pbm.pbm.ServiceInstance',
             MagicMock(return_value=self.mock_pbm_si)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_stub', 'mock_content',
                     'mock_pbm_si', 'mock_prof_mgr'):
            delattr(self, attr)

    def test_get_new_service_stub(self):
        mock_get_new_service_stub = MagicMock()
        with patch('salt.utils.vmware.get_new_service_instance_stub',
                   mock_get_new_service_stub):
            salt.utils.pbm.get_profile_manager(self.mock_si)
        mock_get_new_service_stub.assert_called_once_with(
            self.mock_si, ns='pbm/2.0', path='/pbm/sdk')

    def test_pbm_si(self):
        mock_get_pbm_si = MagicMock()
        with patch('salt.utils.pbm.pbm.ServiceInstance',
                   mock_get_pbm_si):
            salt.utils.pbm.get_profile_manager(self.mock_si)
        mock_get_pbm_si.assert_called_once_with('ServiceInstance',
                                                self.mock_stub)

    def test_return_profile_manager(self):
        ret = salt.utils.pbm.get_profile_manager(self.mock_si)
        self.assertEqual(ret, self.mock_prof_mgr)

    def test_profile_manager_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_content).profileManager = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_profile_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_profile_manager_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_content).profileManager = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_profile_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_profile_manager_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_content).profileManager = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.get_profile_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetPlacementSolverTestCase(TestCase):
    '''Tests for salt.utils.pbm.get_placement_solver'''
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_stub = MagicMock()
        self.mock_prof_mgr = MagicMock()
        self.mock_content = MagicMock()
        self.mock_pbm_si = MagicMock(
            RetrieveContent=MagicMock(return_value=self.mock_content))
        type(self.mock_content).placementSolver = \
                PropertyMock(return_value=self.mock_prof_mgr)
        patches = (
            ('salt.utils.vmware.get_new_service_instance_stub',
             MagicMock(return_value=self.mock_stub)),
            ('salt.utils.pbm.pbm.ServiceInstance',
             MagicMock(return_value=self.mock_pbm_si)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_stub', 'mock_content',
                     'mock_pbm_si', 'mock_prof_mgr'):
            delattr(self, attr)

    def test_get_new_service_stub(self):
        mock_get_new_service_stub = MagicMock()
        with patch('salt.utils.vmware.get_new_service_instance_stub',
                   mock_get_new_service_stub):
            salt.utils.pbm.get_placement_solver(self.mock_si)
        mock_get_new_service_stub.assert_called_once_with(
            self.mock_si, ns='pbm/2.0', path='/pbm/sdk')

    def test_pbm_si(self):
        mock_get_pbm_si = MagicMock()
        with patch('salt.utils.pbm.pbm.ServiceInstance',
                   mock_get_pbm_si):
            salt.utils.pbm.get_placement_solver(self.mock_si)
        mock_get_pbm_si.assert_called_once_with('ServiceInstance',
                                                self.mock_stub)

    def test_return_profile_manager(self):
        ret = salt.utils.pbm.get_placement_solver(self.mock_si)
        self.assertEqual(ret, self.mock_prof_mgr)

    def test_placement_solver_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_content).placementSolver = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_placement_solver(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_placement_solver_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_content).placementSolver = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_placement_solver(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_placement_solver_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_content).placementSolver = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.get_placement_solver(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetCapabilityDefinitionsTestCase(TestCase):
    '''Tests for salt.utils.pbm.get_capability_definitions'''
    def setUp(self):
        self.mock_res_type = MagicMock()
        self.mock_cap_cats =[MagicMock(capabilityMetadata=['fake_cap_meta1',
                                                           'fake_cap_meta2']),
                             MagicMock(capabilityMetadata=['fake_cap_meta3'])]
        self.mock_prof_mgr = MagicMock(
            FetchCapabilityMetadata=MagicMock(return_value=self.mock_cap_cats))
        patches = (
            ('salt.utils.pbm.pbm.profile.ResourceType',
             MagicMock(return_value=self.mock_res_type)),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_res_type', 'mock_cap_cats', 'mock_prof_mgr'):
            delattr(self, attr)

    def test_get_res_type(self):
        mock_get_res_type = MagicMock()
        with patch('salt.utils.pbm.pbm.profile.ResourceType',
                   mock_get_res_type):
            salt.utils.pbm.get_capability_definitions(self.mock_prof_mgr)
        mock_get_res_type.assert_called_once_with(
            resourceType=pbm.profile.ResourceTypeEnum.STORAGE)

    def test_fetch_capabilities(self):
        salt.utils.pbm.get_capability_definitions(self.mock_prof_mgr)
        self.mock_prof_mgr.FetchCapabilityMetadata.assert_callend_once_with(
            self.mock_res_type)

    def test_fetch_capabilities_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_prof_mgr.FetchCapabilityMetadata = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_capability_definitions(self.mock_prof_mgr)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_fetch_capabilities_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_prof_mgr.FetchCapabilityMetadata = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_capability_definitions(self.mock_prof_mgr)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_fetch_capabilities_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_prof_mgr.FetchCapabilityMetadata = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.get_capability_definitions(self.mock_prof_mgr)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_return_cap_definitions(self):
        ret = salt.utils.pbm.get_capability_definitions(self.mock_prof_mgr)
        self.assertEqual(ret, ['fake_cap_meta1', 'fake_cap_meta2',
                               'fake_cap_meta3'])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetPoliciesByIdTestCase(TestCase):
    '''Tests for salt.utils.pbm.get_policies_by_id'''
    def setUp(self):
        self.policy_ids = MagicMock()
        self.mock_policies = MagicMock()
        self.mock_prof_mgr = MagicMock(
            RetrieveContent=MagicMock(return_value=self.mock_policies))

    def tearDown(self):
        for attr in ('policy_ids', 'mock_policies', 'mock_prof_mgr'):
            delattr(self, attr)

    def test_retrieve_policies(self):
        salt.utils.pbm.get_policies_by_id(self.mock_prof_mgr, self.policy_ids)
        self.mock_prof_mgr.RetrieveContent.assert_callend_once_with(
            self.policy_ids)

    def test_retrieve_policies_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_prof_mgr.RetrieveContent = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_policies_by_id(self.mock_prof_mgr, self.policy_ids)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_retrieve_policies_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_prof_mgr.RetrieveContent = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_policies_by_id(self.mock_prof_mgr, self.policy_ids)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_retrieve_policies_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_prof_mgr.RetrieveContent = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.get_policies_by_id(self.mock_prof_mgr, self.policy_ids)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_return_policies(self):
        ret = salt.utils.pbm.get_policies_by_id(self.mock_prof_mgr, self.policy_ids)
        self.assertEqual(ret, self.mock_policies)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetStoragePoliciesTestCase(TestCase):
    '''Tests for salt.utils.pbm.get_storage_policies'''
    def setUp(self):
        self.mock_res_type = MagicMock()
        self.mock_policy_ids = MagicMock()
        self.mock_prof_mgr = MagicMock(
            QueryProfile=MagicMock(return_value=self.mock_policy_ids))
        # Policies
        self.mock_policies=[]
        for i in range(4):
            mock_obj = MagicMock(resourceType=MagicMock(
                resourceType=pbm.profile.ResourceTypeEnum.STORAGE))
            mock_obj.name = 'fake_policy{0}'.format(i)
            self.mock_policies.append(mock_obj)
        patches = (
            ('salt.utils.pbm.pbm.profile.ResourceType',
             MagicMock(return_value=self.mock_res_type)),
            ('salt.utils.pbm.get_policies_by_id',
             MagicMock(return_value=self.mock_policies)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_res_type', 'mock_policy_ids', 'mock_policies',
                     'mock_prof_mgr'):
            delattr(self, attr)

    def test_get_res_type(self):
        mock_get_res_type = MagicMock()
        with patch('salt.utils.pbm.pbm.profile.ResourceType',
                   mock_get_res_type):
            salt.utils.pbm.get_storage_policies(self.mock_prof_mgr)
        mock_get_res_type.assert_called_once_with(
            resourceType=pbm.profile.ResourceTypeEnum.STORAGE)

    def test_retrieve_policy_ids(self):
        mock_retrieve_policy_ids = MagicMock(return_value=self.mock_policy_ids)
        self.mock_prof_mgr.QueryProfile = mock_retrieve_policy_ids
        salt.utils.pbm.get_storage_policies(self.mock_prof_mgr)
        mock_retrieve_policy_ids.assert_called_once_with(self.mock_res_type)

    def test_retrieve_policy_ids_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_prof_mgr.QueryProfile = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_storage_policies(self.mock_prof_mgr)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_retrieve_policy_ids_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_prof_mgr.QueryProfile = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_storage_policies(self.mock_prof_mgr)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_retrieve_policy_ids_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_prof_mgr.QueryProfile = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.get_storage_policies(self.mock_prof_mgr)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_get_policies_by_id(self):
        mock_get_policies_by_id = MagicMock(return_value=self.mock_policies)
        with patch('salt.utils.pbm.get_policies_by_id',
                   mock_get_policies_by_id):
            salt.utils.pbm.get_storage_policies(self.mock_prof_mgr)
        mock_get_policies_by_id.assert_called_once_with(
            self.mock_prof_mgr, self.mock_policy_ids)

    def test_return_all_policies(self):
        ret = salt.utils.pbm.get_storage_policies(self.mock_prof_mgr,
                                                  get_all_policies=True)
        self.assertEqual(ret, self.mock_policies)

    def test_return_filtered_policies(self):
        ret = salt.utils.pbm.get_storage_policies(
            self.mock_prof_mgr, policy_names=['fake_policy1', 'fake_policy3'])
        self.assertEqual(ret, [self.mock_policies[1], self.mock_policies[3]])

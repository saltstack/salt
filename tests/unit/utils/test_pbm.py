# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests functions in salt.utils.vsan
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, \
        PropertyMock

# Import Salt libraries
from salt.exceptions import VMwareApiError, VMwareRuntimeError, \
        VMwareObjectRetrievalError
from salt.ext.six.moves import range
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
        self.mock_cap_cats = [MagicMock(capabilityMetadata=['fake_cap_meta1',
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
        self.mock_prof_mgr.FetchCapabilityMetadata.assert_called_once_with(
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
        self.mock_prof_mgr.RetrieveContent.assert_called_once_with(
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
        self.mock_policies = []
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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class CreateStoragePolicyTestCase(TestCase):
    '''Tests for salt.utils.pbm.create_storage_policy'''
    def setUp(self):
        self.mock_policy_spec = MagicMock()
        self.mock_prof_mgr = MagicMock()

    def tearDown(self):
        for attr in ('mock_policy_spec', 'mock_prof_mgr'):
            delattr(self, attr)

    def test_create_policy(self):
        salt.utils.pbm.create_storage_policy(self.mock_prof_mgr,
                                             self.mock_policy_spec)
        self.mock_prof_mgr.Create.assert_called_once_with(
            self.mock_policy_spec)

    def test_create_policy_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_prof_mgr.Create = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.create_storage_policy(self.mock_prof_mgr,
                                                 self.mock_policy_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_policy_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_prof_mgr.Create = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.create_storage_policy(self.mock_prof_mgr,
                                                 self.mock_policy_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_policy_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_prof_mgr.Create = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.create_storage_policy(self.mock_prof_mgr,
                                                 self.mock_policy_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class UpdateStoragePolicyTestCase(TestCase):
    '''Tests for salt.utils.pbm.update_storage_policy'''
    def setUp(self):
        self.mock_policy_spec = MagicMock()
        self.mock_policy = MagicMock()
        self.mock_prof_mgr = MagicMock()

    def tearDown(self):
        for attr in ('mock_policy_spec', 'mock_policy', 'mock_prof_mgr'):
            delattr(self, attr)

    def test_create_policy(self):
        salt.utils.pbm.update_storage_policy(
            self.mock_prof_mgr, self.mock_policy, self.mock_policy_spec)
        self.mock_prof_mgr.Update.assert_called_once_with(
            self.mock_policy.profileId, self.mock_policy_spec)

    def test_create_policy_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_prof_mgr.Update = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.update_storage_policy(
                self.mock_prof_mgr, self.mock_policy, self.mock_policy_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_policy_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_prof_mgr.Update = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.update_storage_policy(
                self.mock_prof_mgr, self.mock_policy, self.mock_policy_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_policy_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_prof_mgr.Update = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.update_storage_policy(
                self.mock_prof_mgr, self.mock_policy, self.mock_policy_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetDefaultStoragePolicyOfDatastoreTestCase(TestCase):
    '''Tests for salt.utils.pbm.get_default_storage_policy_of_datastore'''
    def setUp(self):
        self.mock_ds = MagicMock(_moId='fake_ds_moid')
        self.mock_hub = MagicMock()
        self.mock_policy_id = 'fake_policy_id'
        self.mock_prof_mgr = MagicMock(
            QueryDefaultRequirementProfile=MagicMock(
                return_value=self.mock_policy_id))
        self.mock_policy_refs = [MagicMock()]
        patches = (
            ('salt.utils.pbm.pbm.placement.PlacementHub',
             MagicMock(return_value=self.mock_hub)),
            ('salt.utils.pbm.get_policies_by_id',
             MagicMock(return_value=self.mock_policy_refs)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_ds', 'mock_hub', 'mock_policy_id', 'mock_prof_mgr',
                     'mock_policy_refs'):
            delattr(self, attr)

    def test_get_placement_hub(self):
        mock_get_placement_hub = MagicMock()
        with patch('salt.utils.pbm.pbm.placement.PlacementHub',
                   mock_get_placement_hub):
            salt.utils.pbm.get_default_storage_policy_of_datastore(
                self.mock_prof_mgr, self.mock_ds)
        mock_get_placement_hub.assert_called_once_with(
            hubId='fake_ds_moid', hubType='Datastore')

    def test_query_default_requirement_profile(self):
        mock_query_prof = MagicMock(return_value=self.mock_policy_id)
        self.mock_prof_mgr.QueryDefaultRequirementProfile = \
                mock_query_prof
        salt.utils.pbm.get_default_storage_policy_of_datastore(
            self.mock_prof_mgr, self.mock_ds)
        mock_query_prof.assert_called_once_with(self.mock_hub)

    def test_query_default_requirement_profile_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_prof_mgr.QueryDefaultRequirementProfile = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_default_storage_policy_of_datastore(
                self.mock_prof_mgr, self.mock_ds)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_query_default_requirement_profile_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_prof_mgr.QueryDefaultRequirementProfile = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.get_default_storage_policy_of_datastore(
                self.mock_prof_mgr, self.mock_ds)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_query_default_requirement_profile_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_prof_mgr.QueryDefaultRequirementProfile = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.get_default_storage_policy_of_datastore(
                self.mock_prof_mgr, self.mock_ds)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_get_policies_by_id(self):
        mock_get_policies_by_id = MagicMock()
        with patch('salt.utils.pbm.get_policies_by_id',
                   mock_get_policies_by_id):
            salt.utils.pbm.get_default_storage_policy_of_datastore(
                self.mock_prof_mgr, self.mock_ds)
        mock_get_policies_by_id.assert_called_once_with(
            self.mock_prof_mgr, [self.mock_policy_id])

    def test_no_policy_refs(self):
        mock_get_policies_by_id = MagicMock()
        with patch('salt.utils.pbm.get_policies_by_id',
                  MagicMock(return_value=None)):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                salt.utils.pbm.get_default_storage_policy_of_datastore(
                    self.mock_prof_mgr, self.mock_ds)
        self.assertEqual(excinfo.exception.strerror,
                         'Storage policy with id \'fake_policy_id\' was not '
                         'found')

    def test_return_policy_ref(self):
        mock_get_policies_by_id = MagicMock()
        ret = salt.utils.pbm.get_default_storage_policy_of_datastore(
            self.mock_prof_mgr, self.mock_ds)
        self.assertEqual(ret, self.mock_policy_refs[0])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class AssignDefaultStoragePolicyToDatastoreTestCase(TestCase):
    '''Tests for salt.utils.pbm.assign_default_storage_policy_to_datastore'''
    def setUp(self):
        self.mock_ds = MagicMock(_moId='fake_ds_moid')
        self.mock_policy = MagicMock()
        self.mock_hub = MagicMock()
        self.mock_prof_mgr = MagicMock()
        patches = (
            ('salt.utils.pbm.pbm.placement.PlacementHub',
             MagicMock(return_value=self.mock_hub)),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_ds', 'mock_hub', 'mock_policy', 'mock_prof_mgr'):
            delattr(self, attr)

    def test_get_placement_hub(self):
        mock_get_placement_hub = MagicMock()
        with patch('salt.utils.pbm.pbm.placement.PlacementHub',
                   mock_get_placement_hub):
            salt.utils.pbm.assign_default_storage_policy_to_datastore(
                self.mock_prof_mgr, self.mock_policy, self.mock_ds)
        mock_get_placement_hub.assert_called_once_with(
            hubId='fake_ds_moid', hubType='Datastore')

    def test_assign_default_requirement_profile(self):
        mock_assign_prof = MagicMock()
        self.mock_prof_mgr.AssignDefaultRequirementProfile = \
                mock_assign_prof
        salt.utils.pbm.assign_default_storage_policy_to_datastore(
            self.mock_prof_mgr, self.mock_policy, self.mock_ds)
        mock_assign_prof.assert_called_once_with(
            self.mock_policy.profileId, [self.mock_hub])

    def test_assign_default_requirement_profile_raises_no_permissions(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_prof_mgr.AssignDefaultRequirementProfile = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.assign_default_storage_policy_to_datastore(
                self.mock_prof_mgr, self.mock_policy, self.mock_ds)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_assign_default_requirement_profile_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_prof_mgr.AssignDefaultRequirementProfile = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.pbm.assign_default_storage_policy_to_datastore(
                self.mock_prof_mgr, self.mock_policy, self.mock_ds)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_assign_default_requirement_profile_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_prof_mgr.AssignDefaultRequirementProfile = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.pbm.assign_default_storage_policy_to_datastore(
                self.mock_prof_mgr, self.mock_policy, self.mock_ds)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

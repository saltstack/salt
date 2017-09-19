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

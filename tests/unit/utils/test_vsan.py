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
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock

# Import Salt libraries
from salt.exceptions import VMwareApiError, VMwareRuntimeError
from salt.utils import vsan

try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False
HAS_PYVSAN = vsan.HAS_PYVSAN


# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class VsanSupportedTestCase(TestCase):
    '''Tests for salt.utils.vsan.vsan_supported'''

    def test_supported_api_version(self):
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = \
                PropertyMock(return_value='6.0')
        self.assertTrue(vsan.vsan_supported(mock_si))

    def test_unsupported_api_version(self):
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = \
                PropertyMock(return_value='5.0')
        self.assertFalse(vsan.vsan_supported(mock_si))

    def test_api_version_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.vsan_supported(mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_api_version_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.vsan_supported(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_api_version_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.vsan_supported(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class GetVsanClusterConfigSystemTestCase(TestCase, LoaderModuleMockMixin):
    '''Tests for salt.utils.vsan.get_vsan_cluster_config_system'''
    def setup_loader_modules(self):
        return {vsan: {
            '__virtual__': MagicMock(return_value='vsan'),
            'sys': MagicMock(),
            'ssl': MagicMock()}}

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_ret = MagicMock()
        patches = (('salt.utils.vsan.vsanapiutils.GetVsanVcMos',
                    MagicMock(
                        return_value={'vsan-cluster-config-system':
                                      self.mock_ret})),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

        type(vsan.sys).version_info = PropertyMock(return_value=(2,7,9))
        self.mock_context = MagicMock()
        self.mock_create_default_context = \
                MagicMock(return_value=self.mock_context)
        vsan.ssl.create_default_context = self.mock_create_default_context

    def tearDown(self):
        for attr in ('mock_si', 'mock_ret', 'mock_context',
                     'mock_create_default_context'):
            delattr(self, attr)

    def test_ssl_default_context_loaded(self):
        vsan.get_vsan_cluster_config_system(self.mock_si)
        self.mock_create_default_context.assert_called_once_with()
        self.assertFalse(self.mock_context.check_hostname)
        self.assertEqual(self.mock_context.verify_mode, vsan.ssl.CERT_NONE)

    def test_ssl_default_context_not_loaded(self):
        type(vsan.sys).version_info = PropertyMock(return_value=(2,7,8))
        vsan.get_vsan_cluster_config_system(self.mock_si)
        self.assertEqual(self.mock_create_default_context.call_count, 0)

    def test_GetVsanVcMos_call(self):
        mock_get_vsan_vc_mos = MagicMock()
        with patch('salt.utils.vsan.vsanapiutils.GetVsanVcMos',
                   mock_get_vsan_vc_mos):
            vsan.get_vsan_cluster_config_system(self.mock_si)
        mock_get_vsan_vc_mos.assert_called_once_with(self.mock_si._stub,
                                                     context=self.mock_context)

    def test_return(self):
        ret = vsan.get_vsan_cluster_config_system(self.mock_si)
        self.assertEqual(ret, self.mock_ret)

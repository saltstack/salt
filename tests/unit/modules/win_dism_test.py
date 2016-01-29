# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import win_dism as dism

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch
)

ensure_in_syspath('../../')

dism.__salt__ = {}


class DISMTestCase(TestCase):

    def test_install_capability(self):
        '''
            Test installing a capability with DISM
        '''
        mock = MagicMock()
        with patch.dict(dism.__salt__, {'cmd.run_all': mock}):
            dism.install_capability("test")
            mock.assert_called_once_with('DISM /Online /Add-Capability /CapabilityName:test')

    def test_install_capability_with_extras(self):
        '''
            Test installing a capability with DISM
        '''
        mock = MagicMock()
        with patch.dict(dism.__salt__, {'cmd.run_all': mock}):
            dism.install_capability("test", "life", True)
            mock.assert_called_once_with('DISM /Online /Add-Capability /CapabilityName:test /Source:life /LimitAccess')

    def test_uninstall_capability(self):
        '''
            Test uninstalling a capability with DISM
        '''
        mock = MagicMock()
        with patch.dict(dism.__salt__, {'cmd.run_all': mock}):
            dism.uninstall_capability("test")
            mock.assert_called_once_with('DISM /Online /Remove-Capability /CapabilityName:test')

    def test_installed_capabilities(self):
        '''
            Test getting all the installed capabilities
        '''
        capabilties = "Capability Identity : Capa1\r\n State : Installed\r\n" \
                      "Capability Identity : Capa2\r\n State : Disabled\r\n"

        mock = MagicMock(return_value=capabilties)
        with patch.dict(dism.__salt__, {'cmd.run': mock}):
            out = dism.installed_capabilities()
            mock.assert_called_once_with('DISM /Online /Get-Capabilities')
            self.assertEqual(out, ["Capa1"])

    def test_install_feature(self):
        '''
            Test installing a feature with DISM
        '''
        mock = MagicMock()
        with patch.dict(dism.__salt__, {'cmd.run_all': mock}):
            dism.install_feature("test")
            mock.assert_called_once_with('DISM /Online /Enable-Feature /FeatureName:test')

    def test_uninstall_feature(self):
        '''
            Test uninstalling a capability with DISM
        '''
        mock = MagicMock()
        with patch.dict(dism.__salt__, {'cmd.run_all': mock}):
            dism.uninstall_feature("test")
            mock.assert_called_once_with('DISM /Online /Disable-Feature /FeatureName:test')

    def test_installed_feature(self):
        '''
            Test getting all the installed capabilities
        '''
        capabilties = "Feature Name : Capa1\r\n State : Enabled\r\n" \
                      "Feature Name : Capa2\r\n State : Disabled\r\n"

        mock = MagicMock(return_value=capabilties)
        with patch.dict(dism.__salt__, {'cmd.run': mock}):
            out = dism.installed_features()
            mock.assert_called_once_with('DISM /Online /Get-Features')
            self.assertEqual(out, ["Capa1"])

if __name__ == '__main__':
    from integration import run_tests
    run_tests(DISMTestCase, needs_daemon=False)

# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.win_psget as win_psget

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

BOOTSTRAP_PS_STR = """<?xml version="1.0" encoding="utf-8"?>
<Objects>
  <Object Type="System.Management.Automation.PSCustomObject">
    <Property Name="Name" Type="System.String">NuGet</Property>
    <Property Name="Version" Type="Microsoft.PackageManagement.Internal.Utility.Versions.FourPartVersion">
      <Property Name="Major" Type="System.UInt16">2</Property>
      <Property Name="Minor" Type="System.UInt16">8</Property>
      <Property Name="Build" Type="System.UInt16">5</Property>
      <Property Name="Revision" Type="System.UInt16">208</Property>
    </Property>
    <Property Name="ProviderPath" Type="System.String">C:\\Program Files\\PackageManagement\\ProviderAssemblies\\nuget\\2.8.5
.208\\Microsoft.PackageManagement.NuGetProvider.dll</Property>
  </Object>
</Objects>"""

AVAIL_MODULES_PS_STR = """<?xml version="1.0" encoding="utf-8"?>
<Objects>
  <Object Type="System.Management.Automation.PSCustomObject">
    <Property Name="Name" Type="System.String">ActOnCmdlets</Property>
    <Property Name="Description" Type="System.String">CData Cmdlets for Act-On</Property>
  </Object>
  <Object Type="System.Management.Automation.PSCustomObject">
    <Property Name="Name" Type="System.String">FinancialEdgeNXTCmdlets</Property>
    <Property Name="Description" Type="System.String">CData Cmdlets for Blackbaud Financial Edge NXT</Property>
  </Object>
  <Object Type="System.Management.Automation.PSCustomObject">
    <Property Name="Name" Type="System.String">GoogleCMCmdlets</Property>
    <Property Name="Description" Type="System.String">CData Cmdlets for Google Campaign Manager</Property>
  </Object>
  <Object Type="System.Management.Automation.PSCustomObject">
    <Property Name="Name" Type="System.String">DHCPMigration</Property>
    <Property Name="Description" Type="System.String">A module to copy various DHCP information from 1 server to another.</Property>
  </Object>
</Objects>"""


class WinPsgetCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_psget
    """

    def setup_loader_modules(self):
        return {win_psget: {}}

    def test_bootstrap(self):
        mock_read_ok = MagicMock(
            return_value={
                "pid": 78,
                "retcode": 0,
                "stderr": "",
                "stdout": BOOTSTRAP_PS_STR,
            }
        )

        with patch.dict(win_psget.__salt__, {"cmd.run_all": mock_read_ok}):
            self.assertTrue("NuGet" in win_psget.bootstrap())

    def test_avail_modules(self):
        mock_read_ok = MagicMock(
            return_value={
                "pid": 78,
                "retcode": 0,
                "stderr": "",
                "stdout": AVAIL_MODULES_PS_STR,
            }
        )

        with patch.dict(win_psget.__salt__, {"cmd.run_all": mock_read_ok}):
            self.assertTrue("DHCPMigration" in win_psget.avail_modules(False))
            self.assertTrue("DHCPMigration" in win_psget.avail_modules(True))

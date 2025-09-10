"""
    Test cases for salt.modules.win_psget
"""

import pytest

import salt.modules.win_psget as win_psget
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_psget: {}}


@pytest.fixture
def bootstrap_ps_str():
    return """<?xml version="1.0" encoding="utf-8"?>
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


@pytest.fixture
def avail_modules_ps_str():
    return """<?xml version="1.0" encoding="utf-8"?>
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


def test_bootstrap(bootstrap_ps_str):
    mock_read_ok = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": bootstrap_ps_str,
        }
    )

    with patch.dict(win_psget.__salt__, {"cmd.run_all": mock_read_ok}):
        assert "NuGet" in win_psget.bootstrap()


def test_avail_modules(avail_modules_ps_str):
    mock_read_ok = MagicMock(
        return_value={
            "pid": 78,
            "retcode": 0,
            "stderr": "",
            "stdout": avail_modules_ps_str,
        }
    )

    with patch.dict(win_psget.__salt__, {"cmd.run_all": mock_read_ok}):
        assert "DHCPMigration" in win_psget.avail_modules(False)
        assert "DHCPMigration" in win_psget.avail_modules(True)

# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

import pytest

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_lgpo_netsh as win_lgpo_netsh
from salt.exceptions import CommandExecutionError


@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinLgpoNetshTestCase(TestCase):
    def test_get_settings_firewallpolicy_local(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='firewallpolicy',
                                          store='local')
        assert 'Inbound' in ret
        assert 'Outbound' in ret

    def test_get_settings_firewallpolicy_lgpo(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='firewallpolicy',
                                          store='lgpo')
        assert 'Inbound' in ret
        assert 'Outbound' in ret

    def test_get_settings_logging_local(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='logging',
                                          store='local')
        assert 'FileName' in ret
        assert 'LogAllowedConnections' in ret
        assert 'LogDroppedConnections' in ret
        assert 'MaxFileSize' in ret

    def test_get_settings_logging_lgpo(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='logging',
                                          store='lgpo')
        assert 'FileName' in ret
        assert 'LogAllowedConnections' in ret
        assert 'LogDroppedConnections' in ret
        assert 'MaxFileSize' in ret

    def test_get_settings_settings_local(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='settings',
                                          store='local')
        assert 'InboundUserNotification' in ret
        assert 'LocalConSecRules' in ret
        assert 'LocalFirewallRules' in ret
        assert 'RemoteManagement' in ret
        assert 'UnicastResponseToMulticast' in ret

    def test_get_settings_settings_lgpo(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='settings',
                                          store='lgpo')
        assert 'InboundUserNotification' in ret
        assert 'LocalConSecRules' in ret
        assert 'LocalFirewallRules' in ret
        assert 'RemoteManagement' in ret
        assert 'UnicastResponseToMulticast' in ret

    def test_get_settings_state_local(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='state',
                                          store='local')
        assert 'State' in ret

    def test_get_settings_state_lgpo(self):
        ret = win_lgpo_netsh.get_settings(profile='domain',
                                          section='state',
                                          store='lgpo')
        assert 'State' in ret

    def test_get_all_settings_local(self):
        ret = win_lgpo_netsh.get_all_settings(profile='domain',
                                              store='local')

        assert 'Inbound' in ret
        assert 'Outbound' in ret
        assert 'FileName' in ret
        assert 'LogAllowedConnections' in ret
        assert 'LogDroppedConnections' in ret
        assert 'MaxFileSize' in ret
        assert 'InboundUserNotification' in ret
        assert 'LocalConSecRules' in ret
        assert 'LocalFirewallRules' in ret
        assert 'RemoteManagement' in ret
        assert 'UnicastResponseToMulticast' in ret
        assert 'State' in ret

    def test_get_all_settings_lgpo(self):
        ret = win_lgpo_netsh.get_all_settings(profile='domain',
                                              store='local')

        assert 'Inbound' in ret
        assert 'Outbound' in ret
        assert 'FileName' in ret
        assert 'LogAllowedConnections' in ret
        assert 'LogDroppedConnections' in ret
        assert 'MaxFileSize' in ret
        assert 'InboundUserNotification' in ret
        assert 'LocalConSecRules' in ret
        assert 'LocalFirewallRules' in ret
        assert 'RemoteManagement' in ret
        assert 'UnicastResponseToMulticast' in ret
        assert 'State' in ret

    def test_get_all_profiles_local(self):
        ret = win_lgpo_netsh.get_all_profiles(store='local')
        assert 'Domain Profile' in ret
        assert 'Private Profile' in ret
        assert 'Public Profile' in ret

    def test_get_all_profiles_lgpo(self):
        ret = win_lgpo_netsh.get_all_profiles(store='lgpo')
        assert 'Domain Profile' in ret
        assert 'Private Profile' in ret
        assert 'Public Profile' in ret

    @pytest.mark.destructive_test
    def test_set_firewall_settings_inbound_local(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='firewallpolicy',
                                              store='local')['Inbound']
        try:
            ret = win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                       inbound='allowinbound',
                                                       store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                                  section='firewallpolicy',
                                                  store='local')['Inbound']
            assert 'AllowInbound' == new
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                       inbound=current,
                                                       store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_settings_inbound_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='firewallpolicy',
                                              store='local')['Inbound']
        try:
            with pytest.raises(CommandExecutionError):
                win_lgpo_netsh.set_firewall_settings(profile='domain',
                inbound='notconfigured',
                store='local')
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                       inbound=current,
                                                       store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_settings_inbound_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='firewallpolicy',
                                              store='lgpo')['Inbound']
        try:
            ret = win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                       inbound='notconfigured',
                                                       store='lgpo')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='firewallpolicy',
                                              store='lgpo')['Inbound']
            assert 'NotConfigured' == new
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                       inbound=current,
                                                       store='lgpo')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_settings_outbound_local(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='firewallpolicy',
                                              store='local')['Outbound']
        try:
            ret = win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                       outbound='allowoutbound',
                                                       store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='firewallpolicy',
                                              store='local')['Outbound']
            assert 'AllowOutbound' == new
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(profile='domain',
                                                       outbound=current,
                                                       store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_logging_allowed_local_enable(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['LogAllowedConnections']
        try:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='allowedconnections',
                                                      value='enable',
                                                      store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['LogAllowedConnections']
            assert 'Enable' == new
        finally:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='allowedconnections',
                                                      value=current,
                                                      store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_logging_allowed_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['LogAllowedConnections']
        try:
            with pytest.raises(CommandExecutionError):
                win_lgpo_netsh.set_logging_settings(profile='domain',
                setting='allowedconnections',
                value='notconfigured',
                store='local')
        finally:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='allowedconnections',
                                                      value=current,
                                                      store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_logging_allowed_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='lgpo')['LogAllowedConnections']
        try:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='allowedconnections',
                                                      value='notconfigured',
                                                      store='lgpo')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='lgpo')['LogAllowedConnections']
            assert 'NotConfigured' == new
        finally:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='allowedconnections',
                                                      value=current,
                                                      store='lgpo')
            assert ret

    def test_set_firewall_logging_dropped_local_enable(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['LogDroppedConnections']
        try:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='droppedconnections',
                                                      value='enable',
                                                      store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['LogDroppedConnections']
            assert 'Enable' == new
        finally:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='droppedconnections',
                                                      value=current,
                                                      store='local')
            assert ret

    def test_set_firewall_logging_filename_local(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['FileName']
        try:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='filename',
                                                      value='C:\\Temp\\test.log',
                                                      store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['FileName']
            assert 'C:\\Temp\\test.log' == new
        finally:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='filename',
                                                      value=current,
                                                      store='local')
            assert ret

    def test_set_firewall_logging_maxfilesize_local(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['MaxFileSize']
        try:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='maxfilesize',
                                                      value='16384',
                                                      store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='logging',
                                              store='local')['MaxFileSize']
            assert '16384' == new
        finally:
            ret = win_lgpo_netsh.set_logging_settings(profile='domain',
                                                      setting='maxfilesize',
                                                      value=current,
                                                      store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_settings_fwrules_local_enable(self):
        with pytest.raises(CommandExecutionError):
            win_lgpo_netsh.set_settings(profile='domain',
            setting='localfirewallrules',
            value='enable',
            store='local')

    @pytest.mark.destructive_test
    def test_set_firewall_settings_fwrules_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='lgpo')['LocalFirewallRules']
        try:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='localfirewallrules',
                                              value='notconfigured',
                                              store='lgpo')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='lgpo')['LocalFirewallRules']
            assert 'NotConfigured' == new
        finally:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='localfirewallrules',
                                              value=current,
                                              store='lgpo')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_settings_consecrules_local_enable(self):
        with pytest.raises(CommandExecutionError):
            win_lgpo_netsh.set_settings(profile='domain',
            setting='localconsecrules',
            value='enable',
            store='local')

    def test_set_firewall_settings_notification_local_enable(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='local')['InboundUserNotification']
        try:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='inboundusernotification',
                                              value='enable',
                                              store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='local')['InboundUserNotification']
            assert 'Enable' == new
        finally:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='inboundusernotification',
                                              value=current,
                                              store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_settings_notification_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='local')['InboundUserNotification']
        try:
            with pytest.raises(CommandExecutionError):
                win_lgpo_netsh.set_settings(profile='domain',
                setting='inboundusernotification',
                value='notconfigured',
                store='local')
        finally:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='inboundusernotification',
                                              value=current,
                                              store='local')
            assert ret

    def test_set_firewall_settings_notification_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='lgpo')['InboundUserNotification']
        try:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='inboundusernotification',
                                              value='notconfigured',
                                              store='lgpo')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='lgpo')['InboundUserNotification']
            assert 'NotConfigured' == new
        finally:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='inboundusernotification',
                                              value=current,
                                              store='lgpo')
            assert ret

    def test_set_firewall_settings_remotemgmt_local_enable(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='local')['RemoteManagement']
        try:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='remotemanagement',
                                              value='enable',
                                              store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='local')['RemoteManagement']
            assert 'Enable' == new
        finally:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='remotemanagement',
                                              value=current,
                                              store='local')
            assert ret

    def test_set_firewall_settings_unicast_local_disable(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='local')['UnicastResponseToMulticast']
        try:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='unicastresponsetomulticast',
                                              value='disable',
                                              store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='settings',
                                              store='local')['UnicastResponseToMulticast']
            assert 'Disable' == new
        finally:
            ret = win_lgpo_netsh.set_settings(profile='domain',
                                              setting='unicastresponsetomulticast',
                                              value=current,
                                              store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_state_local_on(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='state',
                                              store='local')['State']
        try:
            ret = win_lgpo_netsh.set_state(profile='domain',
                                           state='off',
                                           store='local')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='state',
                                              store='local')['State']
            assert 'OFF' == new
        finally:
            ret = win_lgpo_netsh.set_state(profile='domain',
                                           state=current,
                                           store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_state_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='state',
                                              store='local')['State']
        try:
            with pytest.raises(CommandExecutionError):
                win_lgpo_netsh.set_state(profile='domain',
                state='notconfigured',
                store='local')
        finally:
            ret = win_lgpo_netsh.set_state(profile='domain',
                                           state=current,
                                           store='local')
            assert ret

    @pytest.mark.destructive_test
    def test_set_firewall_state_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(profile='domain',
                                              section='state',
                                              store='local')['State']
        try:
            ret = win_lgpo_netsh.set_state(profile='domain',
                                           state='notconfigured',
                                           store='lgpo')
            assert ret
            new = win_lgpo_netsh.get_settings(profile='domain',
                                              section='state',
                                              store='lgpo')['State']
            assert 'NotConfigured' == new
        finally:
            ret = win_lgpo_netsh.set_state(profile='domain',
                                           state=current,
                                           store='lgpo')
            assert ret

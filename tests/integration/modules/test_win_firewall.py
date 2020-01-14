# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

import pytest

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt Libs
import salt.utils.platform


@skipIf(not salt.utils.platform.is_windows(), 'Tests for only Windows')
@pytest.mark.windows_whitelisted
class FirewallTest(ModuleCase):
    '''
    Validate windows firewall module
    '''
    def _pre_firewall_status(self, pre_run):
        post_run = self.run_function('firewall.get_config')
        network = ['Domain', 'Public', 'Private']
        # compare the status of the firewall before and after test
        # and re-enable or disable depending on status before test run
        for net in network:
            if post_run[net] != pre_run[net]:
                if pre_run[net]:
                    assert self.run_function('firewall.enable', profile=net)
                else:
                    assert self.run_function('firewall.disable', profile=net)

    @pytest.mark.destructive_test
    def test_firewall_get_config(self):
        '''
        test firewall.get_config
        '''
        pre_run = self.run_function('firewall.get_config')
        # ensure all networks are enabled then test status
        assert self.run_function('firewall.enable', profile='allprofiles')
        ret = self.run_function('firewall.get_config')
        network = ['Domain', 'Public', 'Private']
        for net in network:
            assert ret[net]
        self._pre_firewall_status(pre_run)

    @pytest.mark.destructive_test
    def test_firewall_disable(self):
        '''
        test firewall.disable
        '''
        pre_run = self.run_function('firewall.get_config')
        network = 'Private'

        ret = self.run_function('firewall.get_config')[network]
        if not ret:
            assert self.run_function('firewall.enable', profile=network)

        assert self.run_function('firewall.disable', profile=network)
        ret = self.run_function('firewall.get_config')[network]
        assert not ret
        self._pre_firewall_status(pre_run)

    @pytest.mark.destructive_test
    def test_firewall_enable(self):
        '''
        test firewall.enable
        '''
        pre_run = self.run_function('firewall.get_config')
        network = 'Private'

        ret = self.run_function('firewall.get_config')[network]
        if ret:
            assert self.run_function('firewall.disable', profile=network)

        assert self.run_function('firewall.enable', profile=network)
        ret = self.run_function('firewall.get_config')[network]
        assert ret
        self._pre_firewall_status(pre_run)

    def test_firewall_get_rule(self):
        '''
        test firewall.get_rule
        '''
        rule = 'Remote Event Log Management (NP-In)'

        ret = self.run_function('firewall.get_rule', [rule])
        checks = ['Private', 'LocalPort', 'RemotePort']
        for check in checks:
            assert check in ret[rule]

    @pytest.mark.destructive_test
    def test_firewall_add_delete_rule(self):
        '''
        test firewall.add_rule and delete_rule
        '''
        rule = 'test rule'
        port = '8080'

        # test adding firewall rule
        add_rule = self.run_function('firewall.add_rule', [rule, port])
        ret = self.run_function('firewall.get_rule', [rule])
        assert rule in ret[rule]
        assert port in ret[rule]

        # test deleting firewall rule
        assert self.run_function('firewall.delete_rule', [rule, port])
        ret = self.run_function('firewall.get_rule', [rule])
        assert rule not in ret
        assert port not in ret
        assert 'No rules match the specified criteria.' in ret

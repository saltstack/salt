# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import MultimasterModuleCase, MultiMasterTestShellCase
from tests.support.helpers import skip_if_not_root, destructiveTest
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.unit import skipIf

import salt.modules.iptables
HAS_IPTABLES = salt.modules.iptables.__virtual__()
if isinstance(HAS_IPTABLES, tuple):
    HAS_IPTABLES = HAS_IPTABLES[0]


@destructiveTest
@skip_if_not_root
@skipIf(not HAS_IPTABLES, 'iptables command is not available')
class TestHandleEvents(MultimasterModuleCase, MultiMasterTestShellCase, AdaptedConfigurationTestCaseMixin):
    '''
    Validate the events handling in multimaster environment
    '''
    def test_minion_hangs_on_master_failure_50814(self):
        '''
        Check minion handling events for the alive master when another master is dead.
        The case being checked here is described in details in issue #50814.
        '''
        disconnect_master_rule = '-i lo -p tcp --dport {0} -j DROP'.format(
                self.mm_master_opts['ret_port'])
        # Disconnect the master.
        res = self.run_function(
                'iptables.append',
                ('filter', 'INPUT', disconnect_master_rule),
                master_tgt=1,
                )
        # Workaround slow beacons.list_available response
        if not res:
            res = self.run_function(
                    'iptables.append',
                    ('filter', 'INPUT', disconnect_master_rule),
                    master_tgt=1,
                    )
        self.assertTrue(res)
        try:
            # Send an event. This would return okay.
            res = self.run_function(
                    'event.send',
                    ('myco/foo/bar',),
                    master_tgt=1,
                    )
            self.assertTrue(res)
            # Send one more event. Minion was hanging on this. This is fixed by #53417
            res = self.run_function(
                    'event.send',
                    ('myco/foo/bar',),
                    master_tgt=1,
                    timeout=60,
                    )
            self.assertTrue(res, 'Minion is not responding to the second master after the first '
                                 'one has gone. Check #50814 for details.')
        finally:
            # Remove the firewall rule taking master online back.
            # Since minion could be not responsive now use `salt-call --local` for this.
            res = self.run_call(
                    "iptables.delete filter INPUT rule='{0}'".format(disconnect_master_rule),
                    local=True,
                    timeout=30)
            self.assertEqual(res, ['local:'])
            # Ensure the master is back.
            res = self.run_function(
                    'event.send',
                    ('myco/foo/bar',),
                    master_tgt=0,
                    )
            self.assertTrue(res)

# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import time

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
                master_tgt='mm-sub-master',
                )
        # Workaround slow beacons.list_available response
        if not res:
            res = self.run_function(
                    'iptables.append',
                    ('filter', 'INPUT', disconnect_master_rule),
                    master_tgt='mm-sub-master',
                    )
        self.assertTrue(res)
        try:
            # Send an event. This would return okay.
            res = self.run_function(
                    'event.send',
                    ('myco/foo/bar',),
                    master_tgt='mm-sub-master',
                    )
            self.assertTrue(res)
            # Send one more event. Minion was hanging on this. This is fixed by #53417
            res = self.run_function(
                    'event.send',
                    ('myco/foo/bar',),
                    master_tgt='mm-sub-master',
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
                    master_tgt='mm-master',
                    )
            self.assertTrue(res)

    def test_master_return_strategy(self):
        '''
        Test minion config master_return_strategy.
        '''
        # GIVEN two masters, mm-master and mm-sub-master,
        # and two minions, mm-minion and mm-sub-minion
        # mm-minion: master_return_strategy = 'source'
        # mm-sub-minion: master_return_strategy = 'any'

        # WHEN a job is sent from one master to both minions and then the connection to that master
        # is severed before the job returns
        # sync_all is run from mm-master on start so we stop mm-sub-master
        disconnect_master_rule = '-i lo -p tcp --dport {0} -j DROP'.format(
                self.mm_sub_master_opts['ret_port'])
        return_source_jid = self.run_function(
            'test.sleep',
            ['2'],
            minion_tgt='mm-minion',
            master_tgt='mm-sub-master',
            asynchronous=True,
        )
        return_any_jid = self.run_function(
            'test.sleep',
            ['2'],
            minion_tgt='mm-sub-minion',
            master_tgt='mm-sub-master',
            asynchronous=True,
        )
        # Give the job time to start then disconnect the master
        time.sleep(.5)
        res = self.run_function(
            'iptables.append',
            ('filter', 'INPUT', disconnect_master_rule),
            master_tgt='mm-master',
        )
        # Workaround slow beacons.list_available response
        if not res:
            res = self.run_function(
                'iptables.append',
                ('filter', 'INPUT', disconnect_master_rule),
                master_tgt='mm-master',
            )
        self.assertTrue(res)

        # THEN the result from mm-sub-minion with master_return_strategy of any will arrive on
        # mm-master whereas the result from mm-minion with master_return_strategy of source will
        # not
        tag = 'salt/job/{0}/ret/mm-sub-minion'.format(return_any_jid)
        try:
            ret_event = self.wait_for_event(
                self.mm_master_opts,
                wait=10,
                tag=tag
            )
            self.assertIsNotNone(ret_event)

            return_source_res = self.run_run(
                'jobs.lookup_jid {0} --out txt'.format(return_source_jid),
                config_dir=self.mm_master_opts['config_dir']
            )
            return_any_res = self.run_run(
                'jobs.lookup_jid {0} --out txt'.format(return_any_jid),
                config_dir=self.mm_master_opts['config_dir']
            )
            self.assertEqual([], return_source_res)
            self.assertIn('True', return_any_res[0])
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
                    master_tgt='mm-sub-master',
                    )
            self.assertTrue(res)

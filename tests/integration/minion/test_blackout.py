# -*- coding: utf-8 -*-
'''
Tests for minion blackout
'''

# Import Python libs
from __future__ import absolute_import
import os
import time
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import flaky
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.files


class MinionBlackoutTestCase(ModuleCase):
    '''
    Test minion blackout functionality
    '''

    @classmethod
    def setUpClass(cls):
        cls.blackout_pillar = os.path.join(RUNTIME_VARS.PILLAR_DIR, 'base', 'blackout.sls')

    def tearDown(self):
        self.end_blackout(sleep=False)
        # Make sure we also refresh the sub_minion pillar
        refreshed = self.run_function(
            'saltutil.refresh_pillar',
            minion_tgt='sub_minion',
            async=False)  # pylint: disable=pep8-reserved-keywords
        self.assertTrue(refreshed)

    def begin_blackout(self, blackout_data='minion_blackout: True'):
        '''
        setup minion blackout mode
        '''
        with salt.utils.files.fopen(self.blackout_pillar, 'w') as wfh:
            wfh.write(blackout_data)
        refreshed = self.run_function(
            'saltutil.refresh_pillar',
            async=False)  # pylint: disable=pep8-reserved-keywords
        self.assertTrue(refreshed)

    def end_blackout(self, sleep=True):
        '''
        takedown minion blackout mode
        '''
        with salt.utils.files.fopen(self.blackout_pillar, 'w') as wfh:
            wfh.write('minion_blackout: False\n')
        self.run_function('saltutil.refresh_pillar')
        if sleep:
            time.sleep(10)  # wait for minion to exit blackout mode

    @flaky
    def test_blackout(self):
        '''
        Test that basic minion blackout functionality works
        '''
        try:
            self.begin_blackout()
            blackout_ret = self.run_function('test.ping')
            self.assertIn('Minion in blackout mode.', blackout_ret)
        finally:
            self.end_blackout()

        ret = self.run_function('test.ping')
        self.assertEqual(ret, True)

    @flaky
    def test_blackout_whitelist(self):
        '''
        Test that minion blackout whitelist works
        '''
        self.begin_blackout(textwrap.dedent('''\
            minion_blackout: True
            minion_blackout_whitelist:
              - test.ping
              - test.fib
            '''))

        ping_ret = self.run_function('test.ping')
        self.assertEqual(ping_ret, True)

        fib_ret = self.run_function('test.fib', [7])
        self.assertTrue(isinstance(fib_ret, list))
        self.assertEqual(fib_ret[0], 13)

    @flaky
    def test_blackout_nonwhitelist(self):
        '''
        Test that minion refuses to run non-whitelisted functions during
        blackout whitelist
        '''
        self.begin_blackout(textwrap.dedent('''\
            minion_blackout: True
            minion_blackout_whitelist:
              - test.ping
              - test.fib
            '''))

        state_ret = self.run_function('state.apply')
        self.assertIn('Minion in blackout mode.', state_ret)

        cloud_ret = self.run_function('cloud.query', ['list_nodes_full'])
        self.assertIn('Minion in blackout mode.', cloud_ret)

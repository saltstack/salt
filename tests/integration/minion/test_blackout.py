# -*- coding: utf-8 -*-
'''
Tests for minion blackout
'''

# Import Python libs
from __future__ import absolute_import
import os
from time import sleep
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.paths import PILLAR_DIR
from tests.support.helpers import destructiveTest, flaky

# Import Salt libs
import salt.utils.files


BLACKOUT_PILLAR = os.path.join(PILLAR_DIR, 'base', 'blackout.sls')


@destructiveTest
class MinionBlackoutTestCase(ModuleCase):
    '''
    Test minion blackout functionality
    '''
    def begin_blackout(self, blackout_data='minion_blackout: True'):
        '''
        setup minion blackout mode
        '''
        with salt.utils.files.fopen(BLACKOUT_PILLAR, 'w') as wfh:
            wfh.write(blackout_data)
        self.run_function('saltutil.refresh_pillar')
        sleep(10)  # wait for minion to enter blackout mode

    def end_blackout(self):
        '''
        takedown minion blackout mode
        '''
        with salt.utils.files.fopen(BLACKOUT_PILLAR, 'w') as blackout_pillar:
            blackout_pillar.write(textwrap.dedent('''\
                minion_blackout: False
                '''))
        self.run_function('saltutil.refresh_pillar')
        sleep(10)  # wait for minion to exit blackout mode

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
        try:
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
        finally:
            self.end_blackout()

    @flaky
    def test_blackout_nonwhitelist(self):
        '''
        Test that minion refuses to run non-whitelisted functions during
        blackout whitelist
        '''
        try:
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
        finally:
            self.end_blackout()

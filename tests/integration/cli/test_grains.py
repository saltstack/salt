# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Daniel Mizyrycki (mzdaniel@glidelink.net)`


    tests.integration.cli.test_grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Grains targeting tests

'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Libs
import integration
import salt.utils


class GrainsTargetingTest(integration.ShellCase):
    '''
    Integration tests for targeting with grains.
    '''

    def test_grains_targeting_os_running(self):
        '''
        Tests running "salt -G 'os:<system-os>' test.ping and minions both return True
        '''
        test_ret = ['sub_minion:', '    True', 'minion:', '    True']

        os_grain = ''
        for item in self.run_salt('minion grains.get os'):
            if item != 'minion:':
                os_grain = item.strip()

        ret = self.run_salt('-G \'os:{0}\' test.ping'.format(os_grain))
        self.assertEqual(sorted(ret), sorted(test_ret))

    def test_grains_targeting_minion_id_running(self):
        '''
        Tests return of each running test minion targeting with minion id grain
        '''
        minion = self.run_salt('-G \'id:minion\' test.ping')
        self.assertEqual(sorted(minion), sorted(['minion:', '    True']))

        sub_minion = self.run_salt('-G \'id:sub_minion\' test.ping')
        self.assertEqual(sorted(sub_minion), sorted(['sub_minion:', '    True']))

    def test_grains_targeting_disconnected(self):
        '''
        Tests return of minion using grains targeting on a disconnected minion.
        '''
        test_ret = 'Minion did not return. [Not connected]'

        # Create a minion key, but do not start the "fake" minion. This mimics a
        # disconnected minion.
        key_file = os.path.join(self.master_opts['pki_dir'], 'minions', 'disconnected')
        salt.utils.fopen(key_file, 'a').close()

        # ping disconnected minion and ensure it times out and returns with correct message
        try:
            ret = ''
            for item in self.run_salt('-G \'id:disconnected\' test.ping'):
                if item != 'disconnected:':
                    ret = item.strip()
            self.assertEqual(ret, test_ret)
        finally:
            os.unlink(key_file)

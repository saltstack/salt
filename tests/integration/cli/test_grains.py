# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Daniel Mizyrycki (mzdaniel@glidelink.net)`


    tests.integration.cli.grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt-ssh grains id work for localhost. (gh #16129)

    $ salt-ssh localhost grains.get id
    localhost:
        localhost
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Libs
import salt.utils

# Import Salt Testing Libs
from tests.support.case import ShellCase, SSHCase


class GrainsTargetingTest(ShellCase):
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
        test_ret = 'Minion did not return. [No response]'

        # Create a minion key, but do not start the "fake" minion. This mimics a
        # disconnected minion.
        key_file = os.path.join(self.master_opts['pki_dir'], 'minions', 'disconnected')
        with salt.utils.fopen(key_file, 'a'):
            pass

        # ping disconnected minion and ensure it times out and returns with correct message
        try:
            ret = ''
            for item in self.run_salt('-t 1 -G \'id:disconnected\' test.ping', timeout=40):
                if item != 'disconnected:':
                    ret = item.strip()
            self.assertEqual(ret, test_ret)
        finally:
            os.unlink(key_file)


class SSHGrainsTest(SSHCase):
    '''
    Test salt-ssh grains functionality
    Depend on proper environment set by SSHCase class
    '''

    def test_grains_id(self):
        '''
        Test salt-ssh grains id work for localhost.
        '''
        cmd = self.run_function('grains.get', ['id'])
        self.assertEqual(cmd, 'localhost')

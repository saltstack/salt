# -*- coding: utf-8 -*-
'''
Tests for existence of manpages
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import pprint
import shutil

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@skipIf(salt.utils.platform.is_windows(), 'minion is windows')
class ManTest(ModuleCase):

    @classmethod
    def setUpClass(cls):
        cls.rootdir = os.path.join(RUNTIME_VARS.TMP, 'mantest')
        # Map filenames to search strings which should be in the manpage
        cls.manpages = {
            'salt-cp.1': [
                'salt-cp Documentation',
                'copies files from the master',
            ],
            'salt-cloud.1': [
                'Salt Cloud Command',
                'Provision virtual machines in the cloud',
            ],
            'salt-call.1': [
                'salt-call Documentation',
                'run module functions locally',
            ],
            'salt-api.1': [
                'salt-api Command',
                'Start interfaces used to remotely connect',
            ],
            'salt-unity.1': [
                'salt-unity Command',
                'unified invocation wrapper',
            ],
            'salt-syndic.1': [
                'salt-syndic Documentation',
                'Salt syndic daemon',
            ],
            'salt-ssh.1': [
                'salt-ssh Documentation',
                'executed using only SSH',
            ],
            'salt-run.1': [
                'salt-run Documentation',
                'frontend command for executing',
            ],
            'salt-proxy.1': [
                'salt-proxy Documentation',
                'proxies these commands',
            ],
            'salt-minion.1': [
                'salt-minion Documentation',
                'Salt minion daemon',
            ],
            'salt-master.1': [
                'salt-master Documentation',
                'Salt master daemon',
            ],
            'salt-key.1': [
                'salt-key Documentation',
                'management of Salt server public keys',
            ],
            'salt.1': [
                'allows for commands to be executed',
            ],
            'salt.7': [
                'Salt Documentation',
            ],
            'spm.1': [
                'Salt Package Manager Command',
                'command for managing Salt packages',
            ],
        }

    @classmethod
    def tearDownClass(cls):
        cls.manpages = None

    def setUp(self):
        self.addCleanup(shutil.rmtree, self.rootdir, ignore_errors=True)
        if not os.path.exists(self.rootdir):
            ret = self.run_function('mantest.install', [self.rootdir])
            if not isinstance(ret, dict):
                self.fail(
                    'The \'mantest.install\' command did not return the excepted dictionary. Output:\n{}'.format(
                        ret
                    )
                )
            if ret['retcode'] != 0:
                self.fail(
                    'Failed to install. Full return dictionary:\n{}'.format(
                        pprint.pformat(ret)
                    )
                )

    def test_man(self):
        '''
        Make sure that man pages are installed
        '''
        ret = self.run_function('mantest.search', [self.manpages, self.rootdir])
        # The above function returns True if successful and an exception (which
        # will manifest in the return as a stringified exception) if
        # unsuccessful. Therefore, a simple assertTrue is not sufficient.
        if ret is not True:
            self.fail(ret)

# -*- coding: utf-8 -*-
"""
    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details
"""

# Import python libs
import os
import shutil
import integration

# Import salt libs
from saltunittest import skipIf, destructiveTest


class VirtualenvTest(integration.ModuleCase):

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_issue_1959_virtualenv_runas(self):
        user = 'issue-1959'
        if not self.run_function('user.add', [user]):
            self.skipTest('Failed to create the \'{0}\' user'.format(user))

        uinfo = self.run_function('user.info', [user])

        venv_dir = '/tmp/issue-1959-virtualenv-runas'
        try:
            ret = self.run_function(
                'state.sls', mods='issue-1959-virtualenv-runas'
            )
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})
            for part in ret.itervalues():
                self.assertTrue(part['result'])

            # Lets check proper ownership
            statinfo = self.run_function('file.stats', [venv_dir])
            self.assertEqual(statinfo['user'], uinfo['name'])
            self.assertEqual(statinfo['uid'], uinfo['uid'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        self.run_function('user.delete', [user, True, True])

# -*- coding: utf-8 -*-
"""
    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details
"""

# Import python libs
import os
import shutil

# Import salt libs
import integration
from saltunittest import skipIf, destructiveTest


class VirtualenvTest(integration.ModuleCase,
                     integration.SaltReturnAssertsMixIn):

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_issue_1959_virtualenv_runas(self):
        user = 'issue-1959'
        if not self.run_function('user.add', [user]):
            # Left behind on a canceled test run?
            self.run_function('user.delete', [user, True, True])
            if not self.run_function('user.add', [user]):
                self.skipTest('Failed to create the \'{0}\' user'.format(user))

        uinfo = self.run_function('user.info', [user])

        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'issue-1959-virtualenv-runas'
        )
        try:
            ret = self.run_function(
                'state.sls', mods='issue-1959-virtualenv-runas'
            )
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})
            for part in ret.itervalues():
                self.assertSaltTrueReturn(part)

            # Lets check proper ownership
            statinfo = self.run_function('file.stats', [venv_dir])
            self.assertEqual(statinfo['user'], uinfo['name'])
            self.assertEqual(statinfo['uid'], uinfo['uid'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        self.run_function('user.delete', [user, True, True])

# -*- coding: utf-8 -*-
'''
    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details
'''

import os
import shutil
import tempfile

# Import salt libs
from saltunittest import skipIf
import integration


class PipStateTest(integration.ModuleCase):

    def setUp(self):
        super(PipStateTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['virtualenv'])
        if not ret:
            self.skipTest('virtualenv not installed')

    def test_pip_installed_errors(self):
        venv_dir = '/tmp/pip-installed-errors'
        try:
            # Since we don't have the virtualenv created, pip.installed will
            # thrown and error.
            ret = self.run_function('state.sls', mods='pip-installed-errors')
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})

            for key in ret.keys():
                self.assertFalse(ret[key]['result'])
                self.assertEqual(
                    ret[key]['comment'],
                    'Failed to install package supervisor. Error: /bin/bash: '
                    '/tmp/pip-installed-errors: No such file or directory'
                )

            # We now create the missing virtualenv
            ret = self.run_function('virtualenv.create', [venv_dir])
            self.assertTrue(ret['retcode']==0)

            # The state should not have any issues running now
            ret = self.run_function('state.sls', mods='pip-installed-errors')
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})

            for key in ret.keys():
                self.assertTrue(ret[key]['result'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

    def test_issue_2028_pip_installed_state(self):
        ret = self.run_function('state.sls', mods='issue-2028-pip-installed')

        venv_dir = '/tmp/issue-2028-pip-installed'

        try:
            self.assertTrue(isinstance(ret, dict)), ret
            self.assertNotEqual(ret, {})

            for key in ret.iterkeys():
                self.assertTrue(ret[key]['result'])

            self.assertTrue(
                os.path.isfile(os.path.join(venv_dir, 'bin', 'supervisord'))
            )
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

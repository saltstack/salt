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
        self.venv_test_dir = tempfile.mkdtemp()
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')

    def test_issue_2028_pip_installed(self):
        print 123, self.run_function(
            'virtualenv.create', [self.venv_dir], system_site_packages=True
        )
        pip_bin = os.path.join(self.venv_dir, 'bin', 'pip')

        print 456, self.run_state(
            'pip.installed', name='supervisor', bin_env=pip_bin,
        )

        self.run_function('virtualenv.create', ['/tmp/issue-2028-virtualenv'])
        self.run_function('state.sls', mods='issue-2028-pip-installed')

    def tearDown(self):
        super(PipStateTest, self).tearDown()
        shutil.rmtree(self.venv_test_dir)
        shutil.rmtree('/tmp/issue-2028-virtualenv')

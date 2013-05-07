# -*- coding: utf-8 -*-
'''
    tests.integration.modules.pip
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import pwd
import shutil
import tempfile

# Import salt libs
import integration


class PipModuleTest(integration.ModuleCase):

    def setUp(self):
        super(PipModuleTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['virtualenv'])
        if not ret:
            self.skipTest('virtualenv not installed')

        self.venv_test_dir = tempfile.mkdtemp()
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')

    def test_issue_2087_missing_pip(self):
        # Let's create the testing virtualenv
        self.run_function('virtualenv.create', [self.venv_dir])

        # Let's remove the pip binary
        pip_bin = os.path.join(self.venv_dir, 'bin', 'pip')
        if not os.path.isfile(pip_bin):
            self.skipTest(
                'Failed to find the pip binary to the test virtualenv'
            )
        os.remove(pip_bin)

        # Let's run a pip depending functions
        for func in ('pip.freeze', 'pip.list'):
            ret = self.run_function(func, bin_env=self.venv_dir)
            self.assertEqual(
                ret,
                'Command required for \'{0}\' not found: Could not find '
                'a `pip` binary'.format(func)
            )

    def test_issue_4805_nested_requirements_runas_no_chown(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.
        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        with open(req1_filename, 'wb') as f:
            f.write('-r requirements2.txt')
        with open(req2_filename, 'wb') as f:
            f.write('pep8')

        this_user = pwd.getpwuid(os.getuid())[0]
        ret = self.run_function('pip.install', requirements=req1_filename,
                                runas=this_user, no_chown=True)
        self.assertEqual(ret['retcode'], 0)
        self.assertIn('installed pep8', ret['stdout'])

    def test_pip_uninstall(self):
        # Let's create the testing virtualenv
        self.run_function('virtualenv.create', [self.venv_dir])
        ret = self.run_function('pip.install', ['pep8'], bin_env=self.venv_dir)
        self.assertEqual(ret['retcode'], 0)
        self.assertIn('installed pep8', ret['stdout'])
        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )
        self.assertEqual(ret['retcode'], 0)
        self.assertIn('uninstalled pep8', ret['stdout'])

    def test_pip_install_upgrade(self):
        # Create the testing virtualenv
        self.run_function('virtualenv.create', [self.venv_dir])
        ret = self.run_function(
            'pip.install', ['pep8==1.3.4'], bin_env=self.venv_dir
        )
        self.assertEqual(ret['retcode'], 0)
        self.assertIn('installed pep8', ret['stdout'])
        ret = self.run_function(
            'pip.install',
            ['pep8'],
            bin_env=self.venv_dir,
            upgrade=True
        )
        self.assertEqual(ret['retcode'], 0)
        self.assertIn('installed pep8', ret['stdout'])
        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )
        self.assertEqual(ret['retcode'], 0)
        self.assertIn('uninstalled pep8', ret['stdout'])

    def tearDown(self):
        super(PipModuleTest, self).tearDown()
        if os.path.isdir(self.venv_test_dir):
            shutil.rmtree(self.venv_test_dir)

# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    tests.integration.modules.pip
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import pwd
import shutil
import tempfile

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES


@skipIf(salt.utils.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
class PipModuleTest(integration.ModuleCase):

    def setUp(self):
        super(PipModuleTest, self).setUp()

        self.venv_test_dir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')
        for key in os.environ.copy():
            if key.startswith('PIP_'):
                os.environ.pop(key)
        self.pip_temp = os.path.join(self.venv_test_dir, '.pip-temp')
        if not os.path.isdir(self.pip_temp):
            os.makedirs(self.pip_temp)
        os.environ['PIP_SOURCE_DIR'] = os.environ['PIP_BUILD_DIR'] = ''

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
            self.assertIn(
                'Command required for \'{0}\' not found: '
                'Could not find a `pip` binary in virtualenv'.format(func),
                ret
            )

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_issue_4805_nested_requirements_user_no_chown(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.
        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        with salt.utils.fopen(req1_filename, 'wb') as f:
            f.write('-r requirements2.txt')
        with salt.utils.fopen(req2_filename, 'wb') as f:
            f.write('pep8')

        this_user = pwd.getpwuid(os.getuid())[0]
        ret = self.run_function(
            'pip.install', requirements=req1_filename, user=this_user,
            no_chown=True, bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except (AssertionError, TypeError):
            import pprint
            pprint.pprint(ret)
            raise

    def test_pip_uninstall(self):
        # Let's create the testing virtualenv
        self.run_function('virtualenv.create', [self.venv_dir])
        ret = self.run_function('pip.install', ['pep8'], bin_env=self.venv_dir)
        self.assertEqual(ret['retcode'], 0)
        self.assertIn('installed pep8', ret['stdout'])
        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('uninstalled pep8', ret['stdout'])
        except AssertionError:
            import pprint
            pprint.pprint(ret)
            raise

    def test_pip_install_upgrade(self):
        # Create the testing virtualenv
        self.run_function('virtualenv.create', [self.venv_dir])
        ret = self.run_function(
            'pip.install', ['pep8==1.3.4'], bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except AssertionError:
            import pprint
            pprint.pprint(ret)
            raise

        ret = self.run_function(
            'pip.install',
            ['pep8'],
            bin_env=self.venv_dir,
            upgrade=True
        )

        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except AssertionError:
            import pprint
            pprint.pprint(ret)
            raise

        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )

        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('uninstalled pep8', ret['stdout'])
        except AssertionError:
            import pprint
            pprint.pprint(ret)
            raise

    def test_pip_install_multiple_editables(self):
        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        # Create the testing virtualenv
        self.run_function('virtualenv.create', [self.venv_dir])
        ret = self.run_function(
            'pip.install', [],
            editable='{0}'.format(','.join(editables)),
            bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn(
                'Successfully installed Blinker SaltTesting', ret['stdout']
            )
        except AssertionError:
            import pprint
            pprint.pprint(ret)
            raise

    def test_pip_install_multiple_editables_and_pkgs(self):
        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        # Create the testing virtualenv
        self.run_function('virtualenv.create', [self.venv_dir])
        ret = self.run_function(
            'pip.install', ['pep8'],
            editable='{0}'.format(','.join(editables)),
            bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)
            for package in ('Blinker', 'SaltTesting', 'pep8'):
                self.assertRegexpMatches(
                    ret['stdout'],
                    r'(?:.*)(Successfully installed)(?:.*)({0})(?:.*)'.format(package)
                )
        except AssertionError:
            import pprint
            pprint.pprint(ret)
            raise

    def tearDown(self):
        super(PipModuleTest, self).tearDown()
        if os.path.isdir(self.venv_test_dir):
            shutil.rmtree(self.venv_test_dir)
        if os.path.isdir(self.pip_temp):
            shutil.rmtree(self.pip_temp)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PipModuleTest)

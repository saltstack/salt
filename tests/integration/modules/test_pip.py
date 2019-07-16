# -*- coding: utf-8 -*-
'''
tests.integration.modules.pip
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
from git.compat import PY3
import os
import re
import sys
import shutil
import tempfile

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import patched_environ, destructiveTest

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES


class PipModuleTest(ModuleCase):
    '''
    These tests don't require the overhead of an environment being set up and torn down for them
    '''
    def setUp(self):
        super(PipModuleTest, self).setUp()

        # Restore the environ
        def cleanup_environ(environ):
            os.environ.clear()
            os.environ.update(environ)

        self.addCleanup(cleanup_environ, os.environ.copy())

    def test_issue_2087_missing_pip(self):
        # Run a pip depending functions with a non existent pip binary
        for func in ('pip.freeze', 'pip.list'):
            ret = self.run_function(func, bin_env=os.path.join(RUNTIME_VARS.TMP, 'no_pip'))
            self.assertIsInstance(ret, str)
            self.assertIn('command required for \'{0}\' not found: '.format(func), ret.lower())
            self.assertIn('could not find a pip binary', ret)

    @skipIf(salt.utils.path.which('deactivate'), 'Must not be in a virtual environment for this test')
    @destructiveTest
    def test_system_pip3(self):
        pip = salt.utils.path.which_bin(['pip3', 'pip3.7', 'pip3.6', 'pip2', 'pip2.7', 'pip'])
        if not pip:
            self.skipTest('System pip is not available')

        self.run_function('pip.install', pkgs=['lazyimport==0.0.1'], bin_env=pip)
        ret = self.run_function('cmd.run', [pip + ' -qqq freeze | grep lazyimport'])
        self.assertIsInstance(ret, list)
        self.assertIn('lazyimport==0.0.1', ret)

        self.run_function('pip.uninstall', pkgs=['lazyimport'], bin_env=pip)
        ret = self.run_function('cmd.run', [pip + ' -qqq freeze | grep lazyimport'])
        self.assertIsInstance(ret, list)
        self.assertNotIn('lazyimport', ret)


@skipIf(salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
class PipModuleVenvTest(ModuleCase):

    def setUp(self):
        super(PipModuleVenvTest, self).setUp()

        # Restore the environ
        def cleanup_environ(environ):
            os.environ.clear()
            os.environ.update(environ)

        self.addCleanup(cleanup_environ, os.environ.copy())

        self.venv_test_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        # Remove the venv test directory
        self.addCleanup(shutil.rmtree, self.venv_test_dir, ignore_errors=True)
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')
        self.pip_temp = os.path.join(self.venv_test_dir, '.pip-temp')
        # Remove the pip-temp directory
        self.addCleanup(shutil.rmtree, self.pip_temp, ignore_errors=True)
        if not os.path.isdir(self.pip_temp):
            os.makedirs(self.pip_temp)
        self.patched_environ = patched_environ(
            PIP_SOURCE_DIR='',
            PIP_BUILD_DIR='',
            __cleanup__=[k for k in os.environ if k.startswith('PIP_')]
        )
        self.patched_environ.__enter__()
        self.addCleanup(self.patched_environ.__exit__)
        for item in ('venv_dir', 'venv_test_dir', 'pip_temp'):
            self.addCleanup(delattr, self, item)

    @property
    def venv_kwargs(self):
        '''
        venv_kwargs only needs to be calculated once since it will be the same for every test

        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, on windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        '''
        if not hasattr(self, '_venv_kwargs'):
            # Default to the system python
            self._venv_kwargs = {}
            if hasattr(sys, 'real_prefix'):
                if salt.utils.platform.is_windows():
                    python = os.path.join(sys.real_prefix, os.path.basename(sys.executable))
                else:
                    python = os.path.join(sys.real_prefix, 'bin', os.path.basename(sys.executable))
                # We're running off a virtualenv, and we don't want to create a virtualenv off of a virtualenv

                # pyvenv 3.4 does not support the --python option
                if (3,) < sys.version_info > (3, 4):
                    self._venv_kwargs = {'python': python}
        return self._venv_kwargs

    def _create_virtualenv(self, path):
        ret = self.run_function('virtualenv.create', [path], **self.venv_kwargs)
        self.assertCmdSuccess(ret)

    def assertCmdSuccess(self, ret):
        self.assertIsInstance(ret, dict, ret)
        self.assertEqual(ret.get('retcode', None), 0, ret)

    def assertPipInstall(self, target, expect=('irc3-plugins-test', 'pep8')):
        '''
        isolate regex for extracting `successful install` message from pip
        '''
        if isinstance(target, dict):
            target = target.get('stdout', '')

        success = re.search(
            r'^.*Successfully installed\s([^\n]+)(?:Clean.*)?',
            target,
            re.M | re.S)
        self.assertTrue(success)

        for ex in expect:
            self.assertIn(ex, success.group(0))

    def test_requirements_as_list_of_chains__cwd_set__absolute_file_path(self):
        self._create_virtualenv(self.venv_dir)

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(self.venv_dir, 'requirements1.txt')
        req1b_filename = os.path.join(self.venv_dir, 'requirements1b.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        req2b_filename = os.path.join(self.venv_dir, 'requirements2b.txt')

        with salt.utils.files.fopen(req1_filename, 'w') as f:
            f.write('-r requirements1b.txt\n')
        with salt.utils.files.fopen(req1b_filename, 'w') as f:
            f.write('irc3-plugins-test\n')
        with salt.utils.files.fopen(req2_filename, 'w') as f:
            f.write('-r requirements2b.txt\n')
        with salt.utils.files.fopen(req2b_filename, 'w') as f:
            f.write('pep8\n')

        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list,
            bin_env=self.venv_dir, cwd=self.venv_dir
        )
        self.assertPipInstall(ret)

    def test_requirements_as_list_of_chains__cwd_not_set__absolute_file_path(self):
        self._create_virtualenv(self.venv_dir)

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(self.venv_dir, 'requirements1.txt')
        req1b_filename = os.path.join(self.venv_dir, 'requirements1b.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        req2b_filename = os.path.join(self.venv_dir, 'requirements2b.txt')

        with salt.utils.files.fopen(req1_filename, 'w') as f:
            f.write('-r requirements1b.txt\n')
        with salt.utils.files.fopen(req1b_filename, 'w') as f:
            f.write('irc3-plugins-test\n')
        with salt.utils.files.fopen(req2_filename, 'w') as f:
            f.write('-r requirements2b.txt\n')
        with salt.utils.files.fopen(req2b_filename, 'w') as f:
            f.write('pep8\n')

        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list, bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertPipInstall(ret)

    def test_requirements_as_list__absolute_file_path(self):
        self._create_virtualenv(self.venv_dir)

        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')

        with salt.utils.files.fopen(req1_filename, 'w') as f:
            f.write('irc3-plugins-test\n')
        with salt.utils.files.fopen(req2_filename, 'w') as f:
            f.write('pep8\n')

        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list, bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertPipInstall(ret)

    def test_requirements_as_list__non_absolute_file_path(self):
        self._create_virtualenv(self.venv_dir)

        # Create a requirements file that depends on another one.

        req1_filename = 'requirements.txt'
        req2_filename = 'requirements2.txt'
        req_cwd = self.venv_dir

        req1_filepath = os.path.join(req_cwd, req1_filename)
        req2_filepath = os.path.join(req_cwd, req2_filename)

        with salt.utils.files.fopen(req1_filepath, 'w') as f:
            f.write('irc3-plugins-test\n')
        with salt.utils.files.fopen(req2_filepath, 'w') as f:
            f.write('pep8\n')

        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list,
            bin_env=self.venv_dir, cwd=req_cwd
        )

        self.assertCmdSuccess(ret)
        self.assertPipInstall(ret)

    def test_chained_requirements__absolute_file_path(self):
        self._create_virtualenv(self.venv_dir)

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')

        with salt.utils.files.fopen(req1_filename, 'w') as f:
            f.write('-r requirements2.txt')
        with salt.utils.files.fopen(req2_filename, 'w') as f:
            f.write('pep8')

        ret = self.run_function(
            'pip.install', requirements=req1_filename, bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertIn('installed pep8', ret['stdout'])

    def test_chained_requirements__non_absolute_file_path(self):
        self._create_virtualenv(self.venv_dir)

        # Create a requirements file that depends on another one.
        req_basepath = (self.venv_dir)

        req1_filename = 'requirements.txt'
        req2_filename = 'requirements2.txt'

        req1_file = os.path.join(self.venv_dir, req1_filename)
        req2_file = os.path.join(self.venv_dir, req2_filename)

        with salt.utils.files.fopen(req1_file, 'w') as f:
            f.write('-r requirements2.txt')
        with salt.utils.files.fopen(req2_file, 'w') as f:
            f.write('pep8')

        ret = self.run_function(
            'pip.install', requirements=req1_filename, cwd=req_basepath,
            bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertIn('installed pep8', ret['stdout'])

    def test_issue_4805_nested_requirements(self):
        self._create_virtualenv(self.venv_dir)

        # Create a requirements file that depends on another one.
        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        with salt.utils.files.fopen(req1_filename, 'w') as f:
            f.write('-r requirements2.txt')
        with salt.utils.files.fopen(req2_filename, 'w') as f:
            f.write('pep8')

        ret = self.run_function(
            'pip.install', requirements=req1_filename, bin_env=self.venv_dir, timeout=300)

        self.assertCmdSuccess(ret)
        self.assertNotIn('URLError', ret['stdout'])
        self.assertNotIn('Download error', ret['stdout'])
        self.assertIn('installed pep8', ret['stdout'])

    def test_pip_uninstall(self):
        # Let's create the testing virtualenv
        self._create_virtualenv(self.venv_dir)
        ret = self.run_function('pip.install', ['pep8'], bin_env=self.venv_dir)

        self.assertCmdSuccess(ret)
        self.assertNotIn('URLError', ret['stdout'])
        self.assertNotIn('Download error', ret['stdout'])
        self.assertIn('installed pep8', ret['stdout'])

        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertIn('uninstalled pep8', ret['stdout'])

    def test_pip_install_upgrade(self):
        # Create the testing virtualenv
        self._create_virtualenv(self.venv_dir)
        ret = self.run_function(
            'pip.install', ['pep8==1.3.4'], bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertNotIn('URLError', ret['stdout'])
        self.assertNotIn('Download error', ret['stdout'])
        self.assertIn('installed pep8', ret['stdout'])

        ret = self.run_function(
            'pip.install',
            ['pep8'],
            bin_env=self.venv_dir,
            upgrade=True
        )

        self.assertCmdSuccess(ret)
        self.assertNotIn('URLError', ret['stdout'])
        self.assertNotIn('Download error', ret['stdout'])
        self.assertIn('installed pep8', ret['stdout'])

        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertIn('uninstalled pep8', ret['stdout'])

    def test_pip_install_multiple_editables(self):
        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        # Create the testing virtualenv
        self._create_virtualenv(self.venv_dir)
        ret = self.run_function(
            'pip.install', [],
            editable='{0}'.format(','.join(editables)),
            bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertNotIn('URLError', ret['stdout'])
        self.assertNotIn('Download error', ret['stdout'])
        self.assertIn(
            'Successfully installed Blinker SaltTesting', ret['stdout']
        )

    def test_pip_install_multiple_editables_and_pkgs(self):
        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        # Create the testing virtualenv
        self._create_virtualenv(self.venv_dir)
        ret = self.run_function(
            'pip.install', ['pep8'],
            editable='{0}'.format(','.join(editables)),
            bin_env=self.venv_dir
        )

        self.assertCmdSuccess(ret)
        self.assertNotIn('URLError', ret['stdout'])
        self.assertNotIn('Download error', ret['stdout'])

        # Only run this function if we are in python3, as assertRegex doesn't exist in python2.7
        if PY3:
            for package in ('Blinker', 'SaltTesting', 'pep8'):
                self.assertRegex(
                    ret['stdout'],
                    r'(?:.*)(Successfully installed)(?:.*)({0})(?:.*)'.format(package)
                )

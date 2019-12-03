# -*- coding: utf-8 -*-
'''
tests.integration.modules.pip
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import re
import sys
import pprint
import shutil
import tempfile

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.paths import TMP

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES


@skipIf(salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
class PipModuleTest(ModuleCase):

    def setUp(self):
        super(PipModuleTest, self).setUp()

        # Restore the environ
        def cleanup_environ(environ):
            os.environ.clear()
            os.environ.update(environ)

        self.addCleanup(cleanup_environ, os.environ.copy())

        self.venv_test_dir = tempfile.mkdtemp(dir=TMP)
        # Remove the venv test directory
        self.addCleanup(shutil.rmtree, self.venv_test_dir, ignore_errors=True)
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')
        for key in os.environ.copy():
            if key.startswith('PIP_'):
                os.environ.pop(key)
        self.pip_temp = os.path.join(self.venv_test_dir, '.pip-temp')
        # Remove the pip-temp directory
        self.addCleanup(shutil.rmtree, self.pip_temp, ignore_errors=True)
        if not os.path.isdir(self.pip_temp):
            os.makedirs(self.pip_temp)
        os.environ['PIP_SOURCE_DIR'] = os.environ['PIP_BUILD_DIR'] = ''
        for item in ('venv_dir', 'venv_test_dir', 'pip_temp'):
            self.addCleanup(delattr, self, item)

    def _create_virtualenv(self, path):
        '''
        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, one windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        '''
        try:
            if salt.utils.is_windows():
                python = os.path.join(sys.real_prefix, os.path.basename(sys.executable))
            else:
                python_binary_names = [
                    'python{}.{}'.format(*sys.version_info),
                    'python{}'.format(*sys.version_info),
                    'python'
                ]
                for binary_name in python_binary_names:
                    python = os.path.join(sys.real_prefix, 'bin', binary_name)
                    if os.path.exists(python):
                        break
                else:
                    self.fail(
                        'Couldn\'t find a python binary name under \'{}\' matching: {}'.format(
                            os.path.join(sys.real_prefix, 'bin'),
                            python_binary_names
                        )
                    )
            # We're running off a virtualenv, and we don't want to create a virtualenv off of
            # a virtualenv
            kwargs = {'python': python}
        except AttributeError:
            # We're running off of the system python
            kwargs = {}
        self.run_function('virtualenv.create', [path], **kwargs)

    def _check_download_error(self, ret):
        '''
        Checks to see if a download error looks transitory
        '''
        return any(w in ret for w in ['URLError', 'Download error'])

    def pip_successful_install(self, target, expect=('irc3-plugins-test', 'pep8',)):
        '''
        isolate regex for extracting `successful install` message from pip
        '''

        expect = set(expect)
        expect_str = '|'.join(expect)

        success = re.search(
            r'^.*Successfully installed\s([^\n]+)(?:Clean.*)?',
            target,
            re.M | re.S)

        success_for = re.findall(
            r'({0})(?:-(?:[\d\.-]))?'.format(expect_str),
            success.groups()[0]
        ) if success else []

        return expect.issubset(set(success_for))

    def test_issue_2087_missing_pip(self):
        # Let's create the testing virtualenv
        self._create_virtualenv(self.venv_dir)

        # Let's remove the pip binary
        pip_bin = os.path.join(self.venv_dir, 'bin', 'pip')
        site_dir = self.run_function('virtualenv.get_distribution_path', [self.venv_dir, 'pip'])
        if salt.utils.platform.is_windows():
            pip_bin = os.path.join(self.venv_dir, 'Scripts', 'pip.exe')
            site_dir = os.path.join(self.venv_dir, 'lib', 'site-packages')
        if not os.path.isfile(pip_bin):
            self.skipTest(
                'Failed to find the pip binary to the test virtualenv'
            )
        os.remove(pip_bin)

        # Also remove the pip dir from site-packages
        # This is needed now that we're using python -m pip instead of the
        # pip binary directly. python -m pip will still work even if the
        # pip binary is missing
        shutil.rmtree(os.path.join(site_dir, 'pip'))

        # Let's run a pip depending functions
        for func in ('pip.freeze', 'pip.list'):
            ret = self.run_function(func, bin_env=self.venv_dir)
            self.assertIn(
                'Command required for \'{0}\' not found: '
                'Could not find a `pip` binary'.format(func),
                ret
            )

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
        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            found = self.pip_successful_install(ret['stdout'])
            self.assertTrue(found)
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

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

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            found = self.pip_successful_install(ret['stdout'])
            self.assertTrue(found)
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

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

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            found = self.pip_successful_install(ret['stdout'])
            self.assertTrue(found)
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

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

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            found = self.pip_successful_install(ret['stdout'])
            self.assertTrue(found)
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

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
        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

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
        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

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

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            if self._check_download_error(ret['stdout']):
                self.skipTest('Test skipped due to pip download error')
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

    def test_pip_uninstall(self):
        # Let's create the testing virtualenv
        self._create_virtualenv(self.venv_dir)
        ret = self.run_function('pip.install', ['pep8'], bin_env=self.venv_dir)

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            if self._check_download_error(ret['stdout']):
                self.skipTest('Test skipped due to pip download error')
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )
        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.uninstall\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('uninstalled pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

    def test_pip_install_upgrade(self):
        # Create the testing virtualenv
        self._create_virtualenv(self.venv_dir)
        ret = self.run_function(
            'pip.install', ['pep8==1.3.4'], bin_env=self.venv_dir
        )

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            if self._check_download_error(ret['stdout']):
                self.skipTest('Test skipped due to pip download error')
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

        ret = self.run_function(
            'pip.install',
            ['pep8'],
            bin_env=self.venv_dir,
            upgrade=True
        )

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            if self._check_download_error(ret['stdout']):
                self.skipTest('Test skipped due to pip download error')
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

        ret = self.run_function(
            'pip.uninstall', ['pep8'], bin_env=self.venv_dir
        )

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.uninstall\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('uninstalled pep8', ret['stdout'])
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

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

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            if self._check_download_error(ret['stdout']):
                self.skipTest('Test skipped due to pip download error')
            self.assertEqual(ret['retcode'], 0)
            self.assertIn(
                'Successfully installed Blinker SaltTesting', ret['stdout']
            )
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
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

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        try:
            if self._check_download_error(ret['stdout']):
                self.skipTest('Test skipped due to pip download error')
            self.assertEqual(ret['retcode'], 0)
            for package in ('Blinker', 'SaltTesting', 'pep8'):
                self.assertRegex(
                    ret['stdout'],
                    r'(?:.*)(Successfully installed)(?:.*)({0})(?:.*)'.format(package)
                )
        except KeyError as exc:
            self.fail(
                'The returned dictionary is missing an expected key. Error: \'{}\'. Dictionary: {}'.format(
                    exc,
                    pprint.pformat(ret)
                )
            )

    @skipIf(not os.path.isfile('pip3'), 'test where pip3 is installed')
    @skipIf(salt.utils.platform.is_windows(), 'test specific for linux usage of /bin/python')
    def test_system_pip3(self):
        self.run_function('pip.install', pkgs=['lazyimport==0.0.1'], bin_env='/bin/pip3')
        ret1 = self.run_function('cmd.run', '/bin/pip3 freeze | grep lazyimport')
        self.run_function('pip.uninstall', pkgs=['lazyimport'], bin_env='/bin/pip3')
        ret2 = self.run_function('cmd.run', '/bin/pip3 freeze | grep lazyimport')
        assert 'lazyimport==0.0.1' in ret1
        assert ret2 == ''

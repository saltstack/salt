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
import re
import tempfile

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.paths import TMP
from tests.support.helpers import skip_if_not_root

# Import salt libs
import salt.utils
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES


@skipIf(salt.utils.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
class PipModuleTest(ModuleCase):

    def setUp(self):
        super(PipModuleTest, self).setUp()

        self.venv_test_dir = tempfile.mkdtemp(dir=TMP)
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')
        for key in os.environ.copy():
            if key.startswith('PIP_'):
                os.environ.pop(key)
        self.pip_temp = os.path.join(self.venv_test_dir, '.pip-temp')
        if not os.path.isdir(self.pip_temp):
            os.makedirs(self.pip_temp)
        os.environ['PIP_SOURCE_DIR'] = os.environ['PIP_BUILD_DIR'] = ''

    def _check_download_error(self, ret):
        '''
        Checks to see if a download error looks transitory
        '''
        return any(w in ret for w in ['URLError', 'Download error'])

    def pip_successful_install(self, target, expect=('flake8', 'pep8',)):
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

    @skip_if_not_root
    def test_requirements_as_list_of_chains__sans_no_chown__cwd_set__absolute_file_path(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(self.venv_dir, 'requirements1.txt')
        req1b_filename = os.path.join(self.venv_dir, 'requirements1b.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        req2b_filename = os.path.join(self.venv_dir, 'requirements2b.txt')

        with salt.utils.fopen(req1_filename, 'w') as f:
            f.write('-r requirements1b.txt\n')
        with salt.utils.fopen(req1b_filename, 'w') as f:
            f.write('flake8\n')
        with salt.utils.fopen(req2_filename, 'w') as f:
            f.write('-r requirements2b.txt\n')
        with salt.utils.fopen(req2b_filename, 'w') as f:
            f.write('pep8\n')

        this_user = pwd.getpwuid(os.getuid())[0]
        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list, user=this_user,
            bin_env=self.venv_dir, cwd=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)

            found = self.pip_successful_install(ret['stdout'])

            self.assertTrue(found)
        except (AssertionError, TypeError):
            import pprint
            pprint.pprint(ret)
            raise

    @skip_if_not_root
    def test_requirements_as_list_of_chains__sans_no_chown__cwd_not_set__absolute_file_path(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(self.venv_dir, 'requirements1.txt')
        req1b_filename = os.path.join(self.venv_dir, 'requirements1b.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        req2b_filename = os.path.join(self.venv_dir, 'requirements2b.txt')

        with salt.utils.fopen(req1_filename, 'w') as f:
            f.write('-r requirements1b.txt\n')
        with salt.utils.fopen(req1b_filename, 'w') as f:
            f.write('flake8\n')
        with salt.utils.fopen(req2_filename, 'w') as f:
            f.write('-r requirements2b.txt\n')
        with salt.utils.fopen(req2b_filename, 'w') as f:
            f.write('pep8\n')

        this_user = pwd.getpwuid(os.getuid())[0]
        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list, user=this_user,
            bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)

            found = self.pip_successful_install(ret['stdout'])

            self.assertTrue(found)

        except (AssertionError, TypeError):
            import pprint
            pprint.pprint(ret)
            raise

    @skip_if_not_root
    def test_requirements_as_list__sans_no_chown__absolute_file_path(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')

        with salt.utils.fopen(req1_filename, 'w') as f:
            f.write('flake8\n')
        with salt.utils.fopen(req2_filename, 'w') as f:
            f.write('pep8\n')

        this_user = pwd.getpwuid(os.getuid())[0]
        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list, user=this_user,
            bin_env=self.venv_dir
        )

        found = self.pip_successful_install(ret['stdout'])

        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertTrue(found)

        except (AssertionError, TypeError):
            import pprint
            pprint.pprint(ret)
            raise

    @skip_if_not_root
    def test_requirements_as_list__sans_no_chown__non_absolute_file_path(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.

        req1_filename = 'requirements.txt'
        req2_filename = 'requirements2.txt'
        req_cwd = self.venv_dir

        req1_filepath = os.path.join(req_cwd, req1_filename)
        req2_filepath = os.path.join(req_cwd, req2_filename)

        with salt.utils.fopen(req1_filepath, 'w') as f:
            f.write('flake8\n')
        with salt.utils.fopen(req2_filepath, 'w') as f:
            f.write('pep8\n')

        this_user = pwd.getpwuid(os.getuid())[0]
        requirements_list = [req1_filename, req2_filename]

        ret = self.run_function(
            'pip.install', requirements=requirements_list, user=this_user,
            bin_env=self.venv_dir, cwd=req_cwd
        )
        try:
            self.assertEqual(ret['retcode'], 0)

            found = self.pip_successful_install(ret['stdout'])
            self.assertTrue(found)

        except (AssertionError, TypeError):
            import pprint
            pprint.pprint(ret)
            raise

    @skip_if_not_root
    def test_chained_requirements__sans_no_chown__absolute_file_path(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')

        with salt.utils.fopen(req1_filename, 'w') as f:
            f.write('-r requirements2.txt')
        with salt.utils.fopen(req2_filename, 'w') as f:
            f.write('pep8')

        this_user = pwd.getpwuid(os.getuid())[0]
        ret = self.run_function(
            'pip.install', requirements=req1_filename, user=this_user,
            bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except (AssertionError, TypeError):
            import pprint
            pprint.pprint(ret)
            raise

    @skip_if_not_root
    def test_chained_requirements__sans_no_chown__non_absolute_file_path(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.
        req_basepath = (self.venv_dir)

        req1_filename = 'requirements.txt'
        req2_filename = 'requirements2.txt'

        req1_file = os.path.join(self.venv_dir, req1_filename)
        req2_file = os.path.join(self.venv_dir, req2_filename)

        with salt.utils.fopen(req1_file, 'w') as f:
            f.write('-r requirements2.txt')
        with salt.utils.fopen(req2_file, 'w') as f:
            f.write('pep8')

        this_user = pwd.getpwuid(os.getuid())[0]
        ret = self.run_function(
            'pip.install', requirements=req1_filename, user=this_user,
            no_chown=False, cwd=req_basepath, bin_env=self.venv_dir
        )
        try:
            self.assertEqual(ret['retcode'], 0)
            self.assertIn('installed pep8', ret['stdout'])
        except (AssertionError, TypeError):
            import pprint
            pprint.pprint(ret)
            raise

    @skip_if_not_root
    def test_issue_4805_nested_requirements_user_no_chown(self):
        self.run_function('virtualenv.create', [self.venv_dir])

        # Create a requirements file that depends on another one.
        req1_filename = os.path.join(self.venv_dir, 'requirements.txt')
        req2_filename = os.path.join(self.venv_dir, 'requirements2.txt')
        with salt.utils.fopen(req1_filename, 'w') as f:
            f.write('-r requirements2.txt')
        with salt.utils.fopen(req2_filename, 'w') as f:
            f.write('pep8')

        this_user = pwd.getpwuid(os.getuid())[0]
        ret = self.run_function(
            'pip.install', requirements=req1_filename, user=this_user,
            no_chown=True, bin_env=self.venv_dir
        )
        if self._check_download_error(ret['stdout']):
            self.skipTest('Test skipped due to pip download error')
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
        if self._check_download_error(ret['stdout']):
            self.skipTest('Test skipped due to pip download error')
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
        if self._check_download_error(ret['stdout']):
            self.skipTest('Test skipped due to pip download error')
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
        if self._check_download_error(ret['stdout']):
            self.skipTest('Test skipped due to pip download error')
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
        if self._check_download_error(ret['stdout']):
            self.skipTest('Test skipped due to pip download error')
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
        if self._check_download_error(ret['stdout']):
            self.skipTest('Test skipped due to pip download error')
        try:
            self.assertEqual(ret['retcode'], 0)
            for package in ('Blinker', 'SaltTesting', 'pep8'):
                self.assertRegex(
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
        del self.venv_dir
        del self.venv_test_dir
        del self.pip_temp

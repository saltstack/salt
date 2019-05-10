# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.states.pip_state
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import os
import glob
import pprint
import shutil
import sys

try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains,
    with_system_user,
    skip_if_not_root,
    with_tempdir
)
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.versions
import salt.utils.win_dacl
import salt.utils.win_functions
import salt.utils.win_runas
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six


def can_runas():
    '''
    Detect if we are running in a limited shell (winrm) and are un-able to use
    the runas utility method.
    '''
    if salt.utils.platform.is_windows():
        try:
            salt.utils.win_runas.runas(
                'cmd.exe /c echo 1', 'noexistuser', 'n0existp4ss',
            )
        except WindowsError as exc:  # pylint: disable=undefined-variable
            if exc.winerror == 5:
                # Access Denied
                return False
    return True


CAN_RUNAS = can_runas()


class VirtualEnv(object):
    def __init__(self, test, venv_dir):
        self.venv_dir = venv_dir
        self.test = test
        self.test.addCleanup(shutil.rmtree, self.venv_dir, ignore_errors=True)

    def __enter__(self):
        ret = self.test._create_virtualenv(self.venv_dir)
        self.test.assertEqual(
            ret['retcode'], 0,
            msg='Expected \'retcode\' key did not match. Full return dictionary:\n{}'.format(
                pprint.pformat(ret)
            )
        )

    def __exit__(self, *args):
        pass


@skipIf(salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
class PipStateTest(ModuleCase, SaltReturnAssertsMixin):

    def _create_virtualenv(self, path, **kwargs):
        '''
        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, one windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        '''
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        try:
            if salt.utils.platform.is_windows():
                python = os.path.join(sys.real_prefix, os.path.basename(sys.executable))
            else:
                python = os.path.join(sys.real_prefix, 'bin', os.path.basename(sys.executable))
            # We're running off a virtualenv, and we don't want to create a virtualenv off of
            # a virtualenv, let's point to the actual python that created the virtualenv
            kwargs['python'] = python
        except AttributeError:
            # We're running off of the system python
            pass
        return self.run_function('virtualenv.create', [path], **kwargs)

    def test_pip_installed_removed(self):
        '''
        Tests installed and removed states
        '''
        name = 'pudb'
        if name in self.run_function('pip.list'):
            self.skipTest('{0} is already installed, uninstall to run this test'.format(name))
        ret = self.run_state('pip.installed', name=name)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pip.removed', name=name)
        self.assertSaltTrueReturn(ret)

    def test_pip_installed_removed_venv(self):
        venv_dir = os.path.join(
            RUNTIME_VARS.TMP, 'pip_installed_removed'
        )
        with VirtualEnv(self, venv_dir):
            name = 'pudb'
            ret = self.run_state('pip.installed', name=name, bin_env=venv_dir)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pip.removed', name=name, bin_env=venv_dir)
            self.assertSaltTrueReturn(ret)

    def test_pip_installed_errors(self):
        venv_dir = os.path.join(
            RUNTIME_VARS.TMP, 'pip-installed-errors'
        )

        def cleanup_environ(environ):
            os.environ.clear()
            os.environ.update(environ)

        self.addCleanup(cleanup_environ, os.environ.copy())

        # Since we don't have the virtualenv created, pip.installed will
        # throw an error.
        # Example error strings:
        #  * "Error installing 'pep8': /tmp/pip-installed-errors: not found"
        #  * "Error installing 'pep8': /bin/sh: 1: /tmp/pip-installed-errors: not found"
        #  * "Error installing 'pep8': /bin/bash: /tmp/pip-installed-errors: No such file or directory"
        os.environ['SHELL'] = '/bin/sh'
        ret = self.run_function('state.sls', mods='pip-installed-errors')
        self.assertSaltFalseReturn(ret)
        self.assertSaltCommentRegexpMatches(
            ret,
            'Error installing \'pep8\':'
        )

        # We now create the missing virtualenv
        ret = self._create_virtualenv(venv_dir)
        self.assertEqual(ret['retcode'], 0)

        # The state should not have any issues running now
        ret = self.run_function('state.sls', mods='pip-installed-errors')
        self.assertSaltTrueReturn(ret)

    @skipIf(six.PY3, 'Issue is specific to carbon module, which is PY2-only')
    @skipIf(salt.utils.platform.is_windows(), "Carbon does not install in Windows")
    @requires_system_grains
    def test_pip_installed_weird_install(self, grains=None):
        # First, check to see if this is running on CentOS 5 or MacOS.
        # If so, skip this test.
        if grains['os'] in ('CentOS',) and grains['osrelease_info'][0] in (5,):
            self.skipTest('This test does not run reliably on CentOS 5')
        if grains['os'] in ('MacOS',):
            self.skipTest('This test does not run reliably on MacOS')

        ographite = '/opt/graphite'
        if os.path.isdir(ographite):
            self.skipTest(
                'You already have \'{0}\'. This test would overwrite this '
                'directory'.format(ographite)
            )
        try:
            os.makedirs(ographite)
        except OSError as err:
            if err.errno == errno.EACCES:
                # Permission denied
                self.skipTest(
                    'You don\'t have the required permissions to run this test'
                )
        finally:
            if os.path.isdir(ographite):
                shutil.rmtree(ographite, ignore_errors=True)

        venv_dir = os.path.join(RUNTIME_VARS.TMP, 'pip-installed-weird-install')
        try:
            # We may be able to remove this, I had to add it because the custom
            # modules from the test suite weren't available in the jinja
            # context when running the call to state.sls that comes after.
            self.run_function('saltutil.sync_modules')
            # Since we don't have the virtualenv created, pip.installed will
            # throw an error.
            ret = self.run_function(
                'state.sls', mods='pip-installed-weird-install'
            )
            self.assertSaltTrueReturn(ret)

            # We cannot use assertInSaltComment here because we need to skip
            # some of the state return parts
            for key in six.iterkeys(ret):
                self.assertTrue(ret[key]['result'])
                if ret[key]['name'] != 'carbon < 1.1':
                    continue
                self.assertEqual(
                    ret[key]['comment'],
                    'There was no error installing package \'carbon < 1.1\' '
                    'although it does not show when calling \'pip.freeze\'.'
                )
                break
            else:
                raise Exception('Expected state did not run')
        finally:
            if os.path.isdir(ographite):
                shutil.rmtree(ographite, ignore_errors=True)

    def test_issue_2028_pip_installed_state(self):
        ret = self.run_function('state.sls', mods='issue-2028-pip-installed')

        venv_dir = os.path.join(
            RUNTIME_VARS.TMP, 'issue-2028-pip-installed'
        )
        self.addCleanup(shutil.rmtree, venv_dir, ignore_errors=True)

        pep8_bin = os.path.join(venv_dir, 'bin', 'pep8')
        if salt.utils.platform.is_windows():
            pep8_bin = os.path.join(venv_dir, 'Scripts', 'pep8.exe')

        self.assertSaltTrueReturn(ret)
        self.assertTrue(
            os.path.isfile(pep8_bin)
        )

    def test_issue_2087_missing_pip(self):
        venv_dir = os.path.join(
            RUNTIME_VARS.TMP, 'issue-2087-missing-pip'
        )

        # Let's create the testing virtualenv
        ret = self._create_virtualenv(venv_dir)
        self.assertEqual(
            ret['retcode'], 0,
            msg='Expected \'retcode\' key did not match. Full return dictionary:\n{}'.format(
                pprint.pformat(ret)
            )
        )

        # Let's remove the pip binary
        pip_bin = os.path.join(venv_dir, 'bin', 'pip')
        site_dir = self.run_function('virtualenv.get_distribution_path', [venv_dir, 'pip'])
        if salt.utils.is_windows():
            pip_bin = os.path.join(venv_dir, 'Scripts', 'pip.exe')
            site_dir = os.path.join(venv_dir, 'lib', 'site-packages')
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

        # Let's run the state which should fail because pip is missing
        ret = self.run_function('state.sls', mods='issue-2087-missing-pip')
        self.assertSaltFalseReturn(ret)
        self.assertInSaltComment(
            'Error installing \'pep8\': Could not find a `pip` binary',
            ret
        )

    def test_issue_5940_multiple_pip_mirrors(self):
        '''
        Test multiple pip mirrors.  This test only works with pip < 7.0.0
        '''
        ret = self.run_function(
            'state.sls', mods='issue-5940-multiple-pip-mirrors'
        )

        venv_dir = os.path.join(
            RUNTIME_VARS.TMP, '5940-multiple-pip-mirrors'
        )
        self.addCleanup(shutil.rmtree, venv_dir, ignore_errors=True)

        try:
            self.assertSaltTrueReturn(ret)
            self.assertTrue(
                os.path.isfile(os.path.join(venv_dir, 'bin', 'pep8'))
            )
        except (AssertionError, CommandExecutionError):
            pip_version = self.run_function('pip.version', [venv_dir])
            if salt.utils.versions.compare(ver1=pip_version, oper='>=', ver2='7.0.0'):
                self.skipTest('the --mirrors arg has been deprecated and removed in pip==7.0.0')

    @destructiveTest
    @skip_if_not_root
    @skipIf(not CAN_RUNAS, 'Runas support required')
    @with_system_user('issue-6912', on_existing='delete', delete=True,
                      password='PassWord1!')
    @with_tempdir()
    def test_issue_6912_wrong_owner(self, temp_dir, username):
        # Setup virtual environment directory to be used throughout the test
        venv_dir = os.path.join(temp_dir, '6912-wrong-owner')

        # The virtual environment needs to be in a location that is accessible
        # by both the user running the test and the runas user
        if salt.utils.platform.is_windows():
            salt.utils.win_dacl.set_permissions(temp_dir, username, 'full_control')
        else:
            uid = self.run_function('file.user_to_uid', [username])
            os.chown(temp_dir, uid, -1)

        # Create the virtual environment
        venv_create = self._create_virtualenv(venv_dir, user=username, password='PassWord1!')
        if venv_create['retcode'] > 0:
            self.skipTest('Failed to create testcase virtual environment: {0}'
                          ''.format(venv_create))

        # pip install passing the package name in `name`
        ret = self.run_state(
            'pip.installed', name='pep8', user=username, bin_env=venv_dir,
            password='PassWord1!')
        self.assertSaltTrueReturn(ret)

        if HAS_PWD:
            uid = pwd.getpwnam(username).pw_uid
        for globmatch in (os.path.join(venv_dir, '**', 'pep8*'),
                          os.path.join(venv_dir, '*', '**', 'pep8*'),
                          os.path.join(venv_dir, '*', '*', '**', 'pep8*')):
            for path in glob.glob(globmatch):
                if HAS_PWD:
                    self.assertEqual(uid, os.stat(path).st_uid)
                elif salt.utils.platform.is_windows():
                    self.assertEqual(
                        salt.utils.win_dacl.get_owner(path), username)

    @destructiveTest
    @skip_if_not_root
    @skipIf(salt.utils.platform.is_darwin(), 'Test is flaky on macosx')
    @skipIf(not CAN_RUNAS, 'Runas support required')
    @with_system_user('issue-6912', on_existing='delete', delete=True,
                      password='PassWord1!')
    @with_tempdir()
    def test_issue_6912_wrong_owner_requirements_file(self, temp_dir, username):
        # Setup virtual environment directory to be used throughout the test
        venv_dir = os.path.join(temp_dir, '6912-wrong-owner')

        # The virtual environment needs to be in a location that is accessible
        # by both the user running the test and the runas user
        if salt.utils.platform.is_windows():
            salt.utils.win_dacl.set_permissions(temp_dir, username, 'full_control')
        else:
            uid = self.run_function('file.user_to_uid', [username])
            os.chown(temp_dir, uid, -1)

        # Create the virtual environment again as it should have been removed
        venv_create = self._create_virtualenv(venv_dir, user=username, password='PassWord1!')
        if venv_create['retcode'] > 0:
            self.skipTest('failed to create testcase virtual environment: {0}'
                          ''.format(venv_create))

        # pip install using a requirements file
        req_filename = os.path.join(
            RUNTIME_VARS.TMP_STATE_TREE, 'issue-6912-requirements.txt'
        )
        with salt.utils.files.fopen(req_filename, 'wb') as reqf:
            reqf.write(b'pep8\n')

        ret = self.run_state(
            'pip.installed', name='', user=username, bin_env=venv_dir,
            requirements='salt://issue-6912-requirements.txt',
            password='PassWord1!')
        self.assertSaltTrueReturn(ret)

        if HAS_PWD:
            uid = pwd.getpwnam(username).pw_uid
        for globmatch in (os.path.join(venv_dir, '**', 'pep8*'),
                          os.path.join(venv_dir, '*', '**', 'pep8*'),
                          os.path.join(venv_dir, '*', '*', '**', 'pep8*')):
            for path in glob.glob(globmatch):
                if HAS_PWD:
                    self.assertEqual(uid, os.stat(path).st_uid)
                elif salt.utils.platform.is_windows():
                    self.assertEqual(
                        salt.utils.win_dacl.get_owner(path), username)

    def test_issue_6833_pip_upgrade_pip(self):
        # Create the testing virtualenv
        venv_dir = os.path.join(
            RUNTIME_VARS.TMP, '6833-pip-upgrade-pip'
        )
        ret = self._create_virtualenv(venv_dir)

        self.assertEqual(
            ret['retcode'], 0,
            msg='Expected \'retcode\' key did not match. Full return dictionary:\n{}'.format(
                pprint.pformat(ret)
            )
        )
        self.assertIn(
            'New python executable',
            ret['stdout'],
            msg='Expected STDOUT did not match. Full return dictionary:\n{}'.format(
                pprint.pformat(ret)
            )
        )

        # Let's install a fixed version pip over whatever pip was
        # previously installed
        ret = self.run_function(
            'pip.install', ['pip==8.0'], upgrade=True,
            bin_env=venv_dir
        )

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        self.assertEqual(ret['retcode'], 0)
        self.assertIn(
            'Successfully installed pip',
            ret['stdout']
        )

        # Let's make sure we have pip 8.0 installed
        self.assertEqual(
            self.run_function('pip.list', ['pip'], bin_env=venv_dir),
            {'pip': '8.0.0'}
        )

        # Now the actual pip upgrade pip test
        ret = self.run_state(
            'pip.installed', name='pip==8.0.1', upgrade=True,
            bin_env=venv_dir
        )

        if not isinstance(ret, dict):
            self.fail(
                'The \'pip.install\' command did not return the excepted dictionary. Output:\n{}'.format(ret)
            )

        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {'pip==8.0.1': 'Installed'})

    def test_pip_installed_specific_env(self):
        # Create the testing virtualenv
        venv_dir = os.path.join(
            RUNTIME_VARS.TMP, 'pip-installed-specific-env'
        )

        # Let's write a requirements file
        requirements_file = os.path.join(
            RUNTIME_VARS.TMP_PRODENV_STATE_TREE, 'prod-env-requirements.txt'
        )
        with salt.utils.files.fopen(requirements_file, 'wb') as reqf:
            reqf.write(b'pep8\n')

        try:
            self._create_virtualenv(venv_dir)

            # The requirements file should not be found the base environment
            ret = self.run_state(
                'pip.installed', name='', bin_env=venv_dir,
                requirements='salt://prod-env-requirements.txt'
            )
            self.assertSaltFalseReturn(ret)
            self.assertInSaltComment(
                "'salt://prod-env-requirements.txt' not found", ret
            )

            # The requirements file must be found in the prod environment
            ret = self.run_state(
                'pip.installed', name='', bin_env=venv_dir, saltenv='prod',
                requirements='salt://prod-env-requirements.txt'
            )
            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment(
                'Successfully processed requirements file '
                'salt://prod-env-requirements.txt', ret
            )

            # We're using the base environment but we're passing the prod
            # environment as an url arg to salt://
            ret = self.run_state(
                'pip.installed', name='', bin_env=venv_dir,
                requirements='salt://prod-env-requirements.txt?saltenv=prod'
            )
            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment(
                'Requirements were already installed.',
                ret
            )
        finally:
            if os.path.isfile(requirements_file):
                os.unlink(requirements_file)

    def test_22359_pip_installed_unless_does_not_trigger_warnings(self):
        # This test case should be moved to a format_call unit test specific to
        # the state internal keywords
        venv_dir = os.path.join(RUNTIME_VARS.TMP, 'pip-installed-unless')
        venv_create = self._create_virtualenv(venv_dir)
        if venv_create['retcode'] > 0:
            self.skipTest(
                'Failed to create testcase virtual environment: {0}'.format(
                    venv_create
                )
            )

        false_cmd = '/bin/false'
        if salt.utils.platform.is_windows():
            false_cmd = 'exit 1 >nul'
        try:
            ret = self.run_state(
                'pip.installed', name='pep8', bin_env=venv_dir, unless=false_cmd
            )
            self.assertSaltTrueReturn(ret)
            self.assertNotIn('warnings', next(six.itervalues(ret)))
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir, ignore_errors=True)

    @skipIf(sys.version_info[:2] >= (3, 6), 'Old version of virtualenv too old for python3.6')
    @skipIf(salt.utils.platform.is_windows(), "Carbon does not install in Windows")
    def test_46127_pip_env_vars(self):
        '''
        Test that checks if env_vars passed to pip.installed are also passed
        to pip.freeze while checking for existing installations
        '''
        # This issue is most easily checked while installing carbon
        # Much of the code here comes from the test_weird_install function above
        ographite = '/opt/graphite'
        if os.path.isdir(ographite):
            self.skipTest(
                'You already have \'{0}\'. This test would overwrite this '
                'directory'.format(ographite)
            )
        try:
            os.makedirs(ographite)
        except OSError as err:
            if err.errno == errno.EACCES:
                # Permission denied
                self.skipTest(
                    'You don\'t have the required permissions to run this test'
                )
        finally:
            if os.path.isdir(ographite):
                shutil.rmtree(ographite, ignore_errors=True)

        venv_dir = os.path.join(RUNTIME_VARS.TMP, 'issue-46127-pip-env-vars')
        try:
            # We may be able to remove this, I had to add it because the custom
            # modules from the test suite weren't available in the jinja
            # context when running the call to state.sls that comes after.
            self.run_function('saltutil.sync_modules')
            # Since we don't have the virtualenv created, pip.installed will
            # throw an error.
            ret = self.run_function(
                'state.sls', mods='issue-46127-pip-env-vars'
            )
            self.assertSaltTrueReturn(ret)
            for key in six.iterkeys(ret):
                self.assertTrue(ret[key]['result'])
                if ret[key]['name'] != 'carbon < 1.3':
                    continue
                self.assertEqual(
                    ret[key]['comment'],
                    'All packages were successfully installed'
                )
                break
            else:
                raise Exception('Expected state did not run')
            # Run the state again. Now the already installed message should
            # appear
            ret = self.run_function(
                'state.sls', mods='issue-46127-pip-env-vars'
            )
            self.assertSaltTrueReturn(ret)
            # We cannot use assertInSaltComment here because we need to skip
            # some of the state return parts
            for key in six.iterkeys(ret):
                self.assertTrue(ret[key]['result'])
                # As we are re-running the formula, some states will not be run
                # and "name" may or may not be present, so we use .get() pattern
                if ret[key].get('name', '') != 'carbon < 1.3':
                    continue
                self.assertEqual(
                    ret[key]['comment'],
                    ('All packages were successfully installed'))
                break
            else:
                raise Exception('Expected state did not run')
        finally:
            if os.path.isdir(ographite):
                shutil.rmtree(ographite, ignore_errors=True)
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

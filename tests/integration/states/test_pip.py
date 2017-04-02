# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.states.pip
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import errno
import os
import pwd
import glob
import shutil

# Import Salt Testing libs
from tests.support.unit import skipIf
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains,
    with_system_user
)
# Import salt libs
import tests.integration as integration
import salt.utils
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six


@skipIf(salt.utils.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
class PipStateTest(integration.ModuleCase, integration.SaltReturnAssertsMixin):

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

    def test_pip_installed_errors(self):
        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'pip-installed-errors'
        )
        try:
            # Since we don't have the virtualenv created, pip.installed will
            # thrown and error.
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
            ret = self.run_function('virtualenv.create', [venv_dir])
            self.assertEqual(ret['retcode'], 0)

            # The state should not have any issues running now
            ret = self.run_function('state.sls', mods='pip-installed-errors')
            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

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
                shutil.rmtree(ographite)

        venv_dir = os.path.join(integration.TMP, 'pip-installed-weird-install')
        try:
            # We may be able to remove this, I had to add it because the custom
            # modules from the test suite weren't available in the jinja
            # context when running the call to state.sls that comes after.
            self.run_function('saltutil.sync_modules')
            # Since we don't have the virtualenv created, pip.installed will
            # thrown and error.
            ret = self.run_function(
                'state.sls', mods='pip-installed-weird-install'
            )
            self.assertSaltTrueReturn(ret)

            # We cannot use assertInSaltComment here because we need to skip
            # some of the state return parts
            for key in six.iterkeys(ret):
                self.assertTrue(ret[key]['result'])
                if ret[key]['name'] != 'carbon':
                    continue
                self.assertEqual(
                    ret[key]['comment'],
                    'There was no error installing package \'carbon\' '
                    'although it does not show when calling \'pip.freeze\'.'
                )
                break
            else:
                raise Exception('Expected state did not run')
        finally:
            if os.path.isdir('/opt/graphite'):
                shutil.rmtree('/opt/graphite')

    def test_issue_2028_pip_installed_state(self):
        ret = self.run_function('state.sls', mods='issue-2028-pip-installed')

        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'issue-2028-pip-installed'
        )

        try:
            self.assertSaltTrueReturn(ret)
            self.assertTrue(
                os.path.isfile(os.path.join(venv_dir, 'bin', 'pep8'))
            )
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

    def test_issue_2087_missing_pip(self):
        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'issue-2087-missing-pip'
        )

        try:
            # Let's create the testing virtualenv
            ret = self.run_function('virtualenv.create', [venv_dir])
            self.assertEqual(ret['retcode'], 0)

            # Let's remove the pip binary
            pip_bin = os.path.join(venv_dir, 'bin', 'pip')
            if not os.path.isfile(pip_bin):
                self.skipTest(
                    'Failed to find the pip binary to the test virtualenv'
                )
            os.remove(pip_bin)

            # Let's run the state which should fail because pip is missing
            ret = self.run_function('state.sls', mods='issue-2087-missing-pip')
            self.assertSaltFalseReturn(ret)
            self.assertInSaltComment(
                'Error installing \'pep8\': Could not find a `pip` binary',
                ret
            )
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

    def test_issue_5940_multiple_pip_mirrors(self):
        '''
        Test multiple pip mirrors.  This test only works with pip < 7.0.0
        '''
        ret = self.run_function(
            'state.sls', mods='issue-5940-multiple-pip-mirrors'
        )

        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, '5940-multiple-pip-mirrors'
        )

        try:
            self.assertSaltTrueReturn(ret)
            self.assertTrue(
                os.path.isfile(os.path.join(venv_dir, 'bin', 'pep8'))
            )
        except (AssertionError, CommandExecutionError):
            pip_version = self.run_function('pip.version', [venv_dir])
            if salt.utils.compare_versions(ver1=pip_version, oper='>=', ver2='7.0.0'):
                self.skipTest('the --mirrors arg has been deprecated and removed in pip==7.0.0')
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @with_system_user('issue-6912', on_existing='delete', delete=True)
    def test_issue_6912_wrong_owner(self, username):
        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, '6912-wrong-owner'
        )
        # ----- Using runas ------------------------------------------------->
        venv_create = self.run_function(
            'virtualenv.create', [venv_dir], user=username
        )
        if venv_create['retcode'] > 0:
            self.skipTest(
                'Failed to create testcase virtual environment: {0}'.format(
                    venv_create
                )
            )

        # Using the package name.
        try:
            ret = self.run_state(
                'pip.installed', name='pep8', user=username, bin_env=venv_dir
            )
            self.assertSaltTrueReturn(ret)
            uinfo = pwd.getpwnam(username)
            for globmatch in (os.path.join(venv_dir, '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '*', '**', 'pep8*')):
                for path in glob.glob(globmatch):
                    self.assertEqual(
                        uinfo.pw_uid, os.stat(path).st_uid
                    )

        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Using a requirements file
        venv_create = self.run_function(
            'virtualenv.create', [venv_dir], user=username
        )
        if venv_create['retcode'] > 0:
            self.skipTest(
                'Failed to create testcase virtual environment: {0}'.format(
                    ret
                )
            )
        req_filename = os.path.join(
            integration.TMP_STATE_TREE, 'issue-6912-requirements.txt'
        )
        with salt.utils.fopen(req_filename, 'wb') as reqf:
            reqf.write(six.b('pep8'))

        try:
            ret = self.run_state(
                'pip.installed', name='', user=username, bin_env=venv_dir,
                requirements='salt://issue-6912-requirements.txt'
            )
            self.assertSaltTrueReturn(ret)
            uinfo = pwd.getpwnam(username)
            for globmatch in (os.path.join(venv_dir, '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '*', '**', 'pep8*')):
                for path in glob.glob(globmatch):
                    self.assertEqual(
                        uinfo.pw_uid, os.stat(path).st_uid
                    )

        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)
            os.unlink(req_filename)
        # <---- Using runas --------------------------------------------------

        # ----- Using user -------------------------------------------------->
        venv_create = self.run_function(
            'virtualenv.create', [venv_dir], user=username
        )
        if venv_create['retcode'] > 0:
            self.skipTest(
                'Failed to create testcase virtual environment: {0}'.format(
                    ret
                )
            )

        # Using the package name
        try:
            ret = self.run_state(
                'pip.installed', name='pep8', user=username, bin_env=venv_dir
            )
            self.assertSaltTrueReturn(ret)
            uinfo = pwd.getpwnam(username)
            for globmatch in (os.path.join(venv_dir, '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '*', '**', 'pep8*')):
                for path in glob.glob(globmatch):
                    self.assertEqual(
                        uinfo.pw_uid, os.stat(path).st_uid
                    )

        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Using a requirements file
        venv_create = self.run_function(
            'virtualenv.create', [venv_dir], user=username
        )
        if venv_create['retcode'] > 0:
            self.skipTest(
                'Failed to create testcase virtual environment: {0}'.format(
                    ret
                )
            )
        req_filename = os.path.join(
            integration.TMP_STATE_TREE, 'issue-6912-requirements.txt'
        )
        with salt.utils.fopen(req_filename, 'wb') as reqf:
            reqf.write(six.b('pep8'))

        try:
            ret = self.run_state(
                'pip.installed', name='', user=username, bin_env=venv_dir,
                requirements='salt://issue-6912-requirements.txt'
            )
            self.assertSaltTrueReturn(ret)
            uinfo = pwd.getpwnam(username)
            for globmatch in (os.path.join(venv_dir, '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '**', 'pep8*'),
                              os.path.join(venv_dir, '*', '*', '**', 'pep8*')):
                for path in glob.glob(globmatch):
                    self.assertEqual(
                        uinfo.pw_uid, os.stat(path).st_uid
                    )

        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)
            os.unlink(req_filename)
        # <---- Using user ---------------------------------------------------

    def test_issue_6833_pip_upgrade_pip(self):
        # Create the testing virtualenv
        venv_dir = os.path.join(
            integration.TMP, '6833-pip-upgrade-pip'
        )
        ret = self.run_function('virtualenv.create', [venv_dir])
        try:
            try:
                self.assertEqual(ret['retcode'], 0)
                self.assertIn(
                    'New python executable',
                    ret['stdout']
                )
            except AssertionError:
                import pprint
                pprint.pprint(ret)
                raise

            # Let's install a fixed version pip over whatever pip was
            # previously installed
            ret = self.run_function(
                'pip.install', ['pip==6.0'], upgrade=True,
                bin_env=venv_dir
            )
            try:
                self.assertEqual(ret['retcode'], 0)
                self.assertIn(
                    'Successfully installed pip',
                    ret['stdout']
                )
            except AssertionError:
                import pprint
                pprint.pprint(ret)
                raise

            # Let's make sure we have pip 6.0 installed
            self.assertEqual(
                self.run_function('pip.list', ['pip'], bin_env=venv_dir),
                {'pip': '6.0'}
            )

            # Now the actual pip upgrade pip test
            ret = self.run_state(
                'pip.installed', name='pip==6.0.7', upgrade=True,
                bin_env=venv_dir
            )
            try:
                self.assertSaltTrueReturn(ret)
                self.assertInSaltReturn(
                    'Installed',
                    ret,
                    ['changes', 'pip==6.0.7']
                )
            except AssertionError:
                import pprint
                pprint.pprint(ret)
                raise
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

    def test_pip_installed_specific_env(self):
        # Create the testing virtualenv
        venv_dir = os.path.join(
            integration.TMP, 'pip-installed-specific-env'
        )

        # Let's write a requirements file
        requirements_file = os.path.join(
            integration.TMP_PRODENV_STATE_TREE, 'prod-env-requirements.txt'
        )
        with salt.utils.fopen(requirements_file, 'wb') as reqf:
            reqf.write(six.b('pep8\n'))

        try:
            self.run_function('virtualenv.create', [venv_dir])

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
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)
            if os.path.isfile(requirements_file):
                os.unlink(requirements_file)

    def test_22359_pip_installed_unless_does_not_trigger_warnings(self):
        # This test case should be moved to a format_call unit test specific to
        # the state internal keywords
        venv_dir = venv_dir = os.path.join(
            integration.TMP, 'pip-installed-unless'
        )
        venv_create = self.run_function('virtualenv.create', [venv_dir])
        if venv_create['retcode'] > 0:
            self.skipTest(
                'Failed to create testcase virtual environment: {0}'.format(
                    venv_create
                )
            )

        try:
            ret = self.run_state(
                'pip.installed', name='pep8', bin_env=venv_dir, unless='/bin/false'
            )
            self.assertSaltTrueReturn(ret)
            self.assertNotIn('warnings', next(six.itervalues(ret)))
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

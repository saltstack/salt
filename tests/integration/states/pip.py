# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.integration.states.pip
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import pwd
import glob
import shutil

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    with_system_account
)
ensure_in_syspath('../../')

# Import salt libs
import integration


class PipStateTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):

    def setUp(self):
        super(PipStateTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['virtualenv'])
        if not ret:
            self.skipTest('virtualenv not installed')

    def test_pip_installed_errors(self):
        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'pip-installed-errors'
        )
        try:
            # Since we don't have the virtualenv created, pip.installed will
            # thrown and error.
            # Example error strings:
            #  * "Error installing 'supervisor': /tmp/pip-installed-errors: not found"
            #  * "Error installing 'supervisor': /bin/sh: 1: /tmp/pip-installed-errors: not found"
            #  * "Error installing 'supervisor': /bin/bash: /tmp/pip-installed-errors: No such file or directory"
            os.environ['SHELL'] = '/bin/sh'
            ret = self.run_function('state.sls', mods='pip-installed-errors')
            self.assertSaltFalseReturn(ret)
            self.assertSaltCommentRegexpMatches(
                ret,
                'Error installing \'supervisor\':(?:.*)'
                '/tmp/pip-installed-errors(?:.*)'
                '([nN]o such file or directory|not found)'
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

    def test_pip_installed_weird_install(self):
        ographite = '/opt/graphite'
        if os.path.isdir(ographite):
            self.skipTest(
                'You already have \'{0}\'. This test would overwrite this '
                'directory'.format(ographite)
            )
        try:
            os.makedirs(ographite)
        except OSError as err:
            if err.errno == 13:
                # Permission denied
                self.skipTest(
                    'You don\'t have the required permissions to run this test'
                )
        finally:
            if os.path.isdir(ographite):
                shutil.rmtree(ographite)

        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'pip-installed-weird-install'
        )
        try:
            # Since we don't have the virtualenv created, pip.installed will
            # thrown and error.
            ret = self.run_function(
                'state.sls', mods='pip-installed-weird-install'
            )
            self.assertSaltTrueReturn(ret)

            # We cannot use assertInSaltComment here because we need to skip
            # some of the state return parts
            for key in ret.keys():
                self.assertTrue(ret[key]['result'])
                if ret[key]['comment'] == 'Created new virtualenv':
                    continue
                self.assertEqual(
                    ret[key]['comment'],
                    'There was no error installing package \'carbon\' '
                    'although it does not show when calling \'pip.freeze\'.'
                )
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)
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
                os.path.isfile(os.path.join(venv_dir, 'bin', 'supervisord'))
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
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @with_system_account('issue-6912', on_existing='delete', delete=True)
    def test_issue_6912_wrong_owner(self, username):
        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, '6912-wrong-owner'
        )
        # ----- Using runas ------------------------------------------------->
        venv_create = self.run_function(
            'virtualenv.create', [venv_dir], runas=username
        )
        if venv_create['retcode'] > 0:
            self.skipTest(
                'Failed to create testcase virtual environment: {0}'.format(
                    ret
                )
            )

        # Using the package name.
        try:
            ret = self.run_state(
                'pip.installed', name='pep8', runas=username, bin_env=venv_dir
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
            'virtualenv.create', [venv_dir], runas=username
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
        with open(req_filename, 'wb') as f:
            f.write('pep8')

        try:
            ret = self.run_state(
                'pip.installed', name='', runas=username, bin_env=venv_dir,
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
            'virtualenv.create', [venv_dir], runas=username
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
            'virtualenv.create', [venv_dir], runas=username
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
        with open(req_filename, 'wb') as f:
            f.write('pep8')

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
                'pip.install', ['pip==1.3.1'], upgrade=True,
                ignore_installed=True,
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

            # Le't make sure we have pip 1.3.1 installed
            self.assertEqual(
                self.run_function('pip.list', ['pip'], bin_env=venv_dir),
                {'pip': '1.3.1'}
            )

            # Now the actual pip upgrade pip test
            ret = self.run_state(
                'pip.installed', name='pip==1.4.1', upgrade=True,
                bin_env=venv_dir
            )
            try:
                self.assertSaltTrueReturn(ret)
                self.assertInSaltReturn(
                    'Installed',
                    ret,
                    ['changes', 'pip==1.4.1']
                )
            except AssertionError:
                import pprint
                pprint.pprint(ret)
                raise
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PipStateTest)

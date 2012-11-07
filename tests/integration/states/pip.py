# -*- coding: utf-8 -*-
'''
    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details
'''

# Import python libs
import os
import shutil

# Import salt libs
import integration


class PipStateTest(integration.ModuleCase):

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
            ret = self.run_function('state.sls', mods='pip-installed-errors')
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})

            for key in ret.keys():
                self.assertFalse(ret[key]['result'])
                self.assertRegexpMatches(
                    ret[key]['comment'],
                    'Error installing \'supervisor\': .* '
                    '[nN]o such file or directory'
                )

            # We now create the missing virtualenv
            ret = self.run_function('virtualenv.create', [venv_dir])
            self.assertEqual(ret['retcode'], 0)

            # The state should not have any issues running now
            ret = self.run_function('state.sls', mods='pip-installed-errors')
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})

            for key in ret.keys():
                self.assertTrue(ret[key]['result'])
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
        except OSError, err:
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
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})

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

    def test_issue_2087_missing_pip(self):
        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'issue-2087-missing-pip'
        )

        try:
            # XXX: Once state.template_str is fixed, consider not using a file
            # for this test.

            # Let's create the testing virtualenv
            self.run_function('virtualenv.create', [venv_dir])

            # Let's remove the pip binary
            pip_bin = os.path.join(venv_dir, 'bin', 'pip')
            if not os.path.isfile(pip_bin):
                self.skipTest(
                    'Failed to find the pip binary to the test virtualenv'
                )
            os.remove(pip_bin)

            # Let's run the state which should fail because pip is missing
            ret = self.run_function('state.sls', mods='issue-2087-missing-pip')
            self.assertFalse(ret.values()[0]['result'])
            self.assertEqual(
                ret.values()[0]['comment'],
                'Error installing \'pep8\': Could not find a `pip` binary'
            )
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

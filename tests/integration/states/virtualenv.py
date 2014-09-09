# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.states.virtualenv
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import shutil

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import destructiveTest, ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES


@skipIf(salt.utils.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
class VirtualenvTest(integration.ModuleCase,
                     integration.SaltReturnAssertsMixIn):
    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_issue_1959_virtualenv_runas(self):
        user = 'issue-1959'
        if not self.run_function('user.add', [user]):
            # Left behind on a canceled test run?
            self.run_function('user.delete', [user, True, True])
            if not self.run_function('user.add', [user]):
                self.skipTest('Failed to create the \'{0}\' user'.format(user))

        uinfo = self.run_function('user.info', [user])

        venv_dir = os.path.join(
            integration.SYS_TMP_DIR, 'issue-1959-virtualenv-runas'
        )
        try:
            ret = self.run_function(
                'state.sls', mods='issue-1959-virtualenv-runas'
            )
            self.assertSaltTrueReturn(ret)

            # Lets check proper ownership
            statinfo = self.run_function('file.stats', [venv_dir])
            self.assertEqual(statinfo['user'], uinfo['name'])
            self.assertEqual(statinfo['uid'], uinfo['uid'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)
            self.run_function('user.delete', [user, True, True])

    def test_issue_2594_non_invalidated_cache(self):
        # Testing virtualenv directory
        venv_path = os.path.join(integration.TMP, 'issue-2594-ve')
        if os.path.exists(venv_path):
            shutil.rmtree(venv_path)
        # Our virtualenv requirements file
        requirements_file_path = os.path.join(
            integration.TMP_STATE_TREE, 'issue-2594-requirements.txt'
        )
        if os.path.exists(requirements_file_path):
            os.unlink(requirements_file_path)

        # Our state template
        template = [
            '{0}:'.format(venv_path),
            '  virtualenv.managed:',
            '    - system_site_packages: False',
            '    - clear: false',
            '    - requirements: salt://issue-2594-requirements.txt',
        ]

        # Let's populate the requirements file, just pep-8 for now
        open(requirements_file_path, 'a').write('pep8==1.3.3\n')

        # Let's run our state!!!
        try:
            ret = self.run_function(
                'state.template_str', ['\n'.join(template)]
            )

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment('Created new virtualenv', ret)
            self.assertSaltStateChangesEqual(
                ret, ['pep8==1.3.3'], keys=('packages', 'new')
            )
        except AssertionError:
            # Always clean up the tests temp files
            if os.path.exists(venv_path):
                shutil.rmtree(venv_path)
            if os.path.exists(requirements_file_path):
                os.unlink(requirements_file_path)
            raise

        # Let's make sure, it really got installed
        ret = self.run_function('pip.freeze', bin_env=venv_path)
        self.assertIn('pep8==1.3.3', ret)
        self.assertNotIn('zope.interface==4.0.1', ret)

        # Now let's update the requirements file, which is now cached.
        open(requirements_file_path, 'w').write('zope.interface==4.0.1\n')

        # Let's run our state!!!
        try:
            ret = self.run_function(
                'state.template_str', ['\n'.join(template)]
            )

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment('virtualenv exists', ret)
            self.assertSaltStateChangesEqual(
                ret, ['zope.interface==4.0.1'], keys=('packages', 'new')
            )
        except AssertionError:
            # Always clean up the tests temp files
            if os.path.exists(venv_path):
                shutil.rmtree(venv_path)
            if os.path.exists(requirements_file_path):
                os.unlink(requirements_file_path)
            raise

        # Let's make sure, it really got installed
        ret = self.run_function('pip.freeze', bin_env=venv_path)
        self.assertIn('pep8==1.3.3', ret)
        self.assertIn('zope.interface==4.0.1', ret)

        # If we reached this point no assertion failed, so, cleanup!
        if os.path.exists(venv_path):
            shutil.rmtree(venv_path)
        if os.path.exists(requirements_file_path):
            os.unlink(requirements_file_path)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtualenvTest)

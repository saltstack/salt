# -*- coding: utf-8 -*-

'''
Tests for the salt-run command
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.integration.utils import testprogram
from tests.support.case import ShellCase
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.support.helpers import skip_if_not_root

# Import Salt libs
import salt.utils.files
import salt.utils.platform
import salt.utils.yaml


USERA = 'saltdev'
USERA_PWD = 'saltdev'
HASHED_USERA_PWD = '$6$SALTsalt$ZZFD90fKFWq8AGmmX0L3uBtS9fXL62SrTk5zcnQ6EkD6zoiM3kB88G1Zvs0xm/gZ7WXJRs5nsTBybUvGSqZkT.'


class RunTest(ShellCase, testprogram.TestProgramCase, ShellCaseCommonTestsMixin):
    '''
    Test the salt-run command
    '''

    _call_binary_ = 'salt-run'

    def _add_user(self):
        '''
        helper method to add user
        '''
        try:
            add_user = self.run_call('user.add {0} createhome=False'.format(USERA))
            add_pwd = self.run_call('shadow.set_password {0} \'{1}\''.format(USERA,
                                    USERA_PWD if salt.utils.platform.is_darwin() else HASHED_USERA_PWD))
            self.assertTrue(add_user)
            self.assertTrue(add_pwd)
            user_list = self.run_call('user.list_users')
            self.assertIn(USERA, str(user_list))
        except AssertionError:
            self.run_call('user.delete {0} remove=True'.format(USERA))
            self.skipTest(
                'Could not add user or password, skipping test'
                )

    def _remove_user(self):
        '''
        helper method to remove user
        '''
        user_list = self.run_call('user.list_users')
        for user in user_list:
            if USERA in user:
                self.run_call('user.delete {0} remove=True'.format(USERA))

    def test_in_docs(self):
        '''
        test the salt-run docs system
        '''
        data = self.run_run('-d')
        data = '\n'.join(data)
        self.assertIn('jobs.active:', data)
        self.assertIn('jobs.list_jobs:', data)
        self.assertIn('jobs.lookup_jid:', data)
        self.assertIn('manage.down:', data)
        self.assertIn('manage.up:', data)
        self.assertIn('network.wol:', data)
        self.assertIn('network.wollist:', data)

    def test_notin_docs(self):
        '''
        Verify that hidden methods are not in run docs
        '''
        data = self.run_run('-d')
        data = '\n'.join(data)
        self.assertNotIn('jobs.SaltException:', data)

    # pylint: disable=invalid-name
    def test_salt_documentation_too_many_arguments(self):
        '''
        Test to see if passing additional arguments shows an error
        '''
        data = self.run_run('-d virt.list foo', catch_stderr=True)
        self.assertIn('You can only get documentation for one method at one time', '\n'.join(data[1]))

    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-run.
        '''

        runner = testprogram.TestProgramSaltRun(
            name='run-unknown_argument',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        runner.setup()
        stdout, stderr, status = runner.run(
            args=['--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_USAGE',
            message='unknown argument',
            stdout=stdout, stderr=stderr
        )
        # runner.shutdown() should be unnecessary since the start-up should fail

    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-run starts correctly.
        '''

        runner = testprogram.TestProgramSaltRun(
            name='run-correct_usage',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        runner.setup()
        stdout, stderr, status = runner.run(
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_OK',
            message='correct usage',
            stdout=stdout, stderr=stderr
        )

    @skip_if_not_root
    def test_salt_run_with_eauth_all_args(self):
        '''
        test salt-run with eauth
        tests all eauth args
        '''
        args = ['--auth', '--eauth', '--external-auth', '-a']
        self._add_user()
        for arg in args:
            run_cmd = self.run_run('{0} pam --username {1} --password {2}\
                                   test.arg arg kwarg=kwarg1'.format(arg, USERA, USERA_PWD))
            expect = ['args:', '    - arg', 'kwargs:', '    ----------', '    kwarg:', '        kwarg1']
            self.assertEqual(expect, run_cmd)
        self._remove_user()

    @skip_if_not_root
    def test_salt_run_with_eauth_bad_passwd(self):
        '''
        test salt-run with eauth and bad password
        '''
        self._add_user()
        run_cmd = self.run_run('-a pam --username {0} --password wrongpassword\
                               test.arg arg kwarg=kwarg1'.format(USERA))
        expect = ['Authentication failure of type "eauth" occurred for user saltdev.']
        self.assertEqual(expect, run_cmd)
        self._remove_user()

    def test_salt_run_with_wrong_eauth(self):
        '''
        test salt-run with wrong eauth parameter
        '''
        run_cmd = self.run_run('-a wrongeauth --username {0} --password {1}\
                               test.arg arg kwarg=kwarg1'.format(USERA, USERA_PWD))
        expect = r"^The specified external authentication system \"wrongeauth\" is not available\tAvailable eauth types: auto, .*"
        self.assertRegex("\t".join(run_cmd), expect)

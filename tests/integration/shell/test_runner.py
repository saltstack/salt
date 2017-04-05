# -*- coding: utf-8 -*-

'''
Tests for the salt-run command
'''

# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.integration.utils import testprogram
from tests.support.case import ShellCase
from tests.support.paths import TMP
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.support.helpers import skip_if_not_root

# Import 3rd-party libs
import yaml

# Import salt libs
import salt.utils

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
                                    USERA_PWD if salt.utils.is_darwin() else HASHED_USERA_PWD))
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

    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        config_file_name = 'master'
        with salt.utils.fopen(self.get_config_file_path(config_file_name), 'r') as fhr:
            config = yaml.load(fhr.read())
            config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
            with salt.utils.fopen(os.path.join(config_dir, config_file_name), 'w') as fhw:
                fhw.write(
                    yaml.dump(config, default_flow_style=False)
                )
        ret = self.run_script(
            self._call_binary_,
            '--config-dir {0} -d'.format(
                config_dir
            ),
            timeout=60,
            catch_stderr=True,
            with_retcode=True
        )
        try:
            self.assertIn("'doc.runner:'", ret[0])
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        except AssertionError:
            if os.path.exists('/dev/log') and ret[2] != 2:
                # If there's a syslog device and the exit code was not 2,
                # 'No such file or directory', raise the error
                raise
            self.assertIn(
                'Failed to setup the Syslog logging handler',
                '\n'.join(ret[1])
            )
            self.assertEqual(ret[2], 2)
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)

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
        expect = ['The specified external authentication system "wrongeauth" is not available']
        self.assertEqual(expect, run_cmd)

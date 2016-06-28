# -*- coding: utf-8 -*-

'''
Tests for the salt-run command
'''

# Import python libs
from __future__ import absolute_import
import os
import yaml
import shutil

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
from integration.utils import testprogram
import salt.utils


class RunTest(integration.ShellCase, testprogram.TestProgramCase, integration.ShellCaseCommonTestsMixIn):
    '''
    Test the salt-run command
    '''

    _call_binary_ = 'salt-run'

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
        config_dir = os.path.join(integration.TMP, 'issue-7754')
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
            timeout=15,
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


if __name__ == '__main__':
    integration.run_tests(RunTest)

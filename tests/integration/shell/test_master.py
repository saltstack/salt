# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.shell.master
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import signal
import shutil

# Import salt libs
import salt.utils.files
import salt.utils.yaml

# Import salt test libs
import tests.integration.utils
from tests.support.case import ShellCase
from tests.support.paths import TMP
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.integration.utils import testprogram


class MasterTest(ShellCase, testprogram.TestProgramCase, ShellCaseCommonTestsMixin):

    _call_binary_ = 'salt-master'

    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        config_file_name = 'master'
        pid_path = os.path.join(config_dir, '{0}.pid'.format(config_file_name))
        with salt.utils.files.fopen(self.get_config_file_path(config_file_name), 'r') as fhr:
            config = salt.utils.yaml.safe_load(fhr)
            config['root_dir'] = config_dir
            config['log_file'] = 'file:///tmp/log/LOG_LOCAL3'
            config['ret_port'] = config['ret_port'] + 10
            config['publish_port'] = config['publish_port'] + 10

            with salt.utils.files.fopen(os.path.join(config_dir, config_file_name), 'w') as fhw:
                salt.utils.yaml.safe_dump(config, fhw, default_flow_style=False)

        ret = self.run_script(
            self._call_binary_,
            '--config-dir {0} --pid-file {1} -l debug'.format(
                config_dir,
                pid_path
            ),
            timeout=5,
            catch_stderr=True,
            with_retcode=True
        )

        # Now kill it if still running
        if os.path.exists(pid_path):
            with salt.utils.files.fopen(pid_path) as fhr:
                try:
                    os.kill(int(fhr.read()), signal.SIGKILL)
                except OSError:
                    pass
        try:
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)

    def test_exit_status_unknown_user(self):
        '''
        Ensure correct exit status when the master is configured to run as an unknown user.
        '''

        master = testprogram.TestDaemonSaltMaster(
            name='unknown_user',
            configs={'master': {'map': {'user': 'some_unknown_user_xyz'}}},
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        master.setup()
        stdout, stderr, status = master.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_NOUSER',
                message='unknown user not on system',
                stdout=stdout,
                stderr=tests.integration.utils.decode_byte_list(stderr)
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exeptions and respective traceback
            master.shutdown()

    # pylint: disable=invalid-name
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-master.
        '''

        master = testprogram.TestDaemonSaltMaster(
            name='unknown_argument',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        master.setup()
        stdout, stderr, status = master.run(
            args=['-d', '--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_USAGE',
                message='unknown argument',
                stdout=stdout,
                stderr=tests.integration.utils.decode_byte_list(stderr)
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exeptions and respective traceback
            master.shutdown()

    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-master starts correctly.
        '''

        master = testprogram.TestDaemonSaltMaster(
            name='correct_usage',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        master.setup()
        stdout, stderr, status = master.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_OK',
                message='correct usage',
                stdout=stdout,
                stderr=tests.integration.utils.decode_byte_list(stderr)
            )
        finally:
            master.shutdown(wait_for_orphans=3)

        # Do the test again to check does master shut down correctly
        # **Due to some underlying subprocessing issues with Minion._thread_return, this
        # part of the test has been commented out. Once these underlying issues have
        # been addressed, this part of the test should be uncommented. Work for this
        # issue is being tracked in https://github.com/saltstack/salt-jenkins/issues/378
        # stdout, stderr, status = master.run(
        #     args=['-d'],
        #     catch_stderr=True,
        #     with_retcode=True,
        # )
        # try:
        #     self.assert_exit_status(
        #         status, 'EX_OK',
        #         message='correct usage',
        #         stdout=stdout,
        #         stderr=tests.integration.utils.decode_byte_list(stderr)
        #     )
        # finally:
        #     master.shutdown(wait_for_orphans=3)

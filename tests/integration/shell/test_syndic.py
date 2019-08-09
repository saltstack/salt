# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.syndic
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import shutil
import logging
from collections import OrderedDict

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ShellCase
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.support.unit import skipIf, WAR_ROOM_SKIP
from tests.integration.utils import testprogram

# Import salt libs
import salt.utils.files
import salt.utils.yaml
import salt.utils.platform

# Import 3rd-party libs
import psutil
import pytest

log = logging.getLogger(__name__)

SIGKILL = 9


@pytest.fixture(scope='module', autouse=True)
def session_salt_syndic(request, session_salt_master_of_masters, session_salt_syndic):
    request.session.stats_processes.update(OrderedDict((
        ('Salt Syndic Master', psutil.Process(session_salt_master_of_masters.pid)),
        ('       Salt Syndic', psutil.Process(session_salt_syndic.pid)),
    )).items())
    yield session_salt_syndic
    request.session.stats_processes.pop('Salt Syndic Master')
    request.session.stats_processes.pop('       Salt Syndic')

    # Stop daemons now(they would be stopped at the end of the test run session
    for daemon in (session_salt_syndic, session_salt_master_of_masters):
        try:
            daemon.terminate()
        except Exception as exc:  # pylint: disable=broad-except
            log.warning('Failed to terminate daemon: %s', daemon.__class__.__name__)


@skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
class SyndicTest(ShellCase, testprogram.TestProgramCase, ShellCaseCommonTestsMixin):
    '''
    Test the salt-syndic command
    '''

    _call_binary_ = 'salt-syndic'

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(RUNTIME_VARS.TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        for fname in ('master', 'minion'):
            pid_path = os.path.join(config_dir, '{0}.pid'.format(fname))
            with salt.utils.files.fopen(self.get_config_file_path(fname), 'r') as fhr:
                config = salt.utils.yaml.safe_load(fhr)
                config['log_file'] = config['syndic_log_file'] = 'file:///tmp/log/LOG_LOCAL3'
                config['root_dir'] = config_dir
                if 'ret_port' in config:
                    config['ret_port'] = int(config['ret_port']) + 10
                    config['publish_port'] = int(config['publish_port']) + 10

                with salt.utils.files.fopen(os.path.join(config_dir, fname), 'w') as fhw:
                    salt.utils.yaml.safe_dump(config, fhw, default_flow_style=False)

        self.run_script(
            self._call_binary_,
            '--config-dir={0} --pid-file={1} -l debug'.format(
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
                    os.kill(int(fhr.read()), SIGKILL)
                except OSError:
                    pass
        try:
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)

    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows OS')
    def test_exit_status_unknown_user(self):
        '''
        Ensure correct exit status when the syndic is configured to run as an unknown user.

        Skipped on windows because daemonization not supported
        '''

        syndic = testprogram.TestDaemonSaltSyndic(
            name='unknown_user',
            config_base={'user': 'some_unknown_user_xyz'},
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        syndic.setup()
        stdout, stderr, status = syndic.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_NOUSER',
                message='unknown user not on system',
                stdout=stdout, stderr=stderr
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exceptions and respective traceback
            syndic.shutdown()

    # pylint: disable=invalid-name
    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows OS')
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-syndic.

        Skipped on windows because daemonization not supported
        '''

        syndic = testprogram.TestDaemonSaltSyndic(
            name='unknown_argument',
            parent_dir=self._test_dir,
        )
        # Syndic setup here to ensure config and script exist
        syndic.setup()
        stdout, stderr, status = syndic.run(
            args=['-d', '--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_USAGE',
                message='unknown argument',
                stdout=stdout, stderr=stderr
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exceptions and respective traceback
            syndic.shutdown()

    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows OS')
    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-syndic starts correctly.

        Skipped on windows because daemonization not supported
        '''

        syndic = testprogram.TestDaemonSaltSyndic(
            name='correct_usage',
            parent_dir=self._test_dir,
        )
        # Syndic setup here to ensure config and script exist
        syndic.setup()
        stdout, stderr, status = syndic.run(
            args=['-d', '-l', 'debug'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_OK',
                message='correct usage',
                stdout=stdout, stderr=stderr
            )
        finally:
            syndic.shutdown(wait_for_orphans=3)

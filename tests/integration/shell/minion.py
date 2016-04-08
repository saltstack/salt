# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.shell.minion
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import sys
import getpass
import platform
import yaml
import signal
import shutil
import tempfile
import logging

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
from integration.utils import testprogram
import salt.utils
import salt.defaults.exitcodes

log = logging.getLogger(__name__)

DEBUG = False


class MinionTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):
    '''
    Various integration tests for the salt-minion executable.
    '''
    _call_binary_ = 'salt-minion'
    _test_dir = None

    _test_minions = (
        'minion',
        'subminion',
    )

    def setUp(self):
        # Setup for scripts
        self._test_dir = tempfile.mkdtemp(prefix='salt-testdaemon-')

    def tearDown(self):
        # shutdown for scripts
        if self._test_dir and os.path.sep == self._test_dir[0]:
            shutil.rmtree(self._test_dir)
            self._test_dir = None

    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(integration.TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        config_file_name = 'minion'
        pid_path = os.path.join(config_dir, '{0}.pid'.format(config_file_name))
        with salt.utils.fopen(self.get_config_file_path(config_file_name), 'r') as fhr:
            config = yaml.load(fhr.read())
            config['log_file'] = 'file:///tmp/log/LOG_LOCAL3'

            with salt.utils.fopen(os.path.join(config_dir, config_file_name), 'w') as fhw:
                fhw.write(
                    yaml.dump(config, default_flow_style=False)
                )

        ret = self.run_script(
            self._call_binary_,
            '--disable-keepalive --config-dir {0} --pid-file {1} -l debug'.format(
                config_dir,
                pid_path
            ),
            timeout=5,
            catch_stderr=True,
            with_retcode=True
        )

        # Now kill it if still running
        if os.path.exists(pid_path):
            with salt.utils.fopen(pid_path) as fhr:
                try:
                    os.kill(int(fhr.read()), signal.SIGKILL)
                except OSError:
                    pass
        try:
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
            self.assertIn(
                'Failed to setup the Syslog logging handler', '\n'.join(ret[1])
            )
            self.assertEqual(ret[2], 2)
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)

    def _run_initscript(
        self,
        init_script,
        minions,
        minion_running,
        action,
        exitstatus=None,
        message=''
    ):
        '''
        Wrapper that runs the initscript for the configured minions and
        verifies the results.
        '''
        ret = init_script.run(
            [action],
            catch_stderr=True,
            with_retcode=True,
            timeout=45,
        )

        # Check minion state
        for minion in minions:
            self.assertEqual(
                minion.is_running(),
                minion_running,
                'Minion "{0}" must be {1} and is not.'.format(minion.name, ["stopped", "running"][minion_running])
            )

        for line in ret[0]:
            log.debug('script: salt-minion: stdout: {0}'.format(line))
        for line in ret[1]:
            log.debug('script: salt-minion: stderr: {0}'.format(line))
        if exitstatus is not None:
            self.assertEqual(
                ret[2],
                exitstatus,
                'script action "{0}" {1} exited {2}, must be {3}'.format(action, message, ret[2], exitstatus)
            )
        return ret

    def test_linux_initscript(self):
        '''
        Various tests of the init script to verify that it properly controls a salt minion.
        '''

        pform = platform.uname()[0].lower()
        if pform not in ('linux',):
            self.skipTest('salt-minion init script is unavailable on {1}'.format(platform))

        user = getpass.getuser()

        minions = []
        for mname in self._test_minions:
            minion = testprogram.TestDaemonSaltMinion(
                name=mname,
                config={'user': user},
                parent_dir=self._test_dir,
            )
            # Call setup here to ensure config and script exist
            minion.setup()
            minions.append(minion)

        # Need salt-call, salt-minion for wrapper script
        salt_call = testprogram.TestProgramSaltCall(parent_dir=self._test_dir)
        # Ensure that run-time files are generated
        salt_call.setup()
        cmd_env = {
            'PATH': ':'.join([salt_call.script_dir, os.getenv('PATH')]),
            'SALTMINION_DEBUG': '1' if DEBUG else '',
            'SALTMINION_PYTHON': sys.executable,
            'SALTMINION_SYSCONFDIR': minions[0].root_dir,
            'SALTMINION_BINDIR': minions[0].script_dir,
            'SALTMINION_CONFIGS': '\n'.join([
                '{0} {1}'.format(user, minion.config_dir) for minion in minions
            ]),
        }

        init_script = testprogram.TestProgram(
            name='init:salt-minion',
            program=os.path.join(integration.CODE_DIR, 'pkg', 'rpm', 'salt-minion'),
            env=cmd_env,
        )

        try:
            # I take visual readability with aligned columns over strict PEP8
            # (bad-whitespace) Exactly one space required after comma
            # pylint: disable=C0326
            ret = self._run_initscript(init_script, minions, False, 'bogusaction', 2)
            ret = self._run_initscript(init_script, minions, False, 'reload',      3)  # Not implemented
            ret = self._run_initscript(init_script, minions, False, 'stop',        0, 'when not running')
            ret = self._run_initscript(init_script, minions, False, 'status',      3, 'when not running')
            ret = self._run_initscript(init_script, minions, False, 'condrestart', 7, 'when not running')
            ret = self._run_initscript(init_script, minions, False, 'try-restart', 7, 'when not running')
            ret = self._run_initscript(init_script, minions, True,  'start',       0, 'when not running')

            ret = self._run_initscript(init_script, minions, True,  'status',      0, 'when running')
            # Verify that PIDs match
            for (minion, stdout) in zip(minions, ret[0]):
                status_pid = int(stdout.rsplit(' ', 1)[-1])
                self.assertEqual(
                    status_pid,
                    minion.daemon_pid,
                    'PID in "{0}" is {1} and does not match status PID {2}'.format(
                        minion.pid_path,
                        minion.daemon_pid,
                        status_pid
                    )
                )

            ret = self._run_initscript(init_script, minions, True,  'start',       0, 'when running')
            ret = self._run_initscript(init_script, minions, True,  'condrestart', 0, 'when running')
            ret = self._run_initscript(init_script, minions, True,  'try-restart', 0, 'when running')
            ret = self._run_initscript(init_script, minions, False, 'stop',        0, 'when running')

        finally:
            # Ensure that minions are shutdown
            for minion in minions:
                minion.shutdown()


if __name__ == '__main__':
    integration.run_tests(MinionTest)

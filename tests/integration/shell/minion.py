# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.shell.minion
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import getpass
import os
import sys
import platform
import yaml
import signal
import shutil
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

DEBUG = True


class MinionTest(integration.ShellCase, testprogram.TestProgramCase, integration.ShellCaseCommonTestsMixIn):
    '''
    Various integration tests for the salt-minion executable.
    '''
    _call_binary_ = 'salt-minion'

    _test_minions = (
        'minion',
        'subminion',
    )

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
            timeout=90,
        )

        # Check minion state
        for minion in minions:
            self.assertEqual(
                minion.is_running(),
                minion_running,
                'Minion "{0}" must be {1} and is not.\nSTDOUT:{2}\nSTDERR:{3}'.format(
                    minion.name,
                    ["stopped", "running"][minion_running],
                    '\nSTDOUT:'.join(ret[0]),
                    '\nSTDERR:'.join(ret[1]),
                )
            )

        for line in ret[0]:
            log.debug('script: salt-minion: stdout: {0}'.format(line))
        for line in ret[1]:
            log.debug('script: salt-minion: stderr: {0}'.format(line))

        if exitstatus is not None:
            self.assertEqual(
                ret[2],
                exitstatus,
                'script action "{0}" {1} exited {2}, must be {3}\nSTDOUT:{4}\nSTDERR:{5}'.format(
                    action,
                    message,
                    ret[2],
                    exitstatus,
                    '\nSTDOUT:'.join(ret[0]),
                    '\nSTDERR:'.join(ret[1]),
                )
            )
        return ret

    def _initscript_setup(self, minions):
        '''Re-usable setup for running salt-minion tests'''
        user = getpass.getuser()

        _minions = []
        for mname in minions:
            minion = testprogram.TestDaemonSaltMinion(
                name=mname,
                parent_dir=self._test_dir,
            )
            # Call setup here to ensure config and script exist
            minion.setup()
            _minions.append(minion)

        # Need salt-call, salt-minion for wrapper script
        salt_call = testprogram.TestProgramSaltCall(parent_dir=self._test_dir)
        # Ensure that run-time files are generated
        salt_call.setup()
        sysconf_dir = os.path.dirname(_minions[0].config_dir)
        cmd_env = {
            'PATH': ':'.join([salt_call.script_dir, os.getenv('PATH')]),
            'SALTMINION_DEBUG': '1' if DEBUG else '',
            'SALTMINION_PYTHON': sys.executable,
            'SALTMINION_SYSCONFDIR': sysconf_dir,
            'SALTMINION_BINDIR': _minions[0].script_dir,
            'SALTMINION_CONFIGS': '\n'.join([
                '{0} {1}'.format(user, minion.config_dir) for minion in _minions
            ]),
        }

        default_dir = os.path.join(sysconf_dir, 'default')
        if not os.path.exists(default_dir):
            os.makedirs(default_dir)
        with open(os.path.join(default_dir, 'salt'), 'w') as defaults:
            # Test suites is quite slow - extend the timeout
            defaults.write(
                'TIMEOUT=60\n'
                'TICK=1\n'
            )

        init_script = testprogram.TestProgram(
            name='init:salt-minion',
            program=os.path.join(integration.CODE_DIR, 'pkg', 'rpm', 'salt-minion'),
            env=cmd_env,
        )

        return _minions, salt_call, init_script

    def test_linux_initscript(self):
        '''
        Various tests of the init script to verify that it properly controls a salt minion.
        '''

        pform = platform.uname()[0].lower()
        if pform not in ('linux',):
            self.skipTest('salt-minion init script is unavailable on {1}'.format(platform))

        minions, _, init_script = self._initscript_setup(self._test_minions[:1])

        try:
            # These tests are grouped together, rather than split into individual test functions,
            # because subsequent tests leverage the state from the previous test which minimizes
            # setup for each test.

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

    def test_exit_status_unknown_user(self):
        '''
        Ensure correct exit status when the minion is configured to run as an unknown user.
        '''

        minion = testprogram.TestDaemonSaltMinion(
            name='unknown_user',
            config={'user': 'unknown'},
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        minion.setup()
        stdout, stderr, status = minion.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_NOUSER',
            message='unknown user not on system',
            stdout=stdout, stderr=stderr
        )
        # minion.shutdown() should be unnecessary since the start-up should fail

    # pylint: disable=invalid-name
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-minion.
        '''

        minion = testprogram.TestDaemonSaltMinion(
            name='unknown_argument',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        minion.setup()
        stdout, stderr, status = minion.run(
            args=['-d', '--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_USAGE',
            message='unknown argument',
            stdout=stdout, stderr=stderr
        )
        # minion.shutdown() should be unnecessary since the start-up should fail

    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-minion starts correctly.
        '''

        minion = testprogram.TestDaemonSaltMinion(
            name='correct_usage',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        minion.setup()
        stdout, stderr, status = minion.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_OK',
            message='correct usage',
            stdout=stdout, stderr=stderr
        )
        minion.shutdown()


if __name__ == '__main__':
    integration.run_tests(MinionTest)

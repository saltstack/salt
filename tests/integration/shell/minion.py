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
import logging

# Import Salt Testing libs
from salttesting.runtests import RUNTIME_VARS
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
import salt.defaults.exitcodes

log = logging.getLogger(__name__)

DEBUG = False
#DEBUG = True


class MinionTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-minion'

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


    def _run_linux_initscript_action(self, cmdv, action, cmd_env, exitstatus=None, message=''):
        ret = self.run_prog(
            cmdv + [action],
            catch_stderr=True,
            with_retcode=True,
            timeout=45,
            env=cmd_env,
        )
        for line in ret[0]:
            log.info('TLH: salt-minion: stdout: {0}'.format(line))
        for line in ret[1]:
            log.info('TLH: salt-minion: stderr: {0}'.format(line))
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

        # Need salt-call, salt-minion for wrapper script
        for script in ('salt-call', 'salt-minion'):
            salt_script_path = self.get_script_path(script)
            if not os.path.isfile(salt_script_path):
                log.error('Unable to find {0} script'.format(script))
                return False

        sysconfdir = os.path.join(RUNTIME_VARS.TMP, 'config')
        cmd_env = {
            'SALTMINION_DEBUG': '1' if DEBUG else '',
            'SALTMINION_PYTHON': sys.executable,
            'SALTMINION_SYSCONFDIR': sysconfdir,
            'SALTMINION_BINDIR': RUNTIME_VARS.TMP_SCRIPT_DIR,
            'SALTMINION_CONFIGS': '{0} {1}'.format(getpass.getuser(), sysconfdir),
        }
        cmdv = [
            os.path.join(integration.CODE_DIR, 'pkg', 'rpm', 'salt-minion'),
        ]

        # Initially guarantee that a salt minion is not running.
        self._run_linux_initscript_action(cmdv, 'stop',        cmd_env, None)

        self._run_linux_initscript_action(cmdv, 'bogusaction', cmd_env, 2)
        self._run_linux_initscript_action(cmdv, 'reload',      cmd_env, 3) # May be added in the future
        self._run_linux_initscript_action(cmdv, 'stop',        cmd_env, 0, 'when not running')
        self._run_linux_initscript_action(cmdv, 'status',      cmd_env, 3, 'when not running')
        self._run_linux_initscript_action(cmdv, 'condrestart', cmd_env, 7, 'when not running')
        self._run_linux_initscript_action(cmdv, 'try-restart', cmd_env, 7, 'when not running')
        self._run_linux_initscript_action(cmdv, 'start',       cmd_env, 0, 'when not running')
        self._run_linux_initscript_action(cmdv, 'status',      cmd_env, 0, 'when running')
        self._run_linux_initscript_action(cmdv, 'start',       cmd_env, 0, 'when running')
        self._run_linux_initscript_action(cmdv, 'condrestart', cmd_env, 0, 'when running')
        self._run_linux_initscript_action(cmdv, 'try-restart', cmd_env, 0, 'when running')
        self._run_linux_initscript_action(cmdv, 'stop',        cmd_env, 0, 'when running')

        # Leave a minion running for other tests
        self._run_linux_initscript_action(cmdv, 'start',       cmd_env, 0, '')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MinionTest)

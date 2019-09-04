# -*- coding: utf-8 -*-
'''
    :copyright: Copyright 2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.processes
    ~~~~~~~~~~~~~~~~~~~~~~~

    Process handling utilities
'''

# Import python libs
from __future__ import absolute_import
import sys
import time
import logging
import threading
import subprocess

# Import pytest-salt libs
from pytestsalt.utils import SaltDaemonScriptBase as PytestSaltDaemonScriptBase
from pytestsalt.utils import SaltRunEventListener as PytestSaltRunEventListener
from pytestsalt.utils import collect_child_processes, terminate_process, terminate_process_list  # pylint: disable=unused-import
from pytestsalt.fixtures.daemons import Salt as PytestSalt
from pytestsalt.fixtures.daemons import SaltKey as PytestSaltKey
from pytestsalt.fixtures.daemons import SaltRun as PytestSaltRun
from pytestsalt.fixtures.daemons import SaltCall as PytestSaltCall
from pytestsalt.fixtures.daemons import SaltMaster as PytestSaltMaster
from pytestsalt.fixtures.daemons import SaltMinion as PytestSaltMinion
from pytestsalt.fixtures.daemons import SaltSyndic as PytestSaltSyndic
from pytestsalt.fixtures.daemons import SaltProxy as PytestSaltProxy

# Import tests support libs
from tests.support.paths import ScriptPathMixin

log = logging.getLogger(__name__)


class LogDaemonStdsMixin(object):

    def start(self):
        '''
        Start the daemon subprocess
        '''
        # Late import
        log.info('[%s][%s] Starting DAEMON in CWD: %s', self.log_prefix, self.cli_display_name, self.cwd)
        proc_args = [
            self.get_script_path(self.cli_script_name)
        ] + self.get_base_script_args() + self.get_script_args()

        if sys.platform.startswith('win'):
            # Windows needs the python executable to come first
            proc_args.insert(0, sys.executable)

        log.info('[%s][%s] Running \'%s\'...', self.log_prefix, self.cli_display_name, ' '.join(proc_args))

        self.init_terminal(proc_args,
                           env=self.environ,
                           cwd=self.cwd,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        self._running.set()
        if self._process_cli_output_in_thread:
            process_output_thread = threading.Thread(target=self._process_output_in_thread)
            process_output_thread.daemon = True
            process_output_thread.start()
        return True


class SaltDaemonScriptBase(LogDaemonStdsMixin, PytestSaltDaemonScriptBase):
    '''
    Inject the LogDaemonStdsMixin until we start doing that on pytest-salt
    '''


class SaltRunEventListener(ScriptPathMixin, PytestSaltRunEventListener):
    '''
    Override this class's __init__ because there's no request argument since we're still
    not running under pytest
    '''


class GetSaltRunFixtureMixin(ScriptPathMixin):
    '''
    Override this classes `get_salt_run_fixture` because we're still not running under pytest
    '''

    def get_salt_run_fixture(self):
        pass

    def get_salt_run_event_listener(self):
        return SaltRunEventListener(None,
                                    self.config,
                                    self.config_dir,
                                    self.bin_dir_path,
                                    self.log_prefix,
                                    cli_script_name='run')


class Salt(ScriptPathMixin, PytestSalt):
    '''
    Class which runs salt-call commands
    '''
    def __init__(self, *args, **kwargs):
        super(Salt, self).__init__(None, *args, **kwargs)


class SaltCall(ScriptPathMixin, PytestSaltCall):
    '''
    Class which runs salt-call commands
    '''
    def __init__(self, *args, **kwargs):
        super(SaltCall, self).__init__(None, *args, **kwargs)


class SaltKey(ScriptPathMixin, PytestSaltKey):
    '''
    Class which runs salt-key commands
    '''
    def __init__(self, *args, **kwargs):
        super(SaltKey, self).__init__(None, *args, **kwargs)


class SaltRun(ScriptPathMixin, PytestSaltRun):
    '''
    Class which runs salt-run commands
    '''
    def __init__(self, *args, **kwargs):
        super(SaltRun, self).__init__(None, *args, **kwargs)


class SaltProxy(GetSaltRunFixtureMixin, LogDaemonStdsMixin, PytestSaltProxy):
    '''
    Class which runs the salt-proxy daemon
    '''


class SaltMinion(GetSaltRunFixtureMixin, LogDaemonStdsMixin, PytestSaltMinion):
    '''
    Class which runs the salt-minion daemon
    '''


class SaltMaster(GetSaltRunFixtureMixin, LogDaemonStdsMixin, PytestSaltMaster):
    '''
    Class which runs the salt-master daemon
    '''


class SaltSyndic(GetSaltRunFixtureMixin, LogDaemonStdsMixin, PytestSaltSyndic):
    '''
    Class which runs the salt-syndic daemon
    '''

# XXX: Unify start_salt_daemon with start_test_daemon


def start_salt_daemon(daemon_name=None,
                      daemon_id=None,
                      daemon_log_prefix=None,
                      daemon_cli_script_name=None,
                      daemon_config=None,
                      daemon_config_dir=None,
                      daemon_class=None,
                      bin_dir_path=None,
                      fail_hard=False,
                      start_timeout=10,
                      slow_stop=False,
                      environ=None,
                      cwd=None):
    '''
    Returns a running salt daemon
    '''
    daemon_config['pytest_port'] = daemon_config['runtests_conn_check_port']
    request = None
    if fail_hard:
        fail_method = RuntimeError
    else:
        fail_method = RuntimeWarning
    log.info('[%s] Starting %s(%s)', daemon_name, daemon_log_prefix, daemon_id)
    attempts = 0
    process = None
    while attempts <= 3:  # pylint: disable=too-many-nested-blocks
        attempts += 1
        process = daemon_class(request,
                               daemon_config,
                               daemon_config_dir,
                               bin_dir_path,
                               daemon_log_prefix,
                               cli_script_name=daemon_cli_script_name,
                               slow_stop=slow_stop,
                               environ=environ,
                               cwd=cwd)
        process.start()
        if process.is_alive():
            try:
                connectable = process.wait_until_running(timeout=start_timeout)
                if connectable is False:
                    connectable = process.wait_until_running(timeout=start_timeout/2)
                    if connectable is False:
                        process.terminate()
                        if attempts >= 3:
                            fail_method(
                                '{0}({1}) has failed to confirm running status '
                                'after {2} attempts'.format(daemon_name, daemon_id, attempts))
                        continue
            except Exception as exc:  # pylint: disable=broad-except
                log.exception('[%s] %s', daemon_log_prefix, exc, exc_info=True)
                terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
                if attempts >= 3:
                    raise fail_method(str(exc))
                continue
            log.info(
                '[%s] %s(%s) is running and accepting commands after %d attempts',
                daemon_log_prefix,
                daemon_name,
                daemon_id,
                attempts
            )

            return process
        else:
            terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
            continue
    else:   # pylint: disable=useless-else-on-loop
            # Wrong, we have a return, its not useless
        if process is not None:
            terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
        raise fail_method(
            '{0}({1}) has failed to start after {2} attempts'.format(
                daemon_name,
                daemon_id,
                attempts-1
            )
        )


def start_test_daemon(daemon_cli_script_name,
                      daemon_config_dir,
                      daemon_check_port,
                      daemon_class,
                      start_timeout=10,
                      slow_stop=True,
                      environ=None,
                      cwd=None,
                      max_attempts=3,
                      **kwargs):
    '''
    Returns a running process daemon
    '''
    log.info('[%s] Starting %s', daemon_class.log_prefix, daemon_class.__name__)
    attempts = 0
    process = None
    while attempts <= max_attempts:  # pylint: disable=too-many-nested-blocks
        attempts += 1
        process = daemon_class(str(daemon_config_dir),
                               daemon_check_port,
                               cli_script_name=daemon_cli_script_name,
                               slow_stop=slow_stop,
                               environ=environ,
                               cwd=cwd,
                               **kwargs)
        process.start()
        if process.is_alive():
            try:
                connectable = process.wait_until_running(timeout=start_timeout)
                if connectable is False:
                    connectable = process.wait_until_running(timeout=start_timeout/2)
                    if connectable is False:
                        process.terminate()
                        if attempts >= max_attempts:
                            raise AssertionError(
                                'The {} has failed to confirm running status '
                                'after {} attempts'.format(daemon_class.__name__, attempts))
                        continue
            except Exception as exc:  # pylint: disable=broad-except
                log.exception('[%s] %s', daemon_class.log_prefix, exc, exc_info=True)
                terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
                if attempts >= max_attempts:
                    raise AssertionError(str(exc))
                continue
            # A little breathing before returning the process
            time.sleep(0.5)
            log.info(
                '[%s] The %s is running after %d attempts',
                daemon_class.log_prefix,
                daemon_class.__name__,
                attempts
            )
            return process
        else:
            terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
            time.sleep(1)
            continue
    else:   # pylint: disable=useless-else-on-loop
            # Wrong, we have a return, its not useless
        if process is not None:
            terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
        raise AssertionError(
            'The {} has failed to start after {} attempts'.format(
                daemon_class.__name__,
                attempts-1
            )
        )

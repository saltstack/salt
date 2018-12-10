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
import os
import logging

# Import pytest-salt libs
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
try:
    from pytestsalt.version import __version_info__ as __pytestsalt_version_info__
except ImportError:
    from pytestsalt import __version_info__ as __pytestsalt_version_info__

# Import tests support libs
from tests.support.paths import ScriptPathMixin

log = logging.getLogger(__name__)


class SaltRunEventListener(ScriptPathMixin, PytestSaltRunEventListener):
    '''
    Override this class's __init__ because there's no request argument since we're still
    not running under pytest
    '''

    def run(self, tags=(), timeout=10):  # pylint: disable=arguments-differ
        if __pytestsalt_version_info__ <= (2018, 9, 28):
            log.info('%s checking for tags: %s', self.__class__.__name__, tags)
        result = super(SaltRunEventListener, self).run(tags=tags, timeout=timeout)
        if __pytestsalt_version_info__ > (2018, 9, 28):
            return result
        if result.exitcode != 0:
            return result
        if not result.json['unmatched']:
            stop_sending_events_file = self.config.get('pytest_stop_sending_events_file')
            if stop_sending_events_file and os.path.exists(stop_sending_events_file):
                log.warning('Removing pytest_stop_sending_events_file: %s', stop_sending_events_file)
                os.unlink(stop_sending_events_file)
        return result


class GetSaltRunFixtureMixin(ScriptPathMixin):
    '''
    Override this classes `get_salt_run_fixture` because we're still not running under pytest
    '''

    def get_salt_run_fixture(self):
        pass

    def get_salt_run_event_listener(self):
        try:
            return SaltRunEventListener(None,
                                        self.config,
                                        self.event_listener_config_dir or self.config_dir,
                                        self.bin_dir_path,
                                        self.log_prefix,
                                        cli_script_name='run')
        except AttributeError:
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


class SaltProxy(GetSaltRunFixtureMixin, PytestSaltProxy):
    '''
    Class which runs the salt-proxy daemon
    '''


class SaltMinion(GetSaltRunFixtureMixin, PytestSaltMinion):
    '''
    Class which runs the salt-minion daemon
    '''


class SaltMaster(GetSaltRunFixtureMixin, PytestSaltMaster):
    '''
    Class which runs the salt-master daemon
    '''


class SaltSyndic(GetSaltRunFixtureMixin, PytestSaltSyndic):
    '''
    Class which runs the salt-syndic daemon
    '''


def start_daemon(daemon_name=None,
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
                 cwd=None,
                 event_listener_config_dir=None):
    '''
    Returns a running salt daemon
    '''
    # Old config name
    daemon_config['pytest_port'] = daemon_config['runtests_conn_check_port']
    # New config name
    daemon_config['pytest_engine_port'] = daemon_config['runtests_conn_check_port']
    request = None
    if fail_hard:
        fail_method = RuntimeError
    else:
        fail_method = RuntimeWarning
    log.info('[%s] Starting pytest %s(%s)', daemon_name, daemon_log_prefix, daemon_id)
    attempts = 0
    process = None
    while attempts <= 3:  # pylint: disable=too-many-nested-blocks
        attempts += 1
        try:
            process = daemon_class(request=request,
                                   config=daemon_config,
                                   config_dir=daemon_config_dir,
                                   bin_dir_path=bin_dir_path,
                                   log_prefix=daemon_log_prefix,
                                   cli_script_name=daemon_cli_script_name,
                                   slow_stop=slow_stop,
                                   environ=environ,
                                   cwd=cwd,
                                   event_listener_config_dir=event_listener_config_dir)
        except TypeError:
            process = daemon_class(request=request,
                                   config=daemon_config,
                                   config_dir=daemon_config_dir,
                                   bin_dir_path=bin_dir_path,
                                   log_prefix=daemon_log_prefix,
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
                                'The pytest {0}({1}) has failed to confirm running status '
                                'after {2} attempts'.format(daemon_name, daemon_id, attempts))
                        continue
            except Exception as exc:  # pylint: disable=broad-except
                log.exception('[%s] %s', daemon_log_prefix, exc, exc_info=True)
                terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
                if attempts >= 3:
                    raise fail_method(str(exc))
                continue
            log.info(
                '[%s] The pytest %s(%s) is running and accepting commands '
                'after %d attempts',
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
            'The pytest {0}({1}) has failed to start after {2} attempts'.format(
                daemon_name,
                daemon_id,
                attempts-1
            )
        )

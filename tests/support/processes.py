# -*- coding: utf-8 -*-
"""
    :copyright: Copyright 2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.processes
    ~~~~~~~~~~~~~~~~~~~~~~~

    Process handling utilities
"""

from __future__ import absolute_import

import logging

from saltfactories.utils.processes.helpers import (  # pylint: disable=unused-import
    collect_child_processes,
    terminate_process,
    terminate_process_list,
)
from tests.support.cli_scripts import ScriptPathMixin

try:
    from pytestsalt.fixtures.daemons import Salt as PytestSalt
    from pytestsalt.fixtures.daemons import SaltCall as PytestSaltCall
    from pytestsalt.fixtures.daemons import SaltKey as PytestSaltKey
    from pytestsalt.fixtures.daemons import SaltMaster as PytestSaltMaster
    from pytestsalt.fixtures.daemons import SaltMinion as PytestSaltMinion
    from pytestsalt.fixtures.daemons import SaltProxy as PytestSaltProxy
    from pytestsalt.fixtures.daemons import SaltRun as PytestSaltRun
    from pytestsalt.fixtures.daemons import SaltSyndic as PytestSaltSyndic
except ImportError:
    # If this happens, we are running under pytest which uninstalls pytest-salt due to impatabilites
    # These imports won't actually work but these classes are only used when running under runtests,
    # so, we're just making sure we also don't hit NameError's
    from saltfactories.utils.processes.salts import SaltCallCLI as PytestSaltCall
    from saltfactories.utils.processes.salts import SaltCLI as PytestSalt
    from saltfactories.utils.processes.salts import SaltKeyCLI as PytestSaltKey
    from saltfactories.utils.processes.salts import SaltMaster as PytestSaltMaster
    from saltfactories.utils.processes.salts import SaltMinion as PytestSaltMinion
    from saltfactories.utils.processes.salts import SaltProxyMinion as PytestSaltProxy
    from saltfactories.utils.processes.salts import SaltRunCLI as PytestSaltRun
    from saltfactories.utils.processes.salts import SaltSyndic as PytestSaltSyndic

log = logging.getLogger(__name__)


class GetSaltRunFixtureMixin(ScriptPathMixin):
    """
    Override this classes `get_salt_run_fixture` because we're still not running under pytest
    """

    def get_salt_run_fixture(self):
        pass


class Salt(ScriptPathMixin, PytestSalt):
    """
    Class which runs salt-call commands
    """

    def __init__(self, *args, **kwargs):
        super(Salt, self).__init__(None, *args, **kwargs)


class SaltCall(ScriptPathMixin, PytestSaltCall):
    """
    Class which runs salt-call commands
    """

    def __init__(self, *args, **kwargs):
        super(SaltCall, self).__init__(None, *args, **kwargs)


class SaltKey(ScriptPathMixin, PytestSaltKey):
    """
    Class which runs salt-key commands
    """

    def __init__(self, *args, **kwargs):
        super(SaltKey, self).__init__(None, *args, **kwargs)


class SaltRun(ScriptPathMixin, PytestSaltRun):
    """
    Class which runs salt-run commands
    """

    def __init__(self, *args, **kwargs):
        super(SaltRun, self).__init__(None, *args, **kwargs)


class SaltProxy(GetSaltRunFixtureMixin, PytestSaltProxy):
    """
    Class which runs the salt-proxy daemon
    """


class SaltMinion(GetSaltRunFixtureMixin, PytestSaltMinion):
    """
    Class which runs the salt-minion daemon
    """


class SaltMaster(GetSaltRunFixtureMixin, PytestSaltMaster):
    """
    Class which runs the salt-master daemon
    """


class SaltSyndic(GetSaltRunFixtureMixin, PytestSaltSyndic):
    """
    Class which runs the salt-syndic daemon
    """


def start_daemon(
    daemon_name=None,
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
    event_listener_config_dir=None,
):
    """
    Returns a running salt daemon
    """
    # Old config name
    daemon_config["pytest_port"] = daemon_config["runtests_conn_check_port"]
    # New config name
    daemon_config["pytest_engine_port"] = daemon_config["runtests_conn_check_port"]
    request = None
    if fail_hard:
        fail_method = RuntimeError
    else:
        fail_method = RuntimeWarning
    log.info("[%s] Starting pytest %s(%s)", daemon_name, daemon_log_prefix, daemon_id)
    attempts = 0
    process = None
    while attempts <= 3:  # pylint: disable=too-many-nested-blocks
        attempts += 1
        try:
            process = daemon_class(
                request=request,
                config=daemon_config,
                config_dir=daemon_config_dir,
                bin_dir_path=bin_dir_path,
                log_prefix=daemon_log_prefix,
                cli_script_name=daemon_cli_script_name,
                slow_stop=slow_stop,
                environ=environ,
                cwd=cwd,
                event_listener_config_dir=event_listener_config_dir,
            )
        except TypeError:
            process = daemon_class(
                request=request,
                config=daemon_config,
                config_dir=daemon_config_dir,
                bin_dir_path=bin_dir_path,
                log_prefix=daemon_log_prefix,
                cli_script_name=daemon_cli_script_name,
                slow_stop=slow_stop,
                environ=environ,
                cwd=cwd,
            )
        process.start()
        if process.is_alive():
            try:
                connectable = process.wait_until_running(timeout=start_timeout)
                if connectable is False:
                    connectable = process.wait_until_running(timeout=start_timeout / 2)
                    if connectable is False:
                        process.terminate()
                        if attempts >= 3:
                            fail_method(
                                "The pytest {0}({1}) has failed to confirm running status "
                                "after {2} attempts".format(
                                    daemon_name, daemon_id, attempts
                                )
                            )
                        continue
            except Exception as exc:  # pylint: disable=broad-except
                log.exception("[%s] %s", daemon_log_prefix, exc, exc_info=True)
                terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
                if attempts >= 3:
                    raise fail_method(str(exc))
                continue
            log.info(
                "[%s] The pytest %s(%s) is running and accepting commands "
                "after %d attempts",
                daemon_log_prefix,
                daemon_name,
                daemon_id,
                attempts,
            )

            break
        else:
            terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
            continue
    else:
        if process is not None:
            terminate_process(process.pid, kill_children=True, slow_stop=slow_stop)
        raise fail_method(
            "The pytest {0}({1}) has failed to start after {2} attempts".format(
                daemon_name, daemon_id, attempts - 1
            )
        )
    return process

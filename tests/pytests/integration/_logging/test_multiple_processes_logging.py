import pathlib
import time
from types import SimpleNamespace

import pytest
from _pytest.pytester import LineMatcher
from saltfactories.utils import random_string

import salt.utils.platform

pytestmark = [
    pytest.mark.skip_on_windows(reason="Temporarily skipped on the newer golden images")
]


@pytest.fixture(scope="module")
def logging_master(salt_factories):
    log_format = "|%(name)-17s:%(lineno)-4d|%(levelname)-8s|%(processName)s|PID:%(process)d|%(message)s"
    config_overrides = {
        "log_level": "debug",
        "log_fmt_console": log_format,
        "log_level_logfile": "debug",
        "log_fmt_logfile": log_format,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("master-logging-"),
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    process_pid = None
    with factory.started("--log-level=debug"):
        process_pid = factory.pid
        # Wait a little after the master starts
        if not salt.utils.platform.spawning_platform():
            time.sleep(2)
        else:
            time.sleep(10)

    ret = factory.terminate()
    return SimpleNamespace(
        process_pid=process_pid,
        ret=ret,
        log_file=pathlib.Path(factory.config["log_file"]),
    )


@pytest.fixture(scope="module")
def matches(logging_master):
    return [
        # Each of these is a separate process started by the master
        "*|PID:{}|*".format(logging_master.process_pid),
        "*|MWorker-*|*",
        "*|Maintenance|*",
        "*|ReqServer|*",
        "*|PubServerChannel._publish_daemon|*",
        "*|MWorkerQueue|*",
        "*|FileServerUpdate|*",
    ]


@pytest.mark.windows_whitelisted
def test_multiple_processes_logging_stderr(logging_master, matches):
    # Are we seeing the main pid in the STDERR getting logged?
    # And there must be more than the main process in the STDERR logs
    matcher = LineMatcher(logging_master.ret.stderr.splitlines())
    matcher.fnmatch_lines_random(matches)


@pytest.mark.windows_whitelisted
def test_multiple_processes_logging_log_file(logging_master, matches):
    # And on the log file, we also have matches?
    matcher = LineMatcher(logging_master.log_file.read_text().splitlines())
    matcher.fnmatch_lines_random(matches)

import pathlib

import pytest
from saltfactories.utils import random_string

from salt._logging import DFLT_LOG_FMT_JID
from salt._logging.impl import DFLT_LOG_FMT_MINION_ID


@pytest.fixture(scope="module")
def log_field_marker():
    """
    Marker to make identifying log fields possible without risk of matching
    other instances of jid or minion_id in the log messages
    """
    return "EXTRA_LOG_FIELD:"


@pytest.fixture(scope="module")
def logging_master(salt_master_factory, log_field_marker):
    """
    A logging master fixture with JID and minion_id in log format
    """
    log_format = (
        f"{log_field_marker}%(jid)s {log_field_marker}%(minion_id)s %(message)s"
    )
    config_overrides = {
        "log_level_logfile": "debug",
        "log_fmt_logfile": log_format,
    }
    logging_master_factory = salt_master_factory.salt_master_daemon(
        random_string("master-logging-"),
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with logging_master_factory.started():
        yield logging_master_factory


@pytest.fixture(scope="module")
def logging_master_logfile(logging_master):
    """
    The logging master log file path
    """
    assert logging_master.is_running()
    return pathlib.Path(logging_master.config["log_file"])


@pytest.fixture(scope="module")
def salt_cli(logging_master):
    """
    A ``salt``` CLI fixture
    """
    assert logging_master.is_running()
    return logging_master.salt_cli(timeout=30)


@pytest.fixture(scope="module")
def logging_minion_id(logging_master):
    """
    Random minion id for a salt-minion fixture
    """
    return random_string("minion-logging-")


@pytest.fixture
def logging_minion(logging_master, logging_minion_id):
    """
    A running salt-minion fixture connected to the logging master
    """
    assert logging_master.is_running()
    salt_minion_factory = logging_master.salt_minion_daemon(
        logging_minion_id,
    )
    with salt_minion_factory.started():
        yield salt_minion_factory


def test_jid_minion_id_in_logs(
    logging_master_logfile, log_field_marker, salt_cli, logging_minion
):
    """
    Test JID and minion_id appear in master log file in the expected format
    """
    ret = salt_cli.run("test.ping", "-v", minion_tgt=logging_minion.id)
    assert ret.returncode == 0
    assert "Executing job with jid" in ret.stdout

    jid_str = DFLT_LOG_FMT_JID % {"jid": ret.stdout.splitlines()[0].split()[-1]}
    minion_id_str = DFLT_LOG_FMT_MINION_ID % {"minion_id": logging_minion.id}

    log_file_text = logging_master_logfile.read_text()

    assert f"{log_field_marker}{jid_str}" in log_file_text
    assert f"{log_field_marker}{minion_id_str}" in log_file_text

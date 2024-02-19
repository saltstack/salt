import logging
import os

import pytest

import salt._logging.impl as log_impl
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows(reason="Temporarily skipped on the newer golden images")
]


log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {log_impl: {}}


def log_nameToLevel(name):
    """
    Return the numeric representation of textual logging level
    """
    # log level values
    CRITICAL = 50
    FATAL = CRITICAL
    ERROR = 40
    WARNING = 30
    WARN = WARNING
    INFO = 20
    DEBUG = 10
    NOTSET = 0

    _nameToLevel = {
        "CRITICAL": CRITICAL,
        "FATAL": FATAL,
        "ERROR": ERROR,
        "WARN": WARNING,
        "WARNING": WARNING,
        "INFO": INFO,
        "DEBUG": DEBUG,
        "NOTSET": NOTSET,
    }
    return _nameToLevel.get(name, None)


def test_lowest_log_level():
    ret = log_impl.get_lowest_log_level()
    assert ret is not None

    log_impl.set_lowest_log_level(log_nameToLevel("DEBUG"))
    ret = log_impl.get_lowest_log_level()
    assert ret is log_nameToLevel("DEBUG")

    log_impl.set_lowest_log_level(log_nameToLevel("WARNING"))
    ret = log_impl.get_lowest_log_level()
    assert ret is log_nameToLevel("WARNING")

    opts = {"log_level": "ERROR", "log_level_logfile": "INFO"}
    log_impl.set_lowest_log_level_by_opts(opts)
    ret = log_impl.get_lowest_log_level()
    assert ret is log_nameToLevel("INFO")


def test_get_logging_level_from_string(caplog):
    ret = log_impl.get_logging_level_from_string(None)
    assert ret is log_nameToLevel("WARNING")

    ret = log_impl.get_logging_level_from_string(log_nameToLevel("DEBUG"))
    assert ret is log_nameToLevel("DEBUG")

    ret = log_impl.get_logging_level_from_string("CRITICAL")
    assert ret is log_nameToLevel("CRITICAL")

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        msg = "Could not translate the logging level string 'BADLEVEL' into an actual logging level integer. Returning 'logging.ERROR'."
        ret = log_impl.get_logging_level_from_string("BADLEVEL")
        assert ret is log_nameToLevel("ERROR")
        assert msg in caplog.text


def test_logfile_handler(caplog):
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ret = log_impl.is_logfile_handler_configured()
        assert ret is False

        msg = "log_path setting is set to `None`. Nothing else to do"
        log_path = None
        assert log_impl.setup_logfile_handler(log_path) is None
        assert msg in caplog.text


def test_in_mainprocess():
    ret = log_impl.in_mainprocess()
    assert ret is True

    curr_pid = os.getpid()
    with patch(
        "os.getpid", MagicMock(side_effect=[AttributeError, curr_pid, curr_pid])
    ):
        ret = log_impl.in_mainprocess()
        assert ret is True

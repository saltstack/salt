"""
How the filter is set up and what it does on the way a real process uses it:
the option defaults to off, ``setup_logging()`` installs the filter before the
pillar exists, and the pillar is registered when it is compiled.
"""

import io
import logging

import pytest

import salt._logging.filters.pillar as pillar_filter
import salt._logging.impl as impl
import salt.config
import salt.utils.immutabletypes
from salt._logging.filters.pillar import PillarRedactingFilter
from salt._logging.handlers import StreamHandler

SECRET = "hunter2-secret"
MASKED = pillar_filter.REDACT_PLACEHOLDER


@pytest.fixture(autouse=True)
def clean_registry():
    pillar_filter.clear()
    try:
        yield
    finally:
        pillar_filter.clear()


def _handler():
    stream = io.StringIO()
    handler = StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler, stream


def _logger(name, *handlers):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers = list(handlers)
    return logger


def _startup_opts(enabled=True):
    """What setup_logging() works from: a frozen copy made before the pillar exists."""
    return salt.utils.immutabletypes.freeze(
        {"pillar_mask_output": enabled, "pillar": {}}
    )


@pytest.mark.parametrize(
    "defaults", [salt.config.DEFAULT_MINION_OPTS, salt.config.DEFAULT_MASTER_OPTS]
)
def test_the_option_is_off_by_default(defaults):
    assert defaults["pillar_mask_output"] is False


def test_the_option_is_a_boolean():
    assert salt.config.VALID_OPTS["pillar_mask_output"] is bool


def test_setup_installs_the_filter_on_every_handler(monkeypatch):
    first, _ = _handler()
    second, _ = _handler()
    monkeypatch.setattr(logging.root, "handlers", [first, second])
    impl.setup_pillar_redacting_filter(_startup_opts())
    for handler in (first, second):
        assert [type(f) for f in handler.filters] == [PillarRedactingFilter]


def test_setup_twice_does_not_install_a_second_filter(monkeypatch):
    handler, _ = _handler()
    monkeypatch.setattr(logging.root, "handlers", [handler])
    impl.setup_pillar_redacting_filter(_startup_opts())
    impl.setup_pillar_redacting_filter(_startup_opts())
    assert len(handler.filters) == 1


@pytest.mark.parametrize("opts", [None, {}])
def test_setup_without_options_does_nothing(monkeypatch, opts):
    handler, _ = _handler()
    monkeypatch.setattr(logging.root, "handlers", [handler])
    impl.setup_pillar_redacting_filter(opts)
    assert handler.filters == []


def test_the_way_a_real_process_starts(monkeypatch):
    """
    Logging is set up first, from a frozen config whose pillar is empty. The
    pillar is compiled later and registered, and from then on its values are
    redacted from what the handlers write.
    """
    handler, stream = _handler()
    monkeypatch.setattr(logging.root, "handlers", [handler])
    impl.setup_pillar_redacting_filter(_startup_opts())
    logger = _logger("salt.tests.setup.realprocess", handler)

    logger.debug("before the pillar is known: %s", SECRET)
    assert stream.getvalue().strip() == f"before the pillar is known: {SECRET}"

    pillar_filter.register({"db": {"password": SECRET}})
    stream.seek(0)
    stream.truncate()
    logger.debug("after the pillar is compiled: %s", SECRET)
    assert stream.getvalue().strip() == f"after the pillar is compiled: {MASKED}"


def test_nothing_is_redacted_when_the_option_is_off(monkeypatch):
    handler, stream = _handler()
    monkeypatch.setattr(logging.root, "handlers", [handler])
    impl.setup_pillar_redacting_filter(_startup_opts(enabled=False))
    pillar_filter.register({"password": SECRET})
    _logger("salt.tests.setup.off", handler).debug("pw %s", SECRET)
    assert stream.getvalue().strip() == f"pw {SECRET}"


def test_a_value_that_is_also_ordinary_text_is_replaced_everywhere():
    """
    Values are matched as text, so a pillar value such as a user name is also
    replaced where it is not a secret. This is how the filter is meant to work,
    not a bug, and it is why the option is off by default.
    """
    handler, stream = _handler()
    handler.addFilter(
        PillarRedactingFilter(
            {"pillar_mask_output": True, "pillar": {"user": "root", "pkg": "salt"}}
        )
    )
    _logger("salt.tests.setup.words", handler).debug("Running as root: salt-minion")
    assert stream.getvalue().strip() == f"Running as {MASKED}: {MASKED}-minion"


def test_a_value_is_replaced_in_a_message_with_no_arguments():
    handler, stream = _handler()
    handler.addFilter(
        PillarRedactingFilter(
            {"pillar_mask_output": True, "pillar": {"password": SECRET}}
        )
    )
    _logger("salt.tests.setup.noargs", handler).debug(f"the password is {SECRET}")
    assert stream.getvalue().strip() == f"the password is {MASKED}"

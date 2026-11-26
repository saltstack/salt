"""
Cases the filter does not cover.

Each test says what a reader would expect, and is marked ``xfail`` with
``strict=True``: today the secret is written, so the test fails as expected.
When a gap is closed the test passes, ``strict`` turns that into a failure, and
the marker and the entry in the documentation are to be removed.
"""

import base64
import io
import logging
import urllib.parse

import pytest

import salt._logging.filters.pillar as pillar_filter
import salt._logging.impl as impl
import salt.utils.immutabletypes
from salt._logging.filters.pillar import PillarRedactingFilter, install_on_handler
from salt._logging.handlers import StreamHandler

SECRET = "hunter2-secret"

gap = pytest.mark.xfail(raises=AssertionError, strict=True)


@pytest.fixture(autouse=True)
def clean_registry():
    pillar_filter.clear()
    pillar_filter.register({"password": SECRET})
    try:
        yield
    finally:
        pillar_filter.clear()


def _logged(name, call, fmt="%(message)s", pillar=None):
    """Run ``call(logger)`` through a handler that has the filter; return the output."""
    opts = salt.utils.immutabletypes.freeze(
        {"pillar_mask_output": True, "pillar": pillar or {}}
    )
    stream = io.StringIO()
    handler = StreamHandler(stream)
    handler.setFormatter(logging.Formatter(fmt))
    install_on_handler(handler, opts)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers = [handler]
    call(logger)
    return stream.getvalue()


class _Custom:
    def __str__(self):
        return f"Custom(password={SECRET})"


@gap
def test_an_object_whose_text_holds_the_value():
    out = _logged("salt.tests.gap.object", lambda lg: lg.error("%s", _Custom()))
    assert SECRET not in out


@gap
def test_an_exception_as_an_argument():
    out = _logged(
        "salt.tests.gap.exception",
        lambda lg: lg.error("failed: %s", RuntimeError(f"bad {SECRET}")),
    )
    assert SECRET not in out


@gap
def test_the_values_inside_a_set():
    out = _logged("salt.tests.gap.set", lambda lg: lg.debug("%s", {SECRET}))
    assert SECRET not in out


@gap
def test_the_traceback_of_log_exception():
    def call(logger):
        try:
            raise RuntimeError(f"login failed with {SECRET}")
        except RuntimeError:
            logger.exception("boom")

    assert SECRET not in _logged("salt.tests.gap.traceback", call)


@gap
def test_a_console_format_that_uses_colormsg():
    out = _logged(
        "salt.tests.gap.colormsg",
        lambda lg: lg.debug("pw %s", SECRET),
        fmt="%(colormsg)s",
    )
    assert SECRET not in out


@gap
def test_an_int_inside_a_dict_argument():
    pillar_filter.register({"port": 5432})
    out = _logged(
        "salt.tests.gap.int", lambda lg: lg.debug("config: %s", {"port": 5432})
    )
    assert "5432" not in out


@gap
def test_a_handler_that_is_added_after_logging_was_set_up(monkeypatch):
    """The filter is installed on the handlers that exist when logging is set up."""
    monkeypatch.setattr(logging.root, "handlers", [])
    impl.setup_pillar_redacting_filter(
        salt.utils.immutabletypes.freeze({"pillar_mask_output": True, "pillar": {}})
    )
    stream = io.StringIO()
    late = StreamHandler(stream)
    late.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("salt.tests.gap.late")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers = [late]
    logger.debug("pw %s", SECRET)
    assert SECRET not in stream.getvalue()


@gap
def test_a_pillar_that_is_changed_in_place():
    """The filter notices a new ``opts["pillar"]``, not a change inside the old one."""
    pillar = {"a": "first-secret-value"}
    opts = {"pillar_mask_output": True, "pillar": pillar}
    flt = PillarRedactingFilter(opts)
    pillar["b"] = "second-secret-value"
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "pw %s", ("second-secret-value",), None
    )
    flt.filter(record)
    assert "second-secret-value" not in record.getMessage()


@gap
def test_one_line_of_a_multi_line_value():
    key = "-----BEGIN KEY-----\nAAAA-secret-line\nBBBB-secret-line\n-----END KEY-----"
    pillar_filter.register({"key": key})
    out = _logged("salt.tests.gap.line", lambda lg: lg.debug("line: AAAA-secret-line"))
    assert "AAAA-secret-line" not in out


@gap
def test_the_url_encoded_form_of_a_value():
    value = "p@ss w0rd/secret"
    pillar_filter.register({"pw": value})
    out = _logged(
        "salt.tests.gap.url", lambda lg: lg.debug("%s", urllib.parse.quote(value))
    )
    assert urllib.parse.quote(value) not in out


@gap
def test_the_base64_form_of_a_value():
    value = "p@ss w0rd/secret"
    pillar_filter.register({"pw": value})
    encoded = base64.b64encode(value.encode()).decode()
    out = _logged("salt.tests.gap.b64", lambda lg: lg.debug("%s", encoded))
    assert encoded not in out

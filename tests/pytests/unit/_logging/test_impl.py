"""
Tests for salt._logging.impl.
"""

import io
import logging

import pytest

from salt._logging.handlers import DeferredStreamHandler, StreamHandler
from salt._logging.impl import (
    SaltColorLogRecord,
    SaltLogRecord,
    get_log_record_factory,
    set_log_record_factory,
    set_logging_options_dict,
    setup_logging,
)
from tests.support.mock import patch


@pytest.fixture
def restore_log_record_factory():
    original = get_log_record_factory()
    try:
        yield
    finally:
        set_log_record_factory(original)


@pytest.fixture
def restore_root_handlers():
    original = logging.root.handlers[:]
    original_level = logging.root.level
    try:
        yield
    finally:
        logging.root.handlers[:] = original
        logging.root.setLevel(original_level)


def test_salt_log_record_provides_color_attributes():
    """
    Regression test for #68129.

    ``SaltLogRecord`` must define the ``color*`` attributes so that a
    formatter using ``%(colorlevel)s`` / ``%(colormsg)s`` / ``%(colorname)s``
    / ``%(colorprocess)s`` can format records produced by the plain
    ``SaltLogRecord`` factory.  Records that were buffered by the temporary
    deferred stream handler before the color log record factory was
    installed (for example, the records flushed by ``shutdown_temp_handler``
    once ``setup_console_handler`` has run with a color ``log_fmt_console``)
    must not raise ``ValueError: Formatting field not found in record``.
    """
    record = SaltLogRecord(
        "salt.test",
        logging.DEBUG,
        __file__,
        1,
        "hello %s",
        ("world",),
        None,
    )
    assert hasattr(record, "colorname")
    assert hasattr(record, "colorlevel")
    assert hasattr(record, "colorprocess")
    assert hasattr(record, "colormsg")

    fmt = logging.Formatter(
        "%(colorlevel)s %(colorname)s %(colorprocess)s %(colormsg)s"
    )
    # Must not raise -- the bug in #68129 manifested here as
    # ``ValueError: Formatting field not found in record: 'colorlevel'``.
    formatted = fmt.format(record)
    assert "DEBUG" in formatted
    assert "hello world" in formatted


def test_deferred_records_flushed_through_color_formatter(
    restore_log_record_factory, restore_root_handlers
):
    """
    Regression test for #68129.

    Simulate the real-world sequence:

    1. The temporary ``DeferredStreamHandler`` buffers log records while
       the plain ``SaltLogRecord`` factory is active.
    2. ``setup_console_handler`` installs ``SaltColorLogRecord`` as the
       active factory and adds a console handler whose formatter uses
       custom color attributes (``%(colorlevel)s``/``%(colormsg)s``).
    3. ``shutdown_temp_handler`` flushes the buffered records to the new
       console handler via ``sync_with_handlers``.

    Before the fix, step 3 raised ``ValueError: Formatting field not found
    in record: 'colorlevel'`` for every buffered record because those
    records were ``SaltLogRecord`` instances created before the color
    factory was installed.
    """
    logging.root.handlers[:] = []
    logging.root.setLevel(logging.DEBUG)

    # Step 1: buffer a record using the plain factory.
    set_log_record_factory(SaltLogRecord)
    deferred = DeferredStreamHandler(io.StringIO())
    deferred.setLevel(logging.DEBUG)
    deferred.setFormatter(logging.Formatter("%(message)s"))
    logging.root.addHandler(deferred)
    logger = logging.getLogger("test_68129_deferred")
    logger.debug("buffered message")

    # Step 2: install the color factory and a color-format console handler.
    set_log_record_factory(SaltColorLogRecord)
    console_stream = io.StringIO()
    console = StreamHandler(console_stream)
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter("%(colorlevel)s %(colormsg)s"))
    logging.root.addHandler(console)

    # Step 3: sync the deferred handler's buffered records out.
    deferred.sync_with_handlers(logging.root.handlers)
    output = console_stream.getvalue()
    assert "buffered message" in output
    assert "DEBUG" in output


def test_set_logging_options_dict_with_none():
    """
    Regression test for issue #68332.
    """
    set_logging_options_dict(None)


def test_setup_logging_with_unseeded_options():
    """
    Regression test for issue #68332.
    """
    with patch.object(set_logging_options_dict, "__options_dict__", None, create=True):
        setup_logging()


@pytest.fixture
def collected_records():
    """
    Attach a record-collecting handler to a logger of our own and yield the
    list it fills.

    A dedicated logger keeps these assertions off the root handlers that
    importing ``salt._logging.impl`` installs, so the record under test is
    unambiguously the one the test emitted.
    """
    records = []

    class Collector(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("tests.logging_extra")
    handler = Collector()
    logger.addHandler(handler)
    original_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        yield logger, records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)


def test_makerecord_passes_extra_to_the_record(collected_records):
    """
    Regression test for issue #70557.

    ``extra`` must reach the ``LogRecord``.
    """
    logger, records = collected_records
    logger.info("structured", extra={"cluster_id": "cluster-a"})
    assert len(records) == 1
    assert records[0].cluster_id == "cluster-a"


def test_makerecord_does_not_break_stack_info(collected_records):
    """
    Regression test for issue #70557.

    ``stack_info=True`` must populate ``record.stack_info`` and not raise.
    """
    logger, records = collected_records
    logger.info("with stack", stack_info=True)
    assert len(records) == 1
    assert records[0].stack_info

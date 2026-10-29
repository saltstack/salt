"""
Unit tests for :mod:`salt.utils.resource_warnings`.
"""

import logging
import warnings

import salt.utils.resource_warnings


def test_warn_until_close_emits_resource_warning_and_logs(caplog):
    """
    ``warn_until_close`` must emit a ``ResourceWarning`` *and* log at
    WARNING level.  The log record survives Python's default warnings
    filter (which drops ``ResourceWarning``) and is what makes leak
    signals visible in production Salt logs.
    """
    logger = logging.getLogger("salt.test.resource_warning")
    src = object()
    with warnings.catch_warnings(record=True) as caught, caplog.at_level(
        logging.WARNING, logger=logger.name
    ):
        warnings.simplefilter("always")
        salt.utils.resource_warnings.warn_until_close(
            "unclosed something-42", source=src, log=logger
        )

    # ResourceWarning emitted
    assert len(caught) == 1
    assert issubclass(caught[0].category, ResourceWarning)
    assert "unclosed something-42" in str(caught[0].message)
    assert caught[0].source is src

    # Log record also produced at WARNING level, same message
    matches = [r for r in caplog.records if "unclosed something-42" in r.getMessage()]
    assert matches, "message must appear in log records"
    assert matches[0].levelno == logging.WARNING


def test_warn_until_close_uses_module_logger_when_no_log_passed(caplog):
    """
    Missing ``log`` argument must fall back to
    ``salt.utils.resource_warnings``'s own logger.
    """
    with caplog.at_level(logging.WARNING, logger="salt.utils.resource_warnings"):
        salt.utils.resource_warnings.warn_until_close(
            "unclosed no-log-passed", source=object()
        )
    assert any("unclosed no-log-passed" in r.getMessage() for r in caplog.records)


def test_warn_until_close_swallows_warnings_module_failure(monkeypatch, caplog):
    """
    The helper is called from ``__del__`` finalizers -- it must not
    raise even if ``warnings.warn`` itself raises (which happens during
    interpreter shutdown when the ``warnings`` module has been torn
    down).  The log record must still be emitted.
    """

    def _bang(*args, **kwargs):
        raise RuntimeError("warnings module torn down")

    monkeypatch.setattr(salt.utils.resource_warnings.warnings, "warn", _bang)
    logger = logging.getLogger("salt.test.resource_warning.warn_fail")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        # Must not raise.
        salt.utils.resource_warnings.warn_until_close(
            "unclosed warnings-broken", source=object(), log=logger
        )
    assert any(
        "unclosed warnings-broken" in r.getMessage() for r in caplog.records
    ), "log must be produced even when warnings.warn raises"


def test_warn_until_close_swallows_log_failure(caplog):
    """
    Same finalizer-safety guarantee for the logging path.  If the
    passed logger raises, the call must return without propagating.
    """

    class _BrokenLogger:
        def warning(self, *args, **kwargs):
            raise RuntimeError("logger torn down")

    # Must not raise.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        salt.utils.resource_warnings.warn_until_close(
            "unclosed log-broken", source=object(), log=_BrokenLogger()
        )
    # ResourceWarning still emitted despite log failure.
    assert any("unclosed log-broken" in str(w.message) for w in caught)


def test_warn_until_close_accepts_custom_category():
    """
    ``category`` defaults to ``ResourceWarning`` but callers can pass
    another warning class (e.g. ``DeprecationWarning``) if they want to
    reuse the helper for a different signal.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        salt.utils.resource_warnings.warn_until_close(
            "custom-category test",
            source=object(),
            category=DeprecationWarning,
        )
    assert len(caught) == 1
    assert issubclass(caught[0].category, DeprecationWarning)

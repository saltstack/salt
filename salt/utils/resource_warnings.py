"""
Helpers for surfacing "unclosed resource" warnings through both Python's
``warnings`` module and Salt's logging pipeline.
"""

import logging
import warnings

_LOGGER = logging.getLogger(__name__)


def warn_until_close(message, source, category=ResourceWarning, log=None):
    """
    Emit ``category`` for an unclosed resource AND log the same message
    at WARNING level so it survives Python's default warnings filter.

    ``ResourceWarning`` is filtered out by Python's default warnings
    filter, so a bare ``warnings.warn(..., ResourceWarning)`` from a
    ``__del__`` finalizer is silently dropped in production.  Callers
    that missed a ``close()`` / ``destroy()`` / context-manager contract
    therefore never see the warning, and the leaked resource
    accumulates invisibly.

    (Concrete incident: after Salt commit ``0c3f53d9172`` removed the
    ``__del__``-based cleanup from ``SaltEvent`` / ``MasterMinion`` /
    ``RunnerClient`` / ``WheelClient`` in favor of a
    ``ResourceWarning``-emitting ``__del__``, out-of-tree consumers
    like SSEAPE that relied on GC-time cleanup via
    ``get_master_event(...).fire_event(...)`` began leaking one unix
    socket per fire-and-forget instance -- but the intended
    ``ResourceWarning`` was never visible because ``ResourceWarning`` is
    silenced by default in production Python.)

    Emitting a WARNING-level log record alongside the warning makes the
    leak visible in normal Salt logs regardless of the operator's
    warnings-filter setting.  Callers should pass their module-local
    ``log`` so records are attributed to the right module; the
    utility's own logger is the fallback.

    Called from ``__del__`` finalizers -- must never raise.
    """
    try:
        warnings.warn(message, category, source=source)
    except Exception:  # pylint: disable=broad-except
        # ``warnings.warn`` can raise during interpreter shutdown when
        # the ``warnings`` module has already been torn down.  A
        # finalizer must not propagate exceptions.
        pass
    try:
        (log or _LOGGER).warning(message)
    except Exception:  # pylint: disable=broad-except
        # Same rationale for the logging module.
        pass

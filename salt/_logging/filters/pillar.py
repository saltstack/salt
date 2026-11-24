"""
salt._logging.filters.pillar
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``PillarRedactingFilter`` — a ``logging.Filter`` that redacts every
pillar leaf value from outbound log records.

The operator opts in with a single config option::

    pillar_mask_output: True

That is the entire configuration surface. When False (the default),
the filter is a zero-cost passthrough. When True, every string,
bytes, int, and float leaf of the minion's pillar that is at least
``MIN_VALUE_LENGTH`` characters long is substituted with
``**********`` wherever it appears in ``record.msg`` or
``record.args``. The snapshot is rebuilt lazily when ``opts["pillar"]``
is reassigned (which happens on every pillar refresh).

The 4-character floor is a fixed internal limit, not a knob.
Redacting shorter values would corrupt too much log text to be
useful.
"""

from __future__ import annotations

import logging
import re
import sys
import threading

log = logging.getLogger(__name__)

REDACT_PLACEHOLDER = "**********"
MIN_VALUE_LENGTH = 4

# A value made only of these characters is an indent or a separator, not a
# secret, and redacting it would hit every line that has one.
SEPARATOR_CHARS = frozenset(" \t\r\n\f\v-_=.*#~+|/\\")

# Written in place of a message that could not be checked, so that a value is
# never written because the check failed.
WITHHELD = "[log message withheld: pillar redaction failed]"
_failure_reported = False

# Pillar values registered by the code that compiles the pillar, see register().
_registry_lock = threading.Lock()
_registered = set()
# Changes whenever a value is added, so that a filter knows to rebuild its regex.
_generation = 0


def _flatten_scalars(value, out):
    """Collect pillar leaf scalars (len >= MIN_VALUE_LENGTH) into ``out``."""
    if isinstance(value, bool):
        # bool is a subclass of int; skip — "True"/"False" collisions are
        # worse than useless.
        return
    if isinstance(value, dict):
        for v in value.values():
            _flatten_scalars(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            _flatten_scalars(v, out)
    elif isinstance(value, (str, bytes)):
        if not value:
            return
        s = value.decode(errors="replace") if isinstance(value, bytes) else value
        # A YAML ``|`` block ends with a newline that the log text does not
        # have, so the value is registered without surrounding whitespace.
        s = s.strip()
        if len(s) >= MIN_VALUE_LENGTH and not set(s) <= SEPARATOR_CHARS:
            out.append(s)
    elif isinstance(value, (int, float)):
        s = str(value)
        if len(s) >= MIN_VALUE_LENGTH:
            out.append(s)


def _report_failure(exc):
    """Say once, on stderr, that a record could not be redacted.

    This must not use logging: it runs inside a log handler. Only the type of
    the error is written, its text could contain a value.
    """
    global _failure_reported  # pylint: disable=global-statement
    if _failure_reported:
        return
    _failure_reported = True
    try:
        sys.stderr.write(
            f"salt: pillar redaction of a log record failed ({type(exc).__name__}); "
            "such messages are withheld\n"
        )
    except Exception:  # pylint: disable=broad-except
        pass


def register(pillar):
    """Add the leaf values of ``pillar`` to the values every filter redacts.

    ``setup_logging()`` gives a filter a frozen copy of the config that was
    made at start-up, when the pillar is still empty, so a filter cannot read
    a pillar that is compiled later. The code that compiles the pillar calls
    this instead. Values are only added, never dropped.

    This does not raise. If the values cannot be registered, a warning is
    logged.
    """
    global _generation  # pylint: disable=global-statement
    try:
        values = []
        _flatten_scalars(pillar, values)
        with _registry_lock:
            new = set(values) - _registered
            if new:
                _registered.update(new)
                _generation += 1
    except Exception as exc:  # pylint: disable=broad-except
        # Only the type of the error: its text could contain a value.
        log.warning(
            "Could not register the pillar values for log redaction (%s). "
            "Log output may contain them.",
            type(exc).__name__,
        )


def clear():
    """Forget the registered values."""
    global _generation, _failure_reported  # pylint: disable=global-statement
    with _registry_lock:
        _registered.clear()
        _generation += 1
    _failure_reported = False


class PillarRedactingFilter(logging.Filter):
    """Redact every pillar leaf value from outbound log records.

    Install with ``install_on_handler(handler, opts)``. The filter
    reads ``opts["pillar_mask_output"]`` and ``opts["pillar"]`` at
    construction time, and the values added with ``register()``. The
    snapshot is refreshed lazily when ``id(opts["pillar"])`` changes or a
    value is registered.
    """

    def __init__(self, opts=None):
        super().__init__()
        self._lock = threading.Lock()
        self._opts = opts or {}
        self._enabled = bool(self._opts.get("pillar_mask_output", False))
        self._regex = None
        self._snapshot_id = None
        self._snapshot_generation = None
        self._compile()

    def refresh(self):
        """Re-read opts and rebuild the pillar-value regex."""
        with self._lock:
            self._enabled = bool(self._opts.get("pillar_mask_output", False))
            self._compile()

    def _compile(self):
        pillar = self._opts.get("pillar") or {}
        values = []
        _flatten_scalars(pillar, values)
        with _registry_lock:
            values.extend(_registered)
            generation = _generation
        # De-dup; order longest-first so compound values redact before
        # their own prefixes would.
        uniq = sorted(set(values), key=len, reverse=True)
        if uniq:
            self._regex = re.compile("|".join(re.escape(v) for v in uniq))
        else:
            self._regex = None
        self._snapshot_id = id(pillar)
        self._snapshot_generation = generation

    def filter(self, record):
        # Fast path: feature off.
        if not self._enabled:
            return True
        try:
            # Opportunistic refresh if opts["pillar"] was rebound or a value
            # was registered.
            if (
                id(self._opts.get("pillar")) != self._snapshot_id
                or _generation != self._snapshot_generation
            ):
                self._compile()
            if self._regex is None:
                return True
            if isinstance(record.msg, str):
                record.msg = self._regex.sub(REDACT_PLACEHOLDER, record.msg)
            record.args = self._scrub(record.args)
        except Exception as exc:  # pylint: disable=broad-except
            # A bug in redaction must never silence logging, and it must not
            # let a message through that was not checked either: keep the
            # line and withhold the message.
            _report_failure(exc)
            record.msg, record.args = WITHHELD, ()
            return True
        return True

    def _scrub(self, obj):
        if self._regex is None or obj is None:
            return obj
        if isinstance(obj, str):
            return self._regex.sub(REDACT_PLACEHOLDER, obj)
        if isinstance(obj, bytes):
            return self._regex.sub(REDACT_PLACEHOLDER, obj.decode(errors="replace"))
        if isinstance(obj, dict):
            return {k: self._scrub(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return type(obj)(self._scrub(v) for v in obj)
        return obj


def install_on_handler(handler, opts):
    """Attach a ``PillarRedactingFilter`` to *handler*.

    Idempotent: if one is already attached, its opts snapshot is
    refreshed in place rather than double-installing.
    """
    if handler is None:
        return None
    for existing in handler.filters:
        if isinstance(existing, PillarRedactingFilter):
            existing._opts = opts or {}  # pylint: disable=protected-access
            existing.refresh()
            return existing
    flt = PillarRedactingFilter(opts)
    handler.addFilter(flt)
    return flt

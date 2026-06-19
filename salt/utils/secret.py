"""
Pillar masking: MaskedDict and MaskedList subclasses that store plain values
internally but redact them in their string representations.

Internal Salt operations (merge, msgpack, isinstance checks, Jinja) all work
on the plain stored values because MaskedDict is-a dict and MaskedList is-a list.
Only __repr__ / __str__ display redacted values.

Usage::

    from salt.utils.secret import hide, expose, serial, mask_output

    # Wrap pillar at the receive boundary (RemotePillarMixin.compile_pillar)
    opts["pillar"] = hide(compiled_pillar)

    # Access works normally — returns plain values
    value = opts["pillar"]["password"]           # "hunter2" (plain str)
    for k, v in opts["pillar"].items(): ...      # plain iteration

    # Repr/logging is masked
    log.debug("pillar: %s", opts["pillar"])      # {'password': '**********'}

    # Explicit output boundary (pillar.get CLI)
    serial(opts["pillar"]["password"])           # '**********'
    expose(opts["pillar"]["password"])           # 'hunter2'

    # Safety net for general output (output/__init__.py)
    mask_output(state_return_data)              # no-op for plain data
"""

from __future__ import annotations

import contextvars
import copy
import logging
from collections.abc import Mapping

log = logging.getLogger(__name__)

# When True (default), pillar output is masked. Template renderers set this to
# False so that SLS files receive plain values via salt["pillar.get"](…).
mask_pillar: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "mask_pillar", default=True
)

REDACT_PLACEHOLDER = "**********"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mask_wrap(value):
    """Wrap nested containers; leave scalar values (str, int, bool …) plain."""
    if isinstance(value, (MaskedDict, MaskedList)):
        return value
    if isinstance(value, dict):
        return MaskedDict(value)
    if isinstance(value, list):
        return MaskedList(value)
    return value


def _masked_repr(value) -> str:
    """Build a redacted repr string for a MaskedDict or MaskedList."""
    if isinstance(value, dict):
        pairs = ", ".join(f"{k!r}: {_masked_repr(v)}" for k, v in value.items())
        return "{" + pairs + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_masked_repr(v) for v in value) + "]"
    if isinstance(value, str) and value:
        return repr(REDACT_PLACEHOLDER)
    if isinstance(value, bytes) and value:
        return repr(REDACT_PLACEHOLDER.encode())
    if isinstance(value, (int, float, bool)) and value:
        return repr(REDACT_PLACEHOLDER)
    return repr(value)


# ---------------------------------------------------------------------------
# Public container types
# ---------------------------------------------------------------------------


class MaskedDict(dict):
    """A dict subclass whose __repr__ / __str__ redacts string leaf values.

    All standard dict operations (iteration, item access, isinstance checks,
    msgpack serialisation, dictupdate.merge) work on the plain stored values.
    Nested dicts and lists are automatically wrapped in MaskedDict / MaskedList.
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, _mask_wrap(value))

    def update(self, other=None, **kwargs):
        if other is not None:
            items = other.items() if isinstance(other, Mapping) else other
            for k, v in items:
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    def __repr__(self):
        if not mask_pillar.get():
            return dict.__repr__(self)
        return _masked_repr(self)

    def __str__(self):
        if not mask_pillar.get():
            return dict.__repr__(self)
        return _masked_repr(self)

    def __dict__(self):
        return self

    def copy(self):
        return MaskedDict(dict.copy(self))

    def __copy__(self):
        return self.copy()

    def __add__(self, other):
        return MaskedDict(dict.__add__(self, other))

    def __mul__(self, other):
        return MaskedDict(dict.__mul__(self, other))

    def __imul__(self, other):
        return MaskedDict(dict.__imul__(self, other))

    def __deepcopy__(self, memo):
        return MaskedDict({k: copy.deepcopy(v, memo) for k, v in dict.items(self)})

    def setdefault(self, key, default=None):
        return dict.setdefault(self, key, _mask_wrap(default))


class MaskedList(list):
    """A list subclass whose __repr__ / __str__ redacts string leaf values.

    All standard list operations work on plain stored values.
    Nested dicts and lists are automatically wrapped.
    """

    def __init__(self, iterable=()):
        super().__init__(_mask_wrap(v) for v in iterable)

    def __setitem__(self, idx, value):
        list.__setitem__(self, idx, _mask_wrap(value))

    def append(self, value):
        list.append(self, _mask_wrap(value))

    def extend(self, iterable):
        for v in iterable:
            self.append(v)

    def insert(self, idx, value):
        list.insert(self, idx, _mask_wrap(value))

    def __iadd__(self, iterable):
        self.extend(iterable)
        return self

    def __add__(self, other):
        return MaskedList(list.__add__(self, other))

    def __mul__(self, other):
        return MaskedList(list.__mul__(self, other))

    def __imul__(self, other):
        return MaskedList(list.__imul__(self, other))

    def __repr__(self):
        if not mask_pillar.get():
            return list.__repr__(self)
        return _masked_repr(self)

    def __str__(self):
        if not mask_pillar.get():
            return list.__repr__(self)
        return _masked_repr(self)

    def copy(self):
        return MaskedList(list.__iter__(self))

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, memo):
        return MaskedList(copy.deepcopy(v, memo) for v in list.__iter__(self))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def hide(value):
    """Wrap a pillar dict/list in MaskedDict/MaskedList for display masking.

    Scalar values (str, int, bool, None …) are returned unchanged — they are
    stored plain inside the container and only redacted in the container's repr.
    Already-wrapped values are returned as-is (idempotent).
    """
    return _mask_wrap(value)


def expose(value, _seen=None):
    """Recursively unwrap MaskedDict / MaskedList to plain Python types.

    Use at ``unmask=True`` pillar output boundaries so callers receive the
    real values (e.g. ``pillar.get(key, unmask=True)``).
    """
    if isinstance(value, MaskedDict):
        if _seen is None:
            _seen = set()
        vid = id(value)
        if vid in _seen:
            return value
        _seen.add(vid)
        try:
            return {k: expose(v, _seen) for k, v in dict.items(value)}
        finally:
            _seen.discard(vid)
    if isinstance(value, MaskedList):
        if _seen is None:
            _seen = set()
        vid = id(value)
        if vid in _seen:
            return value
        _seen.add(vid)
        try:
            return [expose(v, _seen) for v in list.__iter__(value)]
        finally:
            _seen.discard(vid)
    return value


def serial(value, _seen=None):
    """Aggressively redact: replace ALL non-empty strings with REDACT_PLACEHOLDER.

    Use at explicit pillar output boundaries (``pillar.get``, ``pillar.items``,
    ``pillar.item``, ``pillar.ext``) and inside ``no_log_mask``.

    Because ``MaskedDict.__getitem__`` returns plain strings (the scalar leaves
    are stored unwrapped), this function must handle plain str/dict/list values
    in addition to MaskedDict / MaskedList containers.
    """
    if _seen is None:
        _seen = set()
    if isinstance(value, str) and value:
        return REDACT_PLACEHOLDER
    if not isinstance(value, (dict, list)):
        # int, float, bool, None, empty string, bytes — pass through
        return value
    vid = id(value)
    if vid in _seen:
        return value
    _seen.add(vid)
    try:
        if isinstance(value, dict):
            return {
                k: serial(v, _seen)
                for k, v in (
                    dict.items(value)
                    if isinstance(value, MaskedDict)
                    else value.items()
                )
            }
        return [
            serial(v, _seen)
            for v in (
                list.__iter__(value) if isinstance(value, MaskedList) else iter(value)
            )
        ]
    finally:
        _seen.discard(vid)


def mask_output(value, _seen=None):
    """Gently redact: only redact values *inside* MaskedDict / MaskedList containers.

    Plain dicts, plain lists, and plain scalars pass through unchanged.
    Use as a safety net in ``output/__init__.py`` to prevent accidental pillar
    leakage in general Salt output without redacting ordinary result strings
    (state comments, module names, etc.).
    """
    if _seen is None:
        _seen = set()
    if isinstance(value, (MaskedDict, MaskedList)):
        # Hand off to serial() which fully redacts the masked container
        return serial(value, _seen)
    if not isinstance(value, (dict, list)):
        return value
    vid = id(value)
    if vid in _seen:
        return value
    _seen.add(vid)
    try:
        if isinstance(value, dict):
            return {k: mask_output(v, _seen) for k, v in value.items()}
        return [mask_output(v, _seen) for v in value]
    finally:
        _seen.discard(vid)


def no_log_mask(state_ret):
    """Replace ``comment`` and ``changes`` in a state return with redacted values.

    Called by ``salt/state.py`` when a state has ``no_log: True``.
    Mutates *state_ret* in place.
    """
    state_ret["comment"] = serial(state_ret["comment"])
    state_ret["changes"] = serial(state_ret["changes"])

"""
Pillar containers that wrap string/bytes leaves with Pydantic SecretStr/SecretBytes
and use SafeDict/SafeList so later mutations stay protected.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Iterable
from typing import Any

from pydantic import SecretBytes, SecretStr

# ``SecretStr`` / ``SecretBytes`` are imported here only; other code should use
# these names from this module for ``isinstance`` checks (single import surface).

log = logging.getLogger(__name__)

REDACT_PLACEHOLDER = "**********"


def _morph_leaf(value: Any) -> Any:
    """
    Morph a leaf value into a secret-safe container.
    Args:
        value: The value to morph.
    Returns:
        The morphed value.
    """
    if value is None or isinstance(value, (bool, int, float)):
        return value
    elif isinstance(value, SecretStr):
        return value
    elif isinstance(value, SecretBytes):
        return value
    elif isinstance(value, str):
        return SecretStr(value)
    elif isinstance(value, bytes):
        return SecretBytes(value)
    elif isinstance(value, SafeDict):
        return value
    elif isinstance(value, dict):
        return wrap_pillar_tree(value)
    elif isinstance(value, SafeList):
        return value
    elif isinstance(value, set):
        try:
            ordered = sorted(value, key=repr)
        except TypeError:
            ordered = list(value)
        return SafeList(_morph_leaf(x) for x in ordered)
    elif isinstance(value, Iterable):
        return SafeList(_morph_leaf(x) for x in value)
    else:
        return value


class SafeDict(dict):
    """
    Dict that morphs assigned values into secret-safe containers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        if key == "_errors":
            super().__setitem__(key, copy.deepcopy(value))
            return
        super().__setitem__(key, _morph_leaf(value))

    def update(self, *args, **kwargs):  # pylint: disable=arguments-differ
        other = dict(*args, **kwargs)
        for k, v in other.items():
            self[k] = v

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]


class SafeList(list):
    """
    List that morphs appended/inserted values into secret-safe containers.
    """

    def __init__(self, iterable=()):
        super().__init__()
        for item in iterable:
            self.append(item)

    def append(self, item):
        super().append(_morph_leaf(item))

    def extend(self, iterable):
        for item in iterable:
            self.append(item)

    def insert(self, index, item):
        super().insert(index, _morph_leaf(item))

    def __setitem__(self, index, item):
        if isinstance(index, slice):
            if isinstance(item, (list, tuple, SafeList)):
                super().__setitem__(index, [_morph_leaf(x) for x in item])
            else:
                super().__setitem__(index, _morph_leaf(item))
        else:
            super().__setitem__(index, _morph_leaf(item))

    def __iadd__(self, other):
        self.extend(other)
        return self


def wrap_pillar_tree(obj: Any) -> Any:
    """
    Convert a plain pillar structure into SafeDict / SafeList / Secret* leaves.
    Idempotent for already-wrapped structures.
    """
    if isinstance(obj, SafeDict):
        return obj
    if isinstance(obj, dict):
        out = SafeDict()
        for k, v in obj.items():
            out[k] = v
        return out
    if isinstance(obj, (list, tuple)):
        return SafeList(_morph_leaf(x) for x in obj)
    return _morph_leaf(obj)


def unwrap_pillar_tree(obj: Any) -> Any:
    """
    Convert back to plain dict/list/str/bytes for serialization (e.g. pillar cache).
    """
    if isinstance(obj, dict):
        plain = {}
        for k, v in obj.items():
            plain[k] = unwrap_pillar_tree(v)
        return plain
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    if isinstance(obj, SecretBytes):
        return obj.get_secret_value()
    if isinstance(obj, SafeList) or isinstance(obj, list):
        return [unwrap_pillar_tree(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(unwrap_pillar_tree(x) for x in obj)
    if isinstance(obj, set):
        return {unwrap_pillar_tree(x) for x in obj}
    return obj


def unwrap_blackout_whitelist(whitelist: Any) -> list:
    """
    Normalize ``minion_blackout_whitelist`` for ``str in whitelist`` checks.

    Pillar string leaves may be :class:`pydantic.SecretStr`; comparing a job's
    ``function_name`` (a ``str``) with ``x not in whitelist`` would otherwise
    fail because ``SecretStr`` does not compare equal to ``str``.
    """
    if not whitelist:
        return []
    unwrapped = unwrap_pillar_tree(whitelist)
    if isinstance(unwrapped, (list, tuple)):
        return list(unwrapped)
    return [unwrapped]


def _pillar_key_marks_sensitive(key: str) -> bool:
    """
    True if a pillar dict key (any depth) indicates sensitive subtree/values.

    All string leaves are wrapped with SecretStr for in-memory masking, but only
    values under these keys should be treated as cross-field redaction literals;
    otherwise public paths and identifiers (e.g. ``target-path``, beacon names)
    corrupt state output when substring-replaced in comments and diffs.
    """
    lk = str(key).lower().replace("-", "_")
    if lk in (
        "password",
        "passwords",
        "passwd",
        "pwd",
        "pw",
        "secret",
        "secrets",
        "token",
        "tokens",
        "credential",
        "credentials",
        "passphrase",
        "private_key",
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "client_secret",
        "signing_key",
        "encryption_key",
        "auth_token",
    ):
        return True
    for suf in ("_password", "_secret", "_token", "_passwd", "_pwd"):
        if lk.endswith(suf):
            return True
    for pref in ("password_", "secret_", "token_"):
        if lk.startswith(pref):
            return True
    if lk.endswith("_key") or lk.endswith("_token"):
        return True
    return False


def iter_pillar_secret_literals(pillar: Any) -> list[str]:
    """
    Collect secret string and bytes-as-utf8 literals from a (possibly wrapped) pillar.

    Only values under pillar keys that indicate credentials (see
    :func:`_pillar_key_marks_sensitive`) are included. Other wrapped strings
    (paths, IDs, public config) are excluded so return redaction does not damage
    structured output.
    """
    found: list[str] = []

    def walk(node, parent_sensitive: bool = False):
        if node is None:
            return
        if isinstance(node, SecretStr):
            if parent_sensitive:
                found.append(node.get_secret_value())
            return
        if isinstance(node, SecretBytes):
            if parent_sensitive:
                try:
                    found.append(node.get_secret_value().decode("utf-8"))
                except UnicodeDecodeError:
                    found.append(repr(node.get_secret_value()))
            return
        if isinstance(node, (SafeDict, dict)):
            for k, v in node.items():
                if k == "_errors":
                    continue
                child_sensitive = parent_sensitive or _pillar_key_marks_sensitive(
                    str(k)
                )
                walk(v, child_sensitive)
            return
        if isinstance(node, (SafeList, list, tuple)):
            for item in node:
                walk(item, parent_sensitive)
            return
        if isinstance(node, set):
            for item in node:
                walk(item, parent_sensitive)

    walk(pillar)
    # Longest first to avoid partial leaks when one secret is a substring of another
    return sorted(set(found), key=len, reverse=True)


def redact_known_literals(
    obj: Any, literals: list[str], placeholder: str = REDACT_PLACEHOLDER
) -> Any:
    """
    Deep-copy and replace known substrings in strings inside dict/list/tuple structures.
    """
    if not literals:
        return copy.deepcopy(obj) if obj is not None else obj

    def redact_str(text: str) -> str:
        out = text
        for lit in literals:
            if lit:
                out = out.replace(lit, placeholder)
        return out

    def walk(node):
        if isinstance(node, str):
            return redact_str(node)
        if isinstance(node, bytes):
            try:
                s = node.decode("utf-8")
            except UnicodeDecodeError:
                return node
            return redact_str(s).encode("utf-8")
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            t = type(node)
            return t(walk(x) for x in node)
        return node

    return walk(copy.deepcopy(obj))


def apply_no_log_mask(ret: dict[str, Any]) -> None:
    """
    Replace comment and changes in a state return dict when no_log is enabled.
    Mutates ret in place.
    """
    ret["comment"] = REDACT_PLACEHOLDER
    ret["changes"] = {REDACT_PLACEHOLDER: REDACT_PLACEHOLDER}

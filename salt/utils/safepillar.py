"""
Pillar containers that wrap string/bytes leaves with Pydantic SecretStr/SecretBytes
and use SafeDict/SafeList so later mutations stay protected.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from pydantic import SecretBytes, SecretStr

log = logging.getLogger(__name__)

REDACT_PLACEHOLDER = "**********"


def _morph_leaf(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, SecretStr):
        return value
    if isinstance(value, SecretBytes):
        return value
    if isinstance(value, str):
        return SecretStr(value)
    if isinstance(value, bytes):
        return SecretBytes(value)
    if isinstance(value, SafeDict):
        return value
    if isinstance(value, dict):
        return wrap_pillar_tree(value)
    if isinstance(value, SafeList):
        return value
    if isinstance(value, (list, tuple)):
        return SafeList(_morph_leaf(x) for x in value)
    if isinstance(value, set):
        try:
            ordered = sorted(value, key=repr)
        except TypeError:
            ordered = list(value)
        return SafeList(_morph_leaf(x) for x in ordered)
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


def iter_pillar_secret_literals(pillar: Any) -> list[str]:
    """
    Collect all secret string and bytes-as-utf8 literals from a (possibly wrapped) pillar.
    """
    found: list[str] = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, SecretStr):
            found.append(node.get_secret_value())
            return
        if isinstance(node, SecretBytes):
            try:
                found.append(node.get_secret_value().decode("utf-8"))
            except UnicodeDecodeError:
                found.append(repr(node.get_secret_value()))
            return
        if isinstance(node, (SafeDict, dict)):
            for k, v in node.items():
                if k == "_errors":
                    continue
                walk(v)
            return
        if isinstance(node, (SafeList, list, tuple)):
            for item in node:
                walk(item)
            return
        if isinstance(node, set):
            for item in node:
                walk(item)

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

"""
Helpers for Tornado compatibility in Salt.

This module centralizes patterns and docstrings that would otherwise include
backslashes (for example ``\d``), which can trigger SyntaxWarning in Python
3.12+ if they appear in non-raw string literals.
"""

import re

import salt.utils.stringutils

RE_UNESCAPE_DOC = salt.utils.stringutils.build_docstring(
    r"""
    Unescape a string escaped by ``re.escape``.

    May raise ``ValueError`` for regular expressions which could not have been
    produced by ``re.escape`` (for example, strings containing ``\d`` cannot be
    unescaped).
    """
)

RE_UNESCAPE_PATTERN = re.compile(r"\\(.)")


def _re_unescape_replacement(match):
    return match.group(1)


def re_unescape(value):
    return RE_UNESCAPE_PATTERN.sub(_re_unescape_replacement, value)


re_unescape.__doc__ = RE_UNESCAPE_DOC

__all__ = ["RE_UNESCAPE_DOC", "RE_UNESCAPE_PATTERN", "re_unescape"]


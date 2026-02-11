"""
Minimal Tornado util subset shipped with Salt.

We keep a tiny ``re_unescape`` implementation here for bundled builds and to
avoid SyntaxWarning on Python 3.12+ caused by invalid escape sequences in
docstrings.
"""

import salt.utils.tornado as tornado_utils

RE_UNESCAPE_PATTERN = tornado_utils.RE_UNESCAPE_PATTERN


def re_unescape(value):
    return tornado_utils.re_unescape(value)


re_unescape.__doc__ = tornado_utils.RE_UNESCAPE_DOC

__all__ = ["RE_UNESCAPE_PATTERN", "re_unescape"]


# -*- coding: utf-8 -*-
'''
Helpful generators and other tools
'''

# Import python libs
from __future__ import absolute_import
import re


def split(orig, sep=None):
    '''
    Generator function for iterating through large strings, particularly useful
    as a replacement for str.splitlines().

    See http://stackoverflow.com/a/3865367
    '''
    exp = re.compile(r'\s+' if sep is None else re.escape(sep))
    pos = 0
    length = len(orig)
    while True:
        match = exp.search(orig, pos)
        if not match:
            if pos < length or sep is not None:
                val = orig[pos:]
                if val:
                    # Only yield a value if the slice was not an empty string,
                    # because if it is then we've reached the end. This keeps
                    # us from yielding an extra blank value at the end.
                    yield val
            break
        if pos < match.start() or sep is not None:
            yield orig[pos:match.start()]
        pos = match.end()

# -*- coding: utf-8 -*-
'''
Helpful generators and other tools
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import fnmatch
import re

# Import Salt libs
import salt.utils.files


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


def read_file(fh_, chunk_size=1048576):
    '''
    Generator that reads chunk_size bytes at a time from a file/filehandle and
    yields it.
    '''
    try:
        if chunk_size != int(chunk_size):
            raise ValueError
    except ValueError:
        raise ValueError('chunk_size must be an integer')
    try:
        while True:
            try:
                chunk = fh_.read(chunk_size)
            except AttributeError:
                # Open the file and re-attempt the read
                fh_ = salt.utils.files.fopen(fh_, 'rb')  # pylint: disable=W8470
                chunk = fh_.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        try:
            fh_.close()
        except AttributeError:
            pass


def fnmatch_multiple(candidates, pattern):
    '''
    Convenience function which runs fnmatch.fnmatch() on each element of passed
    iterable. The first matching candidate is returned, or None if there is no
    matching candidate.
    '''
    # Make sure that candidates is iterable to avoid a TypeError when we try to
    # iterate over its items.
    try:
        candidates_iter = iter(candidates)
    except TypeError:
        return None

    for candidate in candidates_iter:
        try:
            if fnmatch.fnmatch(candidate, pattern):
                return candidate
        except TypeError:
            pass
    return None

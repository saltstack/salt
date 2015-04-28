# -*- coding: utf-8 -*-
'''
the locale utils used by salt
'''

import sys
import locale

from salt.ext.six import string_types
from salt.utils.decorators import memoize as real_memoize


@real_memoize
def get_encodings():
    '''
    return a list of string encodings to try
    '''
    encodings = []

    try:
        loc_enc = locale.getdefaultlocale()[-1]
    except (ValueError, IndexError):  # system locale is nonstandard or malformed
        loc_enc = None
    if loc_enc:
        encodings.append(loc_enc)

    try:
        sys_enc = sys.getdefaultencoding()
    except ValueError:  # system encoding is nonstandard or malformed
        sys_enc = None
    if sys_enc:
        encodings.append(sys_enc)

    for enc in ['utf-8', 'latin-1']:
        if enc not in encodings:
            encodings.append(enc)

    return encodings


def sdecode(string_):
    '''
    Since we don't know where a string is coming from and that string will
    need to be safely decoded, this function will attempt to decode the string
    until if has a working string that does not stack trace
    '''
    if not isinstance(string_, string_types):
        return string_
    encodings = get_encodings()
    for encoding in encodings:
        try:
            decoded = string_.decode(encoding)
            # Make sure unicode string ops work
            u' ' + decoded  # pylint: disable=W0104
            return decoded
        except UnicodeDecodeError:
            continue
    return string_

# -*- coding: utf-8 -*-
'''
the locale utils used by salt
'''

from __future__ import absolute_import

import sys

import salt.utils
import salt.ext.six as six
from salt.utils.decorators import memoize as real_memoize


@real_memoize
def get_encodings():
    '''
    return a list of string encodings to try
    '''
    encodings = [__salt_system_encoding__]

    try:
        sys_enc = sys.getdefaultencoding()
    except ValueError:  # system encoding is nonstandard or malformed
        sys_enc = None
    if sys_enc and sys_enc not in encodings:
        encodings.append(sys_enc)

    for enc in ['utf-8', 'latin-1']:
        if enc not in encodings:
            encodings.append(enc)

    return encodings


def sdecode(string_):
    '''
    Since we don't know where a string is coming from and that string will
    need to be safely decoded, this function will attempt to decode the string
    until it has a working string that does not stack trace
    '''
    encodings = get_encodings()
    for encoding in encodings:
        try:
            decoded = salt.utils.to_unicode(string_, encoding)
            if isinstance(decoded, six.string_types):
                # Make sure unicode string ops work
                u' ' + decoded  # pylint: disable=W0104
            return decoded
        except UnicodeDecodeError:
            continue
    return string_


def sdecode_if_string(value_):
    '''
    If the value is a string, run sdecode() on it to ensure it is parsed
    properly. If it is not a string, return it as-is
    '''
    if isinstance(value_, six.string_types):
        value_ = sdecode(value_)
    return value_


def split_locale(loc):
    '''
    Split a locale specifier.  The general format is

    language[_territory][.codeset][@modifier] [charmap]

    For example:

    ca_ES.UTF-8@valencia UTF-8
    '''
    def split(st, char):
        '''
        Split a string `st` once by `char`; always return a two-element list
        even if the second element is empty.
        '''
        split_st = st.split(char, 1)
        if len(split_st) == 1:
            split_st.append('')
        return split_st

    comps = {}
    work_st, comps['charmap'] = split(loc, ' ')
    work_st, comps['modifier'] = split(work_st, '@')
    work_st, comps['codeset'] = split(work_st, '.')
    comps['language'], comps['territory'] = split(work_st, '_')
    return comps


def join_locale(comps):
    '''
    Join a locale specifier split in the format returned by split_locale.
    '''
    loc = comps['language']
    if comps.get('territory'):
        loc += '_' + comps['territory']
    if comps.get('codeset'):
        loc += '.' + comps['codeset']
    if comps.get('modifier'):
        loc += '@' + comps['modifier']
    if comps.get('charmap'):
        loc += ' ' + comps['charmap']
    return loc


def normalize_locale(loc):
    '''
    Format a locale specifier according to the format returned by `locale -a`.
    '''
    comps = split_locale(loc)
    comps['territory'] = comps['territory'].upper()
    comps['codeset'] = comps['codeset'].lower().replace('-', '')
    comps['charmap'] = ''
    return join_locale(comps)


def decode_recursively(object_):
    if isinstance(object_, list):
        return [decode_recursively(o) for o in object_]
    if isinstance(object_, tuple):
        return tuple([decode_recursively(o) for o in object_])
    if isinstance(object_, dict):
        return dict([(decode_recursively(key), decode_recursively(value))
                     for key, value in salt.ext.six.iteritems(object_)])
    elif isinstance(object_, six.string_types):
        return sdecode(object_)
    else:
        return object_

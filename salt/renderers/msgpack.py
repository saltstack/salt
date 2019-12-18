# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

# Import third party libs
import msgpack

# Import salt libs
from salt.ext import six


def render(msgpack_data, saltenv='base', sls='', **kws):
    '''
    Accepts a message pack string or a file object, renders said data back to
    a python dict.

    .. note:
        This renderer is NOT intended for use in creating sls files by hand,
        but exists to allow for data backends to serialize the highdata
        structure in an easily transportable way. This is to allow for more
        fluid fileserver backends that rely on pure data sources.

    :rtype: A Python data structure
    '''
    if not isinstance(msgpack_data, six.string_types):
        msgpack_data = msgpack_data.read()

    if msgpack_data.startswith('#!'):
        msgpack_data = msgpack_data[(msgpack_data.find('\n') + 1):]
    if not msgpack_data.strip():
        return {}
    return msgpack.loads(msgpack_data)

# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Import third party libs
import msgpack


def render(msgpack_data, saltenv='base', sls='', **kws):
    '''
    Accepts JSON as a string or as a file object and runs it through the JSON
    parser.

    :rtype: A Python data structure
    '''
    if not isinstance(msgpack_data, basestring):
        msgpack_data = msgpack_data.read()

    if msgpack_data.startswith('#!'):
        msgpack_data = msgpack_data[(msgpack_data.find('\n') + 1):]
    if not msgpack_data.strip():
        return {}
    return msgpack.loads(msgpack_data)

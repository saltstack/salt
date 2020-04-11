# -*- coding: utf-8 -*-
"""
Helper functions for transport components to handle message framing
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.msgpack
from salt.ext import six


def frame_msg(body, header=None, raw_body=False):  # pylint: disable=unused-argument
    """
    Frame the given message with our wire protocol
    """
    framed_msg = {}
    if header is None:
        header = {}

    framed_msg["head"] = header
    framed_msg["body"] = body
    return salt.utils.msgpack.dumps(framed_msg)


def frame_msg_ipc(body, header=None, raw_body=False):  # pylint: disable=unused-argument
    """
    Frame the given message with our wire protocol for IPC

    For IPC, we don't need to be backwards compatible, so
    use the more efficient "use_bin_type=True" on Python 3.
    """
    framed_msg = {}
    if header is None:
        header = {}

    framed_msg["head"] = header
    framed_msg["body"] = body
    if six.PY2:
        return salt.utils.msgpack.dumps(framed_msg)
    else:
        return salt.utils.msgpack.dumps(framed_msg, use_bin_type=True)


def _decode_embedded_list(src):
    """
    Convert enbedded bytes to strings if possible.
    List helper.
    """
    output = []
    for elem in src:
        if isinstance(elem, dict):
            elem = _decode_embedded_dict(elem)
        elif isinstance(elem, list):
            elem = _decode_embedded_list(elem)
        elif isinstance(elem, bytes):
            try:
                elem = elem.decode()
            except UnicodeError:
                pass
        output.append(elem)
    return output


def _decode_embedded_dict(src):
    """
    Convert enbedded bytes to strings if possible.
    Dict helper.
    """
    output = {}
    for key, val in six.iteritems(src):
        if isinstance(val, dict):
            val = _decode_embedded_dict(val)
        elif isinstance(val, list):
            val = _decode_embedded_list(val)
        elif isinstance(val, bytes):
            try:
                val = val.decode()
            except UnicodeError:
                pass
        if isinstance(key, bytes):
            try:
                key = key.decode()
            except UnicodeError:
                pass
        output[key] = val
    return output


def decode_embedded_strs(src):
    """
    Convert enbedded bytes to strings if possible.
    This is necessary because Python 3 makes a distinction
    between these types.

    This wouldn't be needed if we used "use_bin_type=True" when encoding
    and "encoding='utf-8'" when decoding. Unfortunately, this would break
    backwards compatibility due to a change in wire protocol, so this less
    than ideal solution is used instead.
    """
    if not six.PY3:
        return src

    if isinstance(src, dict):
        return _decode_embedded_dict(src)
    elif isinstance(src, list):
        return _decode_embedded_list(src)
    elif isinstance(src, bytes):
        try:
            return src.decode()
        except UnicodeError:
            return src
    else:
        return src

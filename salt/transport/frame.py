"""
Helper functions for transport components to handle message framing
"""

import struct

import salt.utils.msgpack


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
    Frame the given message with our wire protocol for IPC.

    Prefixes the msgpack payload with a 4-byte big-endian length so the
    receiver can read exactly the right number of bytes per message.  This
    prevents msgpack stream corruption when concurrent large writes exceed
    the Unix socket PIPE_BUF atomic-write boundary (~65 536 bytes on Linux),
    which caused interleaved bytes and UnicodeDecodeError / ExtraData crashes
    in subscribers such as EventReturn under high event-bus load.
    """
    framed_msg = {}
    if header is None:
        header = {}

    framed_msg["head"] = header
    framed_msg["body"] = body
    payload = salt.utils.msgpack.dumps(framed_msg, use_bin_type=True)
    return struct.pack(">I", len(payload)) + payload


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
    for key, val in src.items():
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

# -*- coding: utf-8 -*-
'''
Helper functions for transport components to handle message framing
'''
# Import python libs
from __future__ import absolute_import
import msgpack


def frame_msg(body, header=None, raw_body=False):
    '''
    Frame the given message with our wire protocol
    '''
    framed_msg = {}
    if header is None:
        header = {}

    framed_msg['head'] = header
    framed_msg['body'] = body
    return msgpack.dumps(framed_msg)

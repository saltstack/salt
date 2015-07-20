# -*- coding: utf-8 -*-
'''
Helper functions for transport components to handle message framing
'''
# Import python libs
from __future__ import absolute_import

# Import 3rd-party libs
import msgpack
import salt.ext.six as six


# TODO: remove raw_body??
def frame_msg(body, header=None, raw_body=False):
    '''
    Frame the given message with our wire protocol
    '''
    framed_msg = {}
    if header is None:
        header = {}

    # if the body wasn't already msgpacked-- lets do that.
    if not raw_body:
        body = msgpack.dumps(body)

    framed_msg['head'] = header
    framed_msg['body'] = body
    framed_msg_packed = msgpack.packb(framed_msg)
    msg = six.b('{0} '.format(len(framed_msg_packed)))
    msg += framed_msg_packed
    return msg

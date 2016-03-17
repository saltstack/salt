# -*- coding: utf-8 -*-
'''
Run remote execution commands via the local client
'''
# import python libs
from __future__ import absolute_import

# Import salt libs
import salt.client


def cmd(
        name,
        tgt,
        fun,
        arg=(),
        tgt_type='glob',
        ret='',
        kwarg=None,
        **kwargs):
    '''
    Execute a remote execution command
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    local = salt.client.get_local_client(mopts=__opts__)
    jid = local.cmd_async(
                          tgt,
                          fun,
                          arg,
                          expr_form=tgt_type,
                          ret=ret,
                          kwarg=kwarg,
                          **kwargs
                          )
    ret['changes']['jid'] = jid
    return ret

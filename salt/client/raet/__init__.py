# -*- coding: utf-8 -*-
'''
The client libs to communicate with the salt master when running raet
'''

# Import python libs
import os
import time
import logging

# Import Salt libs
from raet import raeting
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard
import salt.config
import salt.client
import salt.utils
import salt.syspaths as syspaths

log = logging.getLogger(__name__)


class LocalClient(salt.client.LocalClient):
    '''
    The RAET LocalClient
    '''
    def __init__(self,
                 c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
                 mopts=None):

        #import  wingdbstub
        salt.client.LocalClient.__init__(self, c_path, mopts)

    def pub(self,
            tgt,
            fun,
            arg=(),
            expr_form='glob',
            ret='',
            jid='',
            timeout=5,
            **kwargs):
        '''
        Publish the command!
        '''
        payload_kwargs = self._prep_pub(
                tgt,
                fun,
                arg=arg,
                expr_form=expr_form,
                ret=ret,
                jid=jid,
                timeout=timeout,
                **kwargs)
        yid = salt.utils.gen_jid()
        stack = LaneStack(
                yid=yid,
                lanename='master',
                sockdirpath=self.opts['sock_dir'])
        stack.Pk = raeting.packKinds.pack
        router_yard = RemoteYard(
                lanename='master',
                yid=0,
                dirpath=self.opts['sock_dir'])
        stack.addRemote(router_yard)
        route = {'dst': (None, router_yard.name, 'local_cmd'),
                 'src': (None, stack.local.name, None)}
        msg = {'route': route, 'load': payload_kwargs}
        stack.transmit(msg)
        stack.serviceAll()
        while True:
            time.sleep(0.01)
            stack.serviceAll()
            for msg in stack.rxMsgs:
                return msg.get('return', {}).get('ret', {})

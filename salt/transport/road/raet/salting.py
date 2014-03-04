# -*- coding: utf-8 -*-
'''
behaving.py raet ioflo behaviors

See raeting.py for data format and packet field details.

Layout in DataStore


raet.udp.stack.stack
    value StackUdp
raet.udp.stack.txmsgs
    value deque()
raet.udp.stack.rxmsgs
    value deque()
raet.udp.stack.local
    name host port sigkey prikey
raet.udp.stack.status
    joined allowed idle
raet.udp.stack.destination
    value deid


'''
# pylint: skip-file
# pylint: disable=W0611

# Import Python libs
from collections import deque
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base.globaling import *

from ioflo.base import aiding
from ioflo.base import storing
from ioflo.base import deeding

from ioflo.base.consoling import getConsole
console = getConsole()

from . import raeting, packeting, stacking, estating


class JoinerStackUdpRaetSalt(deeding.Deed):  # pylint: disable=W0232
    '''
    Initiates join transaction with master
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        masterhost='.salt.etc.master',
        masterport='.salt.etc.master_port', )

    def postinitio(self):
        self.mha = (self.masterhost.value, int(self.masterport.value))

    def action(self, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        stack = self.stack.value
        if stack and isinstance(stack, stacking.StackUdp):
            stack.join(mha=self.mha)


# -*- coding: utf-8 -*-
'''
RAET transport classes
'''

from __future__ import absolute_import
import time

# Import Salt Libs
import logging

from salt.utils import kinds
from salt.transport.client import ReqChannel

log = logging.getLogger(__name__)

try:
    from raet import raeting, nacling
    from raet.lane.stacking import LaneStack
    from raet.lane.yarding import RemoteYard
except (ImportError, OSError):
    # Don't die on missing transport libs since only one transport is required
    pass

# Module globals for default LaneStack. Because RAETReqChannels are created on demand
# they do not have access to the master estate that motivated their creation
# Also in Raet a LaneStack can be shared shared by all channels in a given jobber
# For these reasons module globals are used to setup a shared jobber_stack as
# well has routing information for the master that motivated the jobber
# when a channel is not used in a jobber context then a LaneStack is created
# on demand.

jobber_stack = None  # module global that holds raet jobber LaneStack
jobber_rxMsgs = {}  # dict of deques one for each RAETReqChannel for the jobber
jobber_estate_name = None  # module global of motivating master estate name
jobber_yard_name = None  # module global of motivating master yard name


class RAETReqChannel(ReqChannel):
    '''
    Build the communication framework to communicate over the local process
    uxd socket and send messages forwarded to the master. then wait for the
    relative return message.

    Two use cases:
        mininion to master communication, normal use case
           Minion is communicating via yard through minion Road to master
           The destination route needs the estate name of the associated master
        master call via runner, special use case
           In the special case the master call external process is communicating
           via a yard with the master manor yard
           The destination route estate is None to indicate local estate

        The difference between the two is how the destination route
        is assigned.
    '''

    def __init__(self, opts, usage=None, **kwargs):
        self.opts = opts
        self.ttype = 'raet'
        if usage == 'master_call':  # runner.py master_call
            self.dst = (None, None, 'local_cmd')
        else:  # everything else minion to master including salt-call
            self.dst = (jobber_estate_name or None,
                        jobber_yard_name or None,
                        'remote_cmd')
        self.stack = None
        self.ryn = 'manor'  # remote yard name

    def __prep_stack(self):
        '''
        Prepare the stack objects
        '''
        global jobber_stack
        if not self.stack:
            if jobber_stack:
                self.stack = jobber_stack
            else:
                self.stack = jobber_stack = self._setup_stack(ryn=self.ryn)
        log.debug("RAETReqChannel Using Jobber Stack at = {0}\n".format(self.stack.ha))

    def _setup_stack(self, ryn='manor'):
        '''
        Setup and return the LaneStack and Yard used by by channel when global
        not already setup such as in salt-call to communicate to-from the minion

        '''
        role = self.opts.get('id')
        if not role:
            emsg = ("Missing role(\'id\') required to setup RAETReqChannel.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        kind = self.opts.get('__role')  # application kind 'master', 'minion', etc
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for RAETReqChannel.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)
        if kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                    kinds.APPL_KIND_NAMES[kinds.applKinds.syndic]]:
            lanename = 'master'
        elif kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                      kinds.APPL_KIND_NAMES[kinds.applKinds.caller]]:
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application kind '{0}' for RAETReqChannel.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        name = 'channel' + nacling.uuid(size=18)
        stack = LaneStack(name=name,
                          lanename=lanename,
                          sockdirpath=self.opts['sock_dir'])

        stack.Pk = raeting.PackKind.pack
        stack.addRemote(RemoteYard(stack=stack,
                                   name=ryn,
                                   lanename=lanename,
                                   dirpath=self.opts['sock_dir']))
        log.debug("Created Channel Jobber Stack {0}\n".format(stack.name))
        return stack

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        '''
        We don't need to do the crypted_transfer_decode_dictentry routine for
        raet, just wrap send.
        '''
        return self.send(load, tries, timeout)

    def send(self, load, tries=3, timeout=60):
        '''
        Send a message load and wait for a relative reply
        One shot wonder
        '''
        self.__prep_stack()
        tried = 1
        start = time.time()
        track = nacling.uuid(18)
        src = (None, self.stack.local.name, track)
        self.route = {'src': src, 'dst': self.dst}
        msg = {'route': self.route, 'load': load}
        self.stack.transmit(msg, self.stack.nameRemotes[self.ryn].uid)
        while track not in jobber_rxMsgs:
            self.stack.serviceAll()
            while self.stack.rxMsgs:
                msg, sender = self.stack.rxMsgs.popleft()
                jobber_rxMsgs[msg['route']['dst'][2]] = msg
                continue
            if track in jobber_rxMsgs:
                break
            if time.time() - start > timeout:
                if tried >= tries:
                    raise ValueError("Message send timed out after '{0} * {1}'"
                             " secs. route = {2} track = {3} load={4}".format(tries,
                                                                       timeout,
                                                                       self.route,
                                                                       track,
                                                                       load))
                self.stack.transmit(msg, self.stack.nameRemotes['manor'].uid)
                tried += 1
            time.sleep(0.01)
        return jobber_rxMsgs.pop(track).get('return', {})

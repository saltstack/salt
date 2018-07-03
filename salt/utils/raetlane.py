# -*- coding: utf-8 -*-
'''
Provides RAET LaneStack interface for interprocess communications in Salt Raet
to a remote yard, default name for remote is 'manor' .

Usages are for RAETChannels and RAETEvents
This provides a single module global LaneStack to be shared by all users in
the same process. This combines into one stack the channel and event bus.

The module attributes:
    lane_rx_msgs
        is a dict of deques keyed by the destination share name
        recipients each value deque holds messages that were addressed
        to that share name

    lane_stack
        is the shared LaneStack object

    lane_estate_name
        is the motivating master estate name when applicable

    lane_yard_name
        is the motivating master yard name when applicable

    Because RaetChannels are created on demand
    they do not have access to the master estate that motivated their creation
    the module globals lane_estate_name and lane_yard_name are provided to setup
    so that channels using the routing information for the master that motivated the jobber
    when a channel is not used in a jobber context then a LaneStack is created
    on demand.

Example usage:

import raetlane

raetlane.prep()

track = nacling.uuid(18)
src = (None, 'localyardname', track)
dst = ('remotestackname', 'remoteyardname', 'remotesharename')
route = {'src': src, 'dst': dst}
msg = {'route': route, 'body': {}}

raetlane.transmit(msg)
raetlane.service()

msg = raetlane.wait(share=track, timeout=5.0)
if not msg:
   raise ValueError("Timed out out waiting for response")
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

try:
    from raet import raeting, nacling
    from raet.lane.stacking import LaneStack
    from raet.lane.yarding import RemoteYard
    HAS_RAET = True
except ImportError:
    HAS_RAET = False

if HAS_RAET:
    # pylint: disable=3rd-party-module-not-gated
    import time

    # Import Salt Libs

    import logging
    import salt.utils.kinds as kinds

    log = logging.getLogger(__name__)

    # Module globals for default shared LaneStack for a process.
    rx_msgs = {}  # module global dict of deques one for each receipient of msgs
    lane_stack = None  # module global that holds raet LaneStack
    remote_yard = None  # module global that holds raet remote Yard
    master_estate_name = None  # module global of motivating master estate name
    master_yard_name = None  # module global of motivating master yard name

    def prep(opts, ryn='manor'):
        '''
        required items in opts are keys
            'id'
            '__role'
            'sock_dir'

        ryn is the remote yard name to communicate with
        each use much call raetlane.prep() to ensure lanestack is setup
        '''
        if not lane_stack:
            _setup(opts=opts, ryn=ryn)

    def _setup(opts, ryn='manor'):
        '''
        Setup the LaneStack lane_stack and RemoteYard lane_remote_yard global
        '''
        global lane_stack, remote_yard  # pylint: disable=W0602

        role = opts.get('id')
        if not role:
            emsg = ("Missing role required to setup LaneStack.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        kind = opts.get('__role')  # application kind 'master', 'minion', etc
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for LaneStack.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)
        if kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                    kinds.APPL_KIND_NAMES[kinds.applKinds.syndic]]:
            lanename = 'master'
        elif kind == [kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                      kinds.APPL_KIND_NAMES[kinds.applKinds.caller]]:
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application kind '{0}' for LaneStack.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        name = 'lanestack' + nacling.uuid(size=18)
        lane_stack = LaneStack(name=name,
                          lanename=lanename,
                          sockdirpath=opts['sock_dir'])

        lane_stack.Pk = raeting.PackKind.pack.value
        log.debug(
            'Created new LaneStack and local Yard named %s at %s\n',
            lane_stack.name, lane_stack.ha
        )
        remote_yard = RemoteYard(stack=lane_stack,
                                 name=ryn,
                                 lanename=lanename,
                                 dirpath=opts['sock_dir'])
        lane_stack.addRemote(remote_yard)
        log.debug(
            'Added to LaneStack %s remote Yard named %s at %s\n',
            lane_stack.name, remote_yard.name, remote_yard.ha
        )

    def transmit(msg):
        '''
        Sends msg to remote_yard
        '''
        lane_stack.transmit(msg, remote_yard.uid)

    def service():
        '''
        Service the lane_stack and move any received messages into their associated
        deques in rx_msgs keyed by the destination share in the msg route dict
        '''
        lane_stack.serviceAll()
        while lane_stack.rxMsgs:
            msg, sender = lane_stack.rxMsgs.popleft()
            rx_msgs[msg['route']['dst'][2]] = msg

    def receive(share):
        '''
        Returns first message from deque at key given by share in rx_msgs if any
        otherwise returns None
        '''
        service()
        if share in rx_msgs:
            if rx_msgs[share]:
                return rx_msgs[share].popleft()
        return None

    def wait(share, timeout=0.0, delay=0.01):
        '''
        Blocks until receives a msg addressed to share or timeout
        Return msg or None if timed out
        Delay is sleep time between services
        '''
        start = time.time()
        while True:
            msg = receive(share)
            if msg:
                return msg
            time.sleep(delay)
            if timeout > 0.0 and (time.time() - start) >= timeout:
                return None

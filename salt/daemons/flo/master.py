# -*- coding: utf-8 -*-
'''
The behaviors to run the salt master via ioflo
'''

# Import python libs
from collections import deque

# Import salt libs
import salt.daemons.masterapi
from salt.transport.road.raet import stacking
from salt.transport.road.raet import yarding

# Import ioflo libs
import ioflo.base.deeding


@ioflo.base.deeding.deedify('master_keys', ioinits={'opts': '.salt.etc.opts', 'keys': '.salt.etc.keys.master'})
def master_keys(self):
    '''
    Return the master keys
    '''
    self.keys.value = salt.daemons.masterapi.master_keys(self.opts.value)


@ioflo.base.deeding.deedify('clean_old_jobs', ioinits={'opts': '.salt.etc.opts'})
def clean_old_jobs(self):
    '''
    Call the clan old jobs routine
    '''
    salt.daemons.masterapi.clean_old_jobs(self.opts.value)


@ioflo.base.deeding.deedify('access_keys', ioinits={'opts': '.salt.etc.opts'})
def access_keys(self):
    '''
    Build the access keys
    '''
    salt.daemons.masterapi.access_keys(self.opts.value)


@ioflo.base.deeding.deedify('fileserver_update', ioinits={'opts': '.salt.etc.opts'})
def fileserver_update(self):
    '''
    Update the fileserver backends
    '''
    salt.daemons.masterapi.fileserver_update(self.opts.value)


class UXDRouter(ioflo.base.deeding.Deed):
    '''
    Routes the communication in and out of uxd connections
    '''
    Ioinits = {'opts': '.salt.etc.opts',
               'event_yards': '.salt.uxd.yards.event',
               'com_yards': '.salt.uxd.yards.com',
               'local_cmd': '.salt.uxd.local_cmd',
               'local_ret': '.salt.uxd.local_ret',
               'events': '.salt.uxd.events',
               'stack': '.salt.uxd.stack.stack'}

    def __init__(self):
        ioflo.base.deeding.Deed.__init__(self)

    def postioinit(self):
        '''
        Set up required objects
        '''
        self.stack.value = stacking.StackUxd(
                name='router',
                lanename='com',
                yid=0,
                dirpath=self.opts.value['sock_dir'])
        self.event_yards.value = set()
        self.com_yards.value = set()
        self.local_cmd.value = deque()
        self.local_ret.value = deque()
        self.events.value = deque()

    def _register_event_yard(self, msg):
        '''
        register an incoming event request with the requesting yard id
        '''
        try:
            ev_yard = yarding.Yard(
                    yid=msg['load']['yid'],
                    prefix='com',
                    dirpath=msg['load']['dirpath'])
        except Exception:
            return
        self.stack.value.addRemoteYard(ev_yard)
        self.event_yards.value.add(ev_yard.name)

    def _fire_event(self, event):
        '''
        Fire an event to all subscribed yards
        '''
        for y_name in self.event_yards.value:
            route = {'src': ('router', self.stack.value.yard.name, None),
                     'dst': ('router', y_name, None)}
            msg = {'route': route, 'event': event}
            self.stack.value.transmit(msg)

    def _process_rxmsg(self, msg):
        '''
        Send the message to the correct location
        '''
        try:
            if msg['route']['src'][0] == 'router' and msg['route']['src'][2] == 'local_cmd':
                self.local_cmd.append(msg)
            elif msg['route']['src'][0] == 'router' and msg['route']['src'][2] == 'event_req':
                # Register the event interface
                self._register_event_yard(msg)
        except Exception:
            return

    def action(self):
        '''
        Process the messages!
        '''
        self.stack.value.serviceAll()
        # Process inboud communication stack
        for msg in self.stack.value.rxMsgs:
            self._process_msg(msg)
        for event in self.events.value:
            self._fire_event(event)
        for ret in self.local_ret.value:
            self.stack.value.transmit(ret)
        self.stack.value.serviceAll()


class RemoteMaster(ioflo.base.deeding.Deed):
    '''
    Abstract access to the core salt master api
    '''
    Ioinits = {'opts': '.salt.etc.opts',
               'ret_in': '.salt.net.ret_in',
               'ret_out': '.salt.net.ret_out'}

    def __init__(self):
        ioflo.base.deeding.Deed.__init__(self)

    def postioinit(self):
        '''
        Set up required objects
        '''
        self.remote = salt.daemons.masterapi.RemoteFuncs(self.opts.value)

    def action(self):
        '''
        Perform an action
        '''
        if self.ret_in.value:
            exchange = self.ret_in.value.pop()
            load = exchange.get('load')
            # If the load is invalid, just ignore the request
            if not 'cmd' in load:
                return False
            if load['cmd'].startswith('__'):
                return False
            exchange['ret'] = getattr(self.remote, load['cmd'])(load)
            self.ret_out.value.append(exchange)


class LocalMaster(ioflo.base.deeding.Deed):
    '''
    Abstract access to the core salt master api
    '''
    Ioinits = {'opts': '.salt.etc.opts',
               'local_cmd': '.salt.uxd.local_cmd',
               'local_ret': '.salt.uxd.local_ret'}

    def __init__(self):
        ioflo.base.deeding.Deed.__init__(self)

    def postioinit(self):
        '''
        Set up required objects
        '''
        self.local = salt.daemons.masterapi.LocalFuncs(self.opts.value)

    def action(self):
        '''
        Perform an action
        '''
        for cmd in self.local_cmd.value:
            ret = {}
            load = cmd.get('load')
            # If the load is invalid, just ignore the request
            if not 'cmd' in load:
                return
            if load['cmd'].startswith('__'):
                return
            if hasattr(self.local, load['cmd']):
                ret['return'] = getattr(self.local, load['cmd'])(load)
                ret['route'] = {'src': ('router', self.stack.value.yard.name, None),
                                'dst': cmd['route']('src')}

            self.local_ret.value.append(ret)

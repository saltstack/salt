# -*- coding: utf-8 -*-
'''
Manage events

This module is used to manage events via RAET
'''
# pylint: disable=3rd-party-module-not-gated

# Import python libs
from __future__ import absolute_import
import os
import logging
import time
from collections import MutableMapping

# Import salt libs
import salt.payload
import salt.loader
import salt.state
import salt.utils.event
from salt.utils import kinds
from salt import transport
from salt import syspaths
from raet import raeting, nacling
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


class RAETEvent(object):
    '''
    The base class used to manage salt events
    '''
    def __init__(self, node, sock_dir=None, listen=True, opts=None):
        '''
        Set up the stack and remote yard
        '''
        self.node = node  # application kind see kinds.APPL_KIND_NAMES
        self.sock_dir = sock_dir
        if opts is None:
            opts = {}
        self.opts = opts
        self.stack = None
        self.ryn = 'manor'  # remote yard name
        self.connected = False
        self.cpub = False
        self.__prep_stack(listen)

    def __prep_stack(self, listen):
        '''
        Prepare the stack objects
        '''
        if not self.stack:
            if hasattr(transport, 'jobber_stack') and transport.jobber_stack:
                self.stack = transport.jobber_stack
            else:
                self.stack = transport.jobber_stack = self._setup_stack(ryn=self.ryn)
        log.debug("RAETEvent Using Jobber Stack at = {0}\n".format(self.stack.ha))
        if listen:
            self.subscribe()

    def _setup_stack(self, ryn='manor'):
        kind = self.opts.get('__role', '')  # opts optional for master
        if kind:  # not all uses of Raet SaltEvent has opts defined
            if kind not in kinds.APPL_KINDS:
                emsg = ("Invalid application kind = '{0}' for RAET SaltEvent.".format(kind))
                log.error(emsg + "\n")
                raise ValueError(emsg)
            if kind != self.node:
                emsg = ("Mismatch between node = '{0}' and kind = '{1}' in "
                        "RAET SaltEvent.".format(self.node, kind))
                log.error(emsg + '\n')
                raise ValueError(emsg)

        if self.node in [kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                         kinds.APPL_KIND_NAMES[kinds.applKinds.syndic]]:  # []'master', 'syndic']
            lanename = 'master'
        elif self.node in [kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                           kinds.APPL_KIND_NAMES[kinds.applKinds.caller]]:  # ['minion', 'caller']
            role = self.opts.get('id', '')  # opts required for minion
            if not role:
                emsg = ("Missing role required to setup RAET SaltEvent.")
                log.error(emsg + "\n")
                raise ValueError(emsg)
            if not kind:
                emsg = "Missing kind required to setup RAET SaltEvent."
                log.error(emsg + '\n')
                raise ValueError(emsg)
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application node kind '{0}' for RAET SaltEvent.".format(self.node))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        name = 'event' + nacling.uuid(size=18)
        cachedir = self.opts.get('cachedir', os.path.join(syspaths.CACHE_DIR, self.node))

        stack = LaneStack(
                name=name,
                lanename=lanename,
                sockdirpath=self.sock_dir)
        stack.Pk = raeting.PackKind.pack.value
        stack.addRemote(RemoteYard(stack=stack,
                                   lanename=lanename,
                                   name=ryn,
                                   dirpath=self.sock_dir))
        return stack

    def subscribe(self, tag=None):
        '''
        Included for compat with zeromq events, not required
        '''
        if not self.connected:
            self.connect_pub()

    def unsubscribe(self, tag=None):
        '''
        Included for compat with zeromq events, not required
        '''
        return

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        try:
            route = {'dst': (None, self.ryn, 'event_req'),
                     'src': (None, self.stack.local.name, None)}
            msg = {'route': route}
            self.stack.transmit(msg, self.stack.nameRemotes[self.ryn].uid)
            self.stack.serviceAll()
            self.connected = True
            self.cpub = True
        except Exception:
            pass

    def connect_pull(self, timeout=1000):
        '''
        Included for compat with zeromq events, not required
        '''
        return

    @classmethod
    def unpack(cls, raw, serial=None):
        '''
        Included for compat with zeromq events, not required
        '''
        return raw

    def get_event(self, wait=5, tag='', match_type=None, full=False, no_block=None,
                  auto_reconnect=False):
        '''
        Get a single publication.
        IF no publication available THEN block for up to wait seconds
        AND either return publication OR None IF no publication available.

        IF wait is 0 then block forever.
        '''
        if not self.connected:
            self.connect_pub()
        start = time.time()
        while True:
            self.stack.serviceAll()
            if self.stack.rxMsgs:
                msg, sender = self.stack.rxMsgs.popleft()
                if 'tag' not in msg and 'data' not in msg:
                    # Invalid event, how did this get here?
                    continue
                if not msg['tag'].startswith(tag):
                    # Not what we are looking for, throw it away
                    continue
                if full:
                    return msg
                else:
                    return msg['data']
            if start + wait < time.time():
                return None
            time.sleep(0.01)

    def get_event_noblock(self):
        '''
        Get the raw event msg without blocking or any other niceties
        '''
        if not self.connected:
            self.connect_pub()
        self.stack.serviceAll()
        if self.stack.rxMsgs:
            msg, sender = self.stack.rxMsgs.popleft()
            if 'tag' not in msg and 'data' not in msg:
                # Invalid event, how did this get here?
                return None
            return msg

    def iter_events(self, tag='', full=False, auto_reconnect=False):
        '''
        Creates a generator that continuously listens for events
        '''
        while True:
            data = self.get_event(tag=tag, full=full, auto_reconnect=auto_reconnect)
            if data is None:
                continue
            yield data

    def fire_event(self, data, tag, timeout=1000):
        '''
        Send a single event into the publisher with paylod dict "data" and event
        identifier "tag"
        '''
        # Timeout is retained for compat with zeromq events
        if not str(tag):  # no empty tags allowed
            raise ValueError('Empty tag.')

        if not isinstance(data, MutableMapping):  # data must be dict
            raise ValueError('Dict object expected, not \'{0}\'.'.format(data))
        route = {'dst': (None, self.ryn, 'event_fire'),
                 'src': (None, self.stack.local.name, None)}
        msg = {'route': route, 'tag': tag, 'data': data}
        self.stack.transmit(msg, self.stack.nameRemotes[self.ryn].uid)
        self.stack.serviceAll()

    def fire_ret_load(self, load):
        '''
        Fire events based on information in the return load
        '''
        if load.get('retcode') and load.get('fun'):
            # Minion fired a bad retcode, fire an event
            if load['fun'] in salt.utils.event.SUB_EVENT:
                try:
                    for tag, data in six.iteritems(load.get('return', {})):
                        data['retcode'] = load['retcode']
                        tags = tag.split('_|-')
                        if data.get('result') is False:
                            self.fire_event(
                                    data,
                                    '{0}.{1}'.format(tags[0], tags[-1]))  # old dup event
                            data['jid'] = load['jid']
                            data['id'] = load['id']
                            data['success'] = False
                            data['return'] = 'Error: {0}.{1}'.format(tags[0], tags[-1])
                            data['fun'] = load['fun']
                            data['user'] = load['user']
                            self.fire_event(
                                data,
                                salt.utils.event.tagify([load['jid'],
                                        'sub',
                                        load['id'],
                                        'error',
                                        load['fun']],
                                       'job'))
                except Exception:
                    pass

    def close_pub(self):
        '''
        Here for compatability
        '''
        return

    def destroy(self):
        if hasattr(self, 'stack'):
            self.stack.server.close()


class MasterEvent(RAETEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, opts, sock_dir, listen=True):
        super(MasterEvent, self).__init__('master', opts=opts, sock_dir=sock_dir, listen=listen)


class PresenceEvent(MasterEvent):

    def __init__(self, opts, sock_dir, listen=True, state=None):
        self.state = state
        super(PresenceEvent, self).__init__(opts=opts, sock_dir=sock_dir, listen=listen)

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        try:
            route = {'dst': (None, self.ryn, 'presence_req'),
                     'src': (None, self.stack.local.name, None)}
            msg = {'route': route}
            if self.state:
                msg['data'] = {'state': self.state}
            self.stack.transmit(msg, self.stack.nameRemotes[self.ryn].uid)
            self.stack.serviceAll()
            self.connected = True
        except Exception:
            pass


class StatsEvent(MasterEvent):

    def __init__(self, opts, sock_dir, tag, estate=None, listen=True):
        super(StatsEvent, self).__init__(opts=opts, sock_dir=sock_dir, listen=listen)
        self.tag = tag
        self.estate = estate

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        try:
            route = {'dst': (self.estate, None, 'stats_req'),
                     'src': (None, self.stack.local.name, None)}
            msg = {'route': route, 'tag': self.tag}
            self.stack.transmit(msg, self.stack.nameRemotes[self.ryn].uid)
            self.stack.serviceAll()
            self.connected = True
        except Exception:
            pass

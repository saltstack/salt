# -*- coding: utf-8 -*-
'''
Manage events

This module is used to manage events via RAET
'''

# Import python libs
import os
import logging
import time
from collections import MutableMapping

# Import salt libs
import salt.payload
import salt.loader
import salt.state
import salt.utils.event
from salt import syspaths
from raet import raeting, nacling
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard

log = logging.getLogger(__name__)


class SaltEvent(object):
    '''
    The base class used to manage salt events
    '''
    def __init__(self, node, sock_dir=None, listen=True, opts=None):
        '''
        Set up the stack and remote yard
        '''
        self.node = node  # application kind 'master', 'minion', 'syndic', 'call' etc
        self.sock_dir = sock_dir
        self.listen = listen
        if opts is None:
            opts = {}
        self.opts = opts
        self.__prep_stack()

    def __prep_stack(self):
        if self.node == 'master':
            lanename = 'master'
            if self.opts:
                kind = self.opts.get('__role', '')  # opts optional for master
                if kind and kind != self.node:
                    emsg = ("Mismatch between node '{0}' and kind '{1}' in setup "
                            "of SaltEvent on Raet.".format(self.node, kind))
                    log.error(emsg + '\n')
                    raise ValueError(emsg)
        elif self.node == 'minion':
            role = self.opts.get('id', '')  # opts required for minion
            if not role:
                emsg = ("Missing opts['id'] required by SaltEvent on Raet with "
                       "node kind {0}.".format(self.node))
                log.error(emsg + '\n')
                raise ValueError(emsg)
            kind = self.opts.get('__role', '')
            if kind != self.node:
                emsg = ("Mismatch between node '{0}' and kind '{1}' in setup "
                       "of SaltEvent on Raet.".format(self.node, kind))
                log.error(emsg + '\n')
                raise ValueError(emsg)
            lanename = role  # add '_minion'
        else:
            emsg = ("Unsupported application node kind '{0}' for SaltEvent "
                    "Raet.".format(self.node))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        name = 'event' + nacling.uuid(size=18)
        cachedir = self.opts.get('cachedir', os.path.join(syspaths.CACHE_DIR, self.node))
        self.connected = False
        self.stack = LaneStack(
                name=name,
                lanename=lanename,
                sockdirpath=self.sock_dir)
        self.stack.Pk = raeting.packKinds.pack
        self.router_yard = RemoteYard(
                stack=self.stack,
                lanename=lanename,
                name='manor',
                dirpath=self.sock_dir)
        self.stack.addRemote(self.router_yard)
        self.connect_pub()

    def subscribe(self, tag=None):
        '''
        Included for compat with zeromq events, not required
        '''
        return

    def unsubscribe(self, tag=None):
        '''
        Included for compat with zeromq events, not required
        '''
        return

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        if not self.connected and self.listen:
            try:
                route = {'dst': (None, self.router_yard.name, 'event_req'),
                         'src': (None, self.stack.local.name, None)}
                msg = {'route': route}
                self.stack.transmit(msg, self.router_yard.uid)
                self.stack.serviceAll()
                self.connected = True
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

    def get_event(self, wait=5, tag='', full=False):
        '''
        Get a single publication.
        IF no publication available THEN block for up to wait seconds
        AND either return publication OR None IF no publication available.

        IF wait is 0 then block forever.
        '''
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
        self.connect_pub()
        self.stack.serviceAll()
        if self.stack.rxMsgs:
            msg, sender = self.stack.rxMsgs.popleft()
            if 'tag' not in msg and 'data' not in msg:
                # Invalid event, how did this get here?
                return None
            return msg

    def iter_events(self, tag='', full=False):
        '''
        Creates a generator that continuously listens for events
        '''
        while True:
            data = self.get_event(tag=tag, full=full)
            if data is None:
                continue
            yield data

    def fire_event(self, data, tag, timeout=1000):
        '''
        Send a single event into the publisher with paylod dict "data" and event
        identifier "tag"
        '''
        self.connect_pub()
        # Timeout is retained for compat with zeromq events
        if not str(tag):  # no empty tags allowed
            raise ValueError('Empty tag.')

        if not isinstance(data, MutableMapping):  # data must be dict
            raise ValueError('Dict object expected, not "{0!r}".'.format(data))
        route = {'dst': (None, self.router_yard.name, 'event_fire'),
                 'src': (None, self.stack.local.name, None)}
        msg = {'route': route, 'tag': tag, 'data': data}
        self.stack.transmit(msg, self.router_yard.uid)
        self.stack.serviceAll()

    def fire_ret_load(self, load):
        '''
        Fire events based on information in the return load
        '''
        if load.get('retcode') and load.get('fun'):
            # Minion fired a bad retcode, fire an event
            if load['fun'] in salt.utils.event.SUB_EVENT:
                try:
                    for tag, data in load.get('return', {}).items():
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

    def destroy(self):
        if hasattr(self, 'stack'):
            self.stack.server.close()

    def __del__(self):
        self.destroy()

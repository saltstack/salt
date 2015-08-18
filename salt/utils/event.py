# -*- coding: utf-8 -*-
'''
Manage events

Events are all fired off via a zeromq 'pub' socket, and listened to with local
zeromq 'sub' sockets


All of the formatting is self contained in the event module, so we should be
able to modify the structure in the future since the same module used to read
events is the same module used to fire off events.

Old style event messages were comprised of two parts delimited at the 20 char
point. The first 20 characters are used for the zeromq subscriber to match
publications and 20 characters was chosen because it was at the time a few more
characters than the length of a jid (Job ID).  Any tags of length less than 20
characters were padded with "|" chars out to 20 characters.

Although not explicit, the data for an event comprised a python dict that was
serialized by msgpack.

New style event messages support event tags longer than 20 characters while
still being backwards compatible with old style tags.

The longer tags better enable name spaced event tags which tend to be longer.
Moreover, the constraint that the event data be a python dict is now an
explicit constraint and fire-event will now raise a ValueError if not. Tags
must be ascii safe strings, that is, have values less than 0x80

Since the msgpack dict (map) indicators have values greater than or equal to 0x80
it can be unambiguously determined if the start of data is at char 21 or not.

In the new style, when the tag is longer than 20 characters, an end of tag
string is appended to the tag given by the string constant TAGEND, that is, two
line feeds '\n\n'.  When the tag is less than 20 characters then the tag is
padded with pipes "|" out to 20 characters as before.  When the tag is exactly
20 characters no padded is done.

The get_event method intelligently figures out if the tag is longer than 20
characters.


The convention for namespacing is to use dot characters "." as the name space
delimiter. The name space "salt" is reserved by SaltStack for internal events.

For example:
Namespaced tag
    'salt.runner.manage.status.start'

'''

from __future__ import absolute_import

# Import python libs
import os
import hashlib
import errno
import logging
import time
import datetime
import multiprocessing
import re
from collections import MutableMapping

# Import third party libs
try:
    import zmq
except ImportError:
    # Local mode does not need zmq
    pass

# Import salt libs
import salt.payload
import salt.loader
import salt.utils
import salt.utils.cache
import salt.utils.dicttrim
import salt.utils.process
import salt.utils.zeromq
log = logging.getLogger(__name__)

# The SUB_EVENT set is for functions that require events fired based on
# component executions, like the state system
SUB_EVENT = set([
            'state.highstate',
            'state.sls',
            ])

TAGEND = '\n\n'  # long tag delimiter
TAGPARTER = '/'  # name spaced tag delimiter
SALT = 'salt'  # base prefix for all salt/ events
# dict map of namespaced base tag prefixes for salt events
TAGS = {
    'auth': 'auth',  # prefix for all salt/auth events
    'job': 'job',  # prefix for all salt/job events (minion jobs)
    'key': 'key',  # prefix for all salt/key events
    'minion': 'minion',  # prefix for all salt/minion events (minion sourced events)
    'syndic': 'syndic',  # prefix for all salt/syndic events (syndic minion sourced events)
    'run': 'run',  # prefix for all salt/run events (salt runners)
    'wheel': 'wheel',  # prefix for all salt/wheel events
    'cloud': 'cloud',  # prefix for all salt/cloud events
    'fileserver': 'fileserver',  # prefix for all salt/fileserver events
    'queue': 'queue',  # prefix for all salt/queue events
}


def get_event(node, sock_dir=None, transport='zeromq', opts=None, listen=True):
    '''
    Return an event object suitable for the named transport
    '''
    sock_dir = sock_dir or opts.get('sock_dir', None)
    if transport == 'zeromq':
        if node == 'master':
            return MasterEvent(sock_dir, opts)
        return SaltEvent(node, sock_dir, opts)
    elif transport == 'raet':
        import salt.utils.raetevent
        return salt.utils.raetevent.RAETEvent(node,
                                              sock_dir=sock_dir,
                                              listen=listen,
                                              opts=opts)


def get_master_event(opts, sock_dir, listen=True):
    '''
    Return an event object suitable for the named transport
    '''
    if opts['transport'] == 'zeromq':
        return MasterEvent(sock_dir, opts)
    elif opts['transport'] == 'raet':
        import salt.utils.raetevent
        return salt.utils.raetevent.MasterEvent(opts=opts, sock_dir=sock_dir, listen=listen)


def tagify(suffix='', prefix='', base=SALT):
    '''
    convenience function to build a namespaced event tag string
    from joining with the TABPART character the base, prefix and suffix

    If string prefix is a valid key in TAGS Then use the value of key prefix
    Else use prefix string

    If suffix is a list Then join all string elements of suffix individually
    Else use string suffix

    '''
    parts = [base, TAGS.get(prefix, prefix)]
    if hasattr(suffix, 'append'):  # list so extend parts
        parts.extend(suffix)
    else:  # string so append
        parts.append(suffix)
    return TAGPARTER.join([part for part in parts if part])


class SaltEvent(object):
    '''
    Warning! Use the get_event function or the code will not be
    RAET compatible
    The base class used to manage salt events
    '''
    def __init__(self, node, sock_dir=None, opts=None):
        self.serial = salt.payload.Serial({'serial': 'msgpack'})
        self.context = zmq.Context()
        self.poller = zmq.Poller()
        self.cpub = False
        self.cpush = False
        if opts is None:
            opts = {}
        self.opts = opts
        if sock_dir is None:
            sock_dir = opts.get('sock_dir', None)
        self.puburi, self.pulluri = self.__load_uri(sock_dir, node)
        self.pending_tags = []
        self.pending_rtags = []
        self.pending_events = []
        # since ZMQ connect()  has no guarantees about the socket actually being
        # connected this is a hack to attempt to do so.
        if not self.cpub:
            self.connect_pub()
        self.fire_event({}, tagify('event/new_client'), 0)
        self.get_event(wait=1)

    def __load_uri(self, sock_dir, node):
        '''
        Return the string URI for the location of the pull and pub sockets to
        use for firing and listening to events
        '''
        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        # Only use the first 10 chars to keep longer hashes from exceeding the
        # max socket path length.
        id_hash = hash_type(self.opts.get('id', '')).hexdigest()[:10]
        if node == 'master':
            puburi = 'ipc://{0}'.format(os.path.join(
                    sock_dir,
                    'master_event_pub.ipc'
                    ))
            salt.utils.zeromq.check_ipc_path_max_len(puburi)
            pulluri = 'ipc://{0}'.format(os.path.join(
                    sock_dir,
                    'master_event_pull.ipc'
                    ))
            salt.utils.zeromq.check_ipc_path_max_len(pulluri)
        else:
            if self.opts.get('ipc_mode', '') == 'tcp':
                puburi = 'tcp://127.0.0.1:{0}'.format(
                        self.opts.get('tcp_pub_port', 4510)
                        )
                pulluri = 'tcp://127.0.0.1:{0}'.format(
                        self.opts.get('tcp_pull_port', 4511)
                        )
            else:
                puburi = 'ipc://{0}'.format(os.path.join(
                        sock_dir,
                        'minion_event_{0}_pub.ipc'.format(id_hash)
                        ))
                salt.utils.zeromq.check_ipc_path_max_len(puburi)
                pulluri = 'ipc://{0}'.format(os.path.join(
                        sock_dir,
                        'minion_event_{0}_pull.ipc'.format(id_hash)
                        ))
                salt.utils.zeromq.check_ipc_path_max_len(pulluri)
        log.debug(
            '{0} PUB socket URI: {1}'.format(self.__class__.__name__, puburi)
        )
        log.debug(
            '{0} PULL socket URI: {1}'.format(self.__class__.__name__, pulluri)
        )
        return puburi, pulluri

    def subscribe(self, tag):
        '''
        Subscribe to events matching the passed tag.

        If you do not subscribe to a tag, events will be discarded by calls to
        get_event that request a different tag. In contexts where many different
        jobs are outstanding it is important to subscribe to prevent one call
        to get_event from discarding a response required by a subsequent call
        to get_event.
        '''
        self.pending_tags.append(tag)

        return

    def subscribe_regex(self, tag_regex):
        '''
        Subscribe to events matching the passed tag expression.

        If you do not subscribe to a tag, events will be discarded by calls to
        get_event that request a different tag. In contexts where many different
        jobs are outstanding it is important to subscribe to prevent one call
        to get_event from discarding a response required by a subsequent call
        to get_event.
        '''
        self.pending_rtags.append(re.compile(tag_regex))

        return

    def unsubscribe(self, tag):
        '''
        Un-subscribe to events matching the passed tag.
        '''
        self.pending_tags.remove(tag)

        return

    def unsubscribe_regex(self, tag_regex):
        '''
        Un-subscribe to events matching the passed tag.
        '''
        self.pending_rtags.remove(tag_regex)

        old_events = self.pending_events
        self.pending_events = []
        for evt in old_events:
            if any(evt['tag'].startswith(ptag) for ptag in self.pending_tags) or any(rtag.search(evt['tag']) for rtag in self.pending_rtags):
                self.pending_events.append(evt)

        return

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(self.puburi)
        self.poller.register(self.sub, zmq.POLLIN)
        self.sub.setsockopt(zmq.SUBSCRIBE, '')
        self.sub.setsockopt(zmq.LINGER, 5000)
        self.cpub = True

    def connect_pull(self, timeout=1000):
        '''
        Establish a connection with the event pull socket
        Set the send timeout of the socket options to timeout (in milliseconds)
        Default timeout is 1000 ms
        The linger timeout must be at least as long as this timeout
        '''
        self.push = self.context.socket(zmq.PUSH)
        try:
            # bug in 0MQ default send timeout of -1 (infinite) is not infinite
            self.push.setsockopt(zmq.SNDTIMEO, timeout)
        except AttributeError:
            # This is for ZMQ < 2.2 (Caught when ssh'ing into the Jenkins
            #                        CentOS5, which still uses 2.1.9)
            pass
        self.push.setsockopt(zmq.LINGER, timeout)
        self.push.connect(self.pulluri)
        self.cpush = True

    @classmethod
    def unpack(cls, raw, serial=None):
        if serial is None:
            serial = salt.payload.Serial({'serial': 'msgpack'})

        mtag, sep, mdata = raw.partition(TAGEND)  # split tag from data

        data = serial.loads(mdata)
        return mtag, data

    def _check_pending(self, tag, tags_regex):
        """Check the pending_events list for events that match the tag

        :param tag: The tag to search for
        :type tag: str
        :param tags_regex: List of re expressions to search for also
        :type tags_regex: list[re.compile()]
        :return:
        """
        old_events = self.pending_events
        self.pending_events = []
        ret = None
        for evt in old_events:
            if evt['tag'].startswith(tag) or any(rtag.search(evt['tag']) for rtag in tags_regex):
                if ret is None:
                    ret = evt
                    log.trace('get_event() returning cached event = {0}'.format(ret))
                else:
                    self.pending_events.append(evt)
            elif any(evt['tag'].startswith(ptag) for ptag in self.pending_tags) or any(rtag.search(evt['tag']) for rtag in self.pending_rtags):
                self.pending_events.append(evt)
            else:
                log.trace('get_event() discarding cached event that no longer has any subscriptions = {0}'.format(evt))
        return ret

    def _get_event(self, wait, tag, tags_regex):
        start = time.time()
        timeout_at = start + wait
        while not wait or time.time() <= timeout_at:
            try:
                # convert to milliseconds
                socks = dict(self.poller.poll(wait * 1000))
                if socks.get(self.sub) != zmq.POLLIN:
                    continue
                # Please do not use non-blocking mode here.
                # Reliability is more important than pure speed on the event bus.
                ret = self.get_event_block()
            except zmq.ZMQError as ex:
                if ex.errno == errno.EAGAIN or ex.errno == errno.EINTR:
                    continue
                else:
                    raise

            if not ret['tag'].startswith(tag) and not any(rtag.search(ret['tag']) for rtag in tags_regex):
                # tag not match
                if any(ret['tag'].startswith(ptag) for ptag in self.pending_tags) or any(rtag.search(ret['tag']) for rtag in self.pending_rtags):
                    log.trace('get_event() caching unwanted event = {0}'.format(ret))
                    self.pending_events.append(ret)
                if wait:  # only update the wait timeout if we had one
                    wait = timeout_at - time.time()
                continue

            log.trace('get_event() received = {0}'.format(ret))
            return ret

        return None

    def get_event(self, wait=5, tag='', tags_regex=None, full=False):
        '''
        Get a single publication.
        IF no publication available THEN block for up to wait seconds
        AND either return publication OR None IF no publication available.

        IF wait is 0 then block forever.

        A tag specification can be given to only return publications with a tag
        STARTING WITH a given string (tag) OR MATCHING one or more string
        regular expressions (tags_regex list). If tag is not specified or given
        as an empty string, all events are considered.

        Searches cached publications first. If no cached publications are found
        that match the given tag specification, new publications are received
        and checked.

        If a publication is received that does not match the tag specification,
        it is DISCARDED unless it is subscribed to via subscribe() and
        subscribe_regex() which will cause it to be cached.

        If a caller is not going to call get_event immediately after sending a
        request, it MUST subscribe the result to ensure the response is not lost
        should other regions of code call get_event for other purposes.
        '''

        if tags_regex is None:
            tags_regex = []
        else:
            tags_regex = [re.compile(rtag) for rtag in tags_regex]

        ret = self._check_pending(tag, tags_regex)
        if ret is None:
            ret = self._get_event(wait, tag, tags_regex)

        if ret is None or full:
            return ret
        else:
            return ret['data']

    def get_event_noblock(self):
        '''Get the raw event without blocking or any other niceties
        '''
        if not self.cpub:
            self.connect_pub()
        raw = self.sub.recv(zmq.NOBLOCK)
        mtag, data = self.unpack(raw, self.serial)
        return {'data': data, 'tag': mtag}

    def get_event_block(self):
        '''Get the raw event in a blocking fashion
           Slower, but decreases the possibility of dropped events
        '''
        raw = self.sub.recv()
        mtag, data = self.unpack(raw, self.serial)
        return {'data': data, 'tag': mtag}

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
        Send a single event into the publisher with payload dict "data" and event
        identifier "tag"

        The default is 1000 ms
        Note the linger timeout must be at least as long as this timeout
        '''
        if not str(tag):  # no empty tags allowed
            raise ValueError('Empty tag.')

        if not isinstance(data, MutableMapping):  # data must be dict
            raise ValueError('Dict object expected, not "{0!r}".'.format(data))

        if not self.cpush:
            self.connect_pull(timeout=timeout)

        data['_stamp'] = datetime.datetime.utcnow().isoformat()

        tagend = TAGEND
        serialized_data = salt.utils.dicttrim.trim_dict(self.serial.dumps(data),
                self.opts.get('max_event_size', 1048576),
                is_msgpacked=True
                )
        log.debug('Sending event - data = {0}'.format(data))
        event = '{0}{1}{2}'.format(tag, tagend, serialized_data)
        try:
            self.push.send(event)
        except Exception as ex:
            log.debug(ex)
            raise
        return True

    def destroy(self, linger=5000):
        if self.cpub is True and self.sub.closed is False:
            # Wait at most 2.5 secs to send any remaining messages in the
            # socket or the context.term() bellow will hang indefinitely.
            # See https://github.com/zeromq/pyzmq/issues/102
            self.sub.close()
        if self.cpush is True and self.push.closed is False:
            self.push.close()
        # If sockets are not unregistered from a poller, nothing which touches
        # that poller gets garbage collected. The Poller itself, its
        # registered sockets and the Context
        if isinstance(self.poller.sockets, dict):
            for socket in self.poller.sockets.keys():
                if socket.closed is False:
                    socket.setsockopt(zmq.LINGER, linger)
                    socket.close()
                self.poller.unregister(socket)
        else:
            for socket in self.poller.sockets:
                if socket[0].closed is False:
                    socket[0].setsockopt(zmq.LINGER, linger)
                    socket[0].close()
                self.poller.unregister(socket[0])
        if self.context.closed is False:
            self.context.term()

        # Hardcore destruction
        if hasattr(self.context, 'destroy'):
            self.context.destroy(linger=1)

        # https://github.com/zeromq/pyzmq/issues/173#issuecomment-4037083
        # Assertion failed: get_load () == 0 (poller_base.cpp:32)
        time.sleep(0.025)

    def fire_ret_load(self, load):
        '''
        Fire events based on information in the return load
        '''
        if load.get('retcode') and load.get('fun'):
            # Minion fired a bad retcode, fire an event
            if load['fun'] in SUB_EVENT:
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
                                tagify([load['jid'],
                                        'sub',
                                        load['id'],
                                        'error',
                                        load['fun']],
                                       'job'))
                except Exception:
                    pass

    def __del__(self):
        # skip exceptions in destroy-- since destroy() doesn't cover interpreter
        # shutdown-- where globals start going missing
        try:
            self.destroy()
        except Exception as ex:
            log.debug(ex)


class MasterEvent(SaltEvent):
    '''
    Warning! Use the get_event function or the code will not be
    RAET compatible
    Create a master event management object
    '''
    def __init__(self, sock_dir, opts=None):
        super(MasterEvent, self).__init__('master', sock_dir, opts)


class LocalClientEvent(MasterEvent):
    '''
    Warning! Use the get_event function or the code will not be
    RAET compatible
    This class is just used to differentiate who is handling the events,
    specially on logs, but it's the same as MasterEvent.
    '''


class NamespacedEvent(object):
    '''
    A wrapper for sending events within a specific base namespace
    '''
    def __init__(self, event, base, print_func=None):
        self.event = event
        self.base = base
        self.print_func = print_func

    def fire_event(self, data, tag):
        if self.print_func is not None:
            self.print_func(tag, data)
        self.event.fire_event(data, tagify(tag, base=self.base))


class MinionEvent(SaltEvent):
    '''
    Warning! Use the get_event function or the code will not be
    RAET compatible
    Create a master event management object
    '''
    def __init__(self, opts):
        super(MinionEvent, self).__init__('minion', sock_dir=opts.get('sock_dir', None), opts=opts)


class EventPublisher(multiprocessing.Process):
    '''
    The interface that takes master events and republishes them out to anyone
    who wants to listen
    '''
    def __init__(self, opts):
        super(EventPublisher, self).__init__()
        self.opts = opts

    def run(self):
        '''
        Bind the pub and pull sockets for events
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        linger = 5000
        # Set up the context
        self.context = zmq.Context(1)
        # Prepare the master event publisher
        self.epub_sock = self.context.socket(zmq.PUB)
        epub_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pub.ipc')
                )
        salt.utils.zeromq.check_ipc_path_max_len(epub_uri)
        # Prepare master event pull socket
        self.epull_sock = self.context.socket(zmq.PULL)
        epull_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pull.ipc')
                )
        salt.utils.zeromq.check_ipc_path_max_len(epull_uri)

        # Start the master event publisher
        old_umask = os.umask(0o177)
        try:
            self.epull_sock.bind(epull_uri)
            self.epub_sock.bind(epub_uri)
            if self.opts.get('client_acl') or self.opts.get('external_auth'):
                os.chmod(
                        os.path.join(self.opts['sock_dir'],
                            'master_event_pub.ipc'),
                        0o666
                        )
        finally:
            os.umask(old_umask)
        try:
            while True:
                # Catch and handle EINTR from when this process is sent
                # SIGUSR1 gracefully so we don't choke and die horribly
                try:
                    package = self.epull_sock.recv()
                    self.epub_sock.send(package)
                except zmq.ZMQError as exc:
                    if exc.errno == errno.EINTR:
                        continue
                    raise exc
        except KeyboardInterrupt:
            if self.epub_sock.closed is False:
                self.epub_sock.setsockopt(zmq.LINGER, linger)
                self.epub_sock.close()
            if self.epull_sock.closed is False:
                self.epull_sock.setsockopt(zmq.LINGER, linger)
                self.epull_sock.close()
            if self.context.closed is False:
                self.context.term()


class EventReturn(multiprocessing.Process):
    '''
    A dedicated process which listens to the master event bus and queues
    and forwards events to the specified returner.
    '''
    def __init__(self, opts):
        '''
        Initialize the EventReturn system

        Return an EventReturn instance
        '''
        multiprocessing.Process.__init__(self)

        self.opts = opts
        self.event_return_queue = self.opts['event_return_queue']
        local_minion_opts = self.opts.copy()
        local_minion_opts['file_client'] = 'local'
        self.minion = salt.minion.MasterMinion(local_minion_opts)

    def run(self):
        '''
        Spin up the multiprocess event returner
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        self.event = get_event('master', opts=self.opts)
        events = self.event.iter_events(full=True)
        self.event.fire_event({}, 'salt/event_listen/start')
        event_queue = []
        for event in events:
            if self._filter(event):
                event_queue.append(event)
            if len(event_queue) >= self.event_return_queue:
                event_return = '{0}.event_return'.format(
                    self.opts['event_return']
                )
                if event_return in self.minion.returners:
                    self.minion.returners[event_return](event_queue)
                    event_queue = []
                else:
                    log.error(
                        'Could not store return for event(s) {0}. Returner '
                        '\'{1}\' not found.'
                        .format(event_queue, self.opts['event_return'])
                    )

    def _filter(self, event):
        '''
        Take an event and run it through configured filters.

        Returns True if event should be stored, else False
        '''
        tag = event['tag']
        if tag in self.opts['event_return_whitelist']:
            if tag not in self.opts['event_return_blacklist']:
                return True
            else:
                return False  # Event was whitelisted and blacklisted
        elif tag in self.opts['event_return_blacklist']:
            return False
        return True


class StateFire(object):
    '''
    Evaluate the data from a state run and fire events on the master and minion
    for each returned chunk that is not "green"
    This object is made to only run on a minion
    '''
    def __init__(self, opts, auth=None):
        self.opts = opts
        self.event = SaltEvent(opts, 'minion')
        if not auth:
            self.auth = salt.crypt.SAuth(self.opts)
        else:
            self.auth = auth

    def fire_master(self, data, tag, preload=None):
        '''
        Fire an event off on the master server

        CLI Example:

        .. code-block:: bash

            salt '*' event.fire_master 'stuff to be in the event' 'tag'
        '''
        load = {}
        if preload:
            load.update(preload)

        load.update({'id': self.opts['id'],
                    'tag': tag,
                    'data': data,
                    'cmd': '_minion_event',
                    'tok': self.auth.gen_token('salt')})

        channel = salt.transport.Channel.factory(self.opts)
        try:
            channel.send(load)
        except Exception:
            pass
        return True

    def fire_running(self, running):
        '''
        Pass in a state "running" dict, this is the return dict from a state
        call. The dict will be processed and fire events.

        By default yellows and reds fire events on the master and minion, but
        this can be configured.
        '''
        load = {'id': self.opts['id'],
                'events': [],
                'cmd': '_minion_event'}
        for stag in sorted(
                running,
                key=lambda k: running[k].get('__run_num__', 0)):
            if running[stag]['result'] and not running[stag]['changes']:
                continue
            tag = 'state_{0}_{1}'.format(
                    str(running[stag]['result']),
                    'True' if running[stag]['changes'] else 'False')
            load['events'].append(
                    {'tag': tag,
                     'data': running[stag]}
                    )
        channel = salt.transport.Channel.factory(self.opts)
        try:
            channel.send(load)
        except Exception:
            pass
        return True

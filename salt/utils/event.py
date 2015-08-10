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

Since the msgpack dict (map) indicators have values greater than or equal to
0x80 it can be unambiguously determined if the start of data is at char 21
or not.

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
import time
import errno
import signal
import hashlib
import logging
import datetime
import multiprocessing
from collections import MutableMapping

# Import third party libs
import salt.ext.six as six
try:
    import zmq
    import zmq.eventloop.ioloop
    # support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
    if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
        zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
    import zmq.eventloop.zmqstream
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
    'minion': 'minion',  # prefix for all salt/minion events
                         # (minion sourced events)
    'syndic': 'syndic',  # prefix for all salt/syndic events
                         # (syndic minion sourced events)
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
    # TODO: AIO core is separate from transport
    if transport in ('zeromq', 'tcp'):
        if node == 'master':
            return MasterEvent(sock_dir, opts, listen=listen)
        return SaltEvent(node, sock_dir, opts, listen=listen)
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
    # TODO: AIO core is separate from transport
    if opts['transport'] in ('zeromq', 'tcp'):
        return MasterEvent(sock_dir, opts, listen=listen)
    elif opts['transport'] == 'raet':
        import salt.utils.raetevent
        return salt.utils.raetevent.MasterEvent(
            opts=opts, sock_dir=sock_dir, listen=listen
        )


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
    def __init__(self, node, sock_dir=None, opts=None, listen=True):
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
        if salt.utils.is_windows() and not hasattr(opts, 'ipc_mode'):
            opts['ipc_mode'] = 'tcp'
        self.puburi, self.pulluri = self.__load_uri(sock_dir, node)
        if listen:
            self.subscribe()
        self.pending_events = []
        self.__load_cache_regex()

    @classmethod
    def __load_cache_regex(cls):
        '''
        Initialize the regular expression cache and put it in the
        class namespace. The regex search strings will be prepend with '^'
        '''
        # This is in the class namespace, to minimize cache memory
        # usage and maximize cache hits
        # The prepend='^' is to reduce differences in behavior between
        # the default 'startswith' and the optional 'regex' match_type
        cls.cache_regex = salt.utils.cache.CacheRegex(prepend='^')

    def __load_uri(self, sock_dir, node):
        '''
        Return the string URI for the location of the pull and pub sockets to
        use for firing and listening to events
        '''
        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        # Only use the first 10 chars to keep longer hashes from exceeding the
        # max socket path length.
        id_hash = hash_type(salt.utils.to_bytes(self.opts.get('id', ''))).hexdigest()[:10]
        if node == 'master':
            if self.opts.get('ipc_mode', '') == 'tcp':
                puburi = 'tcp://127.0.0.1:{0}'.format(
                    self.opts.get('tcp_master_pub_port', 4512)
                    )
                pulluri = 'tcp://127.0.0.1:{0}'.format(
                    self.opts.get('tcp_master_pull_port', 4513)
                    )
            else:
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

    def subscribe(self, tag=None):
        '''
        Subscribe to events matching the passed tag.
        '''
        if not self.cpub:
            self.connect_pub()

    def unsubscribe(self, tag=None):
        '''
        Un-subscribe to events matching the passed tag.
        '''
        return

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(self.puburi)
        self.poller.register(self.sub, zmq.POLLIN)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, u'')
        self.sub.setsockopt(zmq.LINGER, 5000)
        self.cpub = True

    def connect_pull(self, timeout=1000):
        '''
        Establish a connection with the event pull socket
        Set the linger timeout of the socket options to timeout (in milliseconds)
        Default timeout is 1000 ms
        '''
        self.push = self.context.socket(zmq.PUSH)
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

    def _get_match_func(self, match_type=None):
        if match_type is None:
            match_type = self.opts.get('event_match_type', 'startswith')
        return getattr(self, '_match_tag_{0}'.format(match_type), None)

    def _check_pending(self, tag, pending_tags, match_func=None):
        """Check the pending_events list for events that match the tag

        :param tag: The tag to search for
        :type tag: str
        :param pending_tags: List of tags to preserve
        :type pending_tags: list[str]
        :return:
        """
        if match_func is None:
            match_func = self._get_match_func()
        old_events = self.pending_events
        self.pending_events = []
        ret = None
        for evt in old_events:
            if match_func(evt['tag'], tag):
                if ret is None:
                    ret = evt
                else:
                    self.pending_events.append(evt)
            elif any(match_func(evt['tag'], ptag) for ptag in pending_tags):
                self.pending_events.append(evt)
        return ret

    def _match_tag_startswith(self, event_tag, search_tag):
        '''
        Check if the event_tag matches the search check.
        Uses startswith to check.
        Return True (matches) or False (no match)
        '''
        return event_tag.startswith(search_tag)

    def _match_tag_endswith(self, event_tag, search_tag):
        '''
        Check if the event_tag matches the search check.
        Uses endswith to check.
        Return True (matches) or False (no match)
        '''
        return event_tag.endswith(search_tag)

    def _match_tag_find(self, event_tag, search_tag):
        '''
        Check if the event_tag matches the search check.
        Uses find to check.
        Return True (matches) or False (no match)
        '''
        return event_tag.find(search_tag) >= 0

    def _match_tag_regex(self, event_tag, search_tag):
        '''
        Check if the event_tag matches the search check.
        Uses regular expression search to check.
        Return True (matches) or False (no match)
        '''
        return self.cache_regex.get(search_tag).search(event_tag) is not None

    def _get_event(self, wait, tag, pending_tags, match_func=None):
        if match_func is None:
            match_func = self._get_match_func()
        start = time.time()
        timeout_at = start + wait
        while not wait or time.time() <= timeout_at:
            try:
                # convert to milliseconds
                socks = dict(self.poller.poll(wait * 1000))
                if socks.get(self.sub) != zmq.POLLIN:
                    continue

                # Please do not use non-blocking mode here. Reliability is
                # more important than pure speed on the event bus.
                ret = self.get_event_block()
            except KeyboardInterrupt:
                return {'tag': 'salt/event/exit', 'data': {}}
            except zmq.ZMQError as ex:
                if ex.errno == errno.EAGAIN or ex.errno == errno.EINTR:
                    continue
                else:
                    raise

            if not match_func(ret['tag'], tag):     # tag not match
                if any(match_func(ret['tag'], ptag) for ptag in pending_tags):
                    self.pending_events.append(ret)
                if wait:  # only update the wait timeout if we had one
                    wait = timeout_at - time.time()
                continue

            log.trace('get_event() received = {0}'.format(ret))
            return ret

        return None

    def get_event(self, wait=5, tag='', full=False, use_pending=False,
                  pending_tags=None, match_type=None):
        '''
        Get a single publication.
        IF no publication available THEN block for up to wait seconds
        AND either return publication OR None IF no publication available.

        IF wait is 0 then block forever.

        New in Boron always checks the list of pending events

        New in @TBD optionally set match_type

        use_pending
            Defines whether to keep all unconsumed events in a pending_events
            list, or to discard events that don't match the requested tag.  If
            set to True, MAY CAUSE MEMORY LEAKS.

        pending_tags
            Add any events matching the listed tags to the pending queue.
            Still MAY CAUSE MEMORY LEAKS but less likely than use_pending
            assuming you later get_event for the tags you've listed here

            New in Boron

        match_type
            Set the function to match the search tag with event tags.
             - 'startswith' : search for event tags that start with tag
             - 'endswith' : search for event tags that end with tag
             - 'find' : search for event tags that contain tag
             - 'regex' : regex search '^' + tag event tags
            Default is opts['event_match_type'] or 'startswith'

            New in @TBD
        '''

        match_func = self._get_match_func(match_type)
        if use_pending:
            pending_tags = ['']
        elif pending_tags is None:
            pending_tags = []

        ret = self._check_pending(tag, pending_tags, match_func)
        if ret is None:
            ret = self._get_event(wait, tag, pending_tags, match_func)

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

    def iter_events(self, tag='', full=False, match_type=None):
        '''
        Creates a generator that continuously listens for events
        '''
        while True:
            data = self.get_event(tag=tag, full=full, match_type=match_type)
            if data is None:
                continue
            yield data

    def fire_event(self, data, tag, timeout=1000):
        '''
        Send a single event into the publisher with payload dict "data" and
        event identifier "tag"

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
        serialized_data = salt.utils.dicttrim.trim_dict(
            self.serial.dumps(data),
            self.opts.get('max_event_size', 1048576),
            is_msgpacked=True,
        )
        log.debug('Sending event - data = {0}'.format(data))
        event = '{0}{1}{2}'.format(tag, tagend, serialized_data)
        try:
            self.push.send(salt.utils.to_bytes(event, 'utf-8'))
        except Exception as ex:
            log.debug(ex)
            raise
        return True

    def fire_master(self, data, tag, timeout=1000):
        ''''
        Send a single event to the master, with the payload "data" and the
        event identifier "tag".

        Default timeout is 1000ms
        '''
        msg = {
            'tag': tag,
            'data': data,
            'events': None,
            'pretag': None
        }
        return self.fire_event(msg, "fire_master", timeout)

    def destroy(self, linger=5000):
        if self.cpub is True and self.sub.closed is False:
            # Wait at most 2.5 secs to send any remaining messages in the
            # socket or the context.term() below will hang indefinitely.
            # See https://github.com/zeromq/pyzmq/issues/102
            self.sub.close()
        if self.cpush is True and self.push.closed is False:
            self.push.close()
        # If sockets are not unregistered from a poller, nothing which touches
        # that poller gets garbage collected. The Poller itself, its
        # registered sockets and the Context
        if isinstance(self.poller.sockets, dict):
            for socket in six.iterkeys(self.poller.sockets):
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
                    for tag, data in six.iteritems(load.get('return', {})):
                        data['retcode'] = load['retcode']
                        tags = tag.split('_|-')
                        if data.get('result') is False:
                            self.fire_event(
                                data,
                                '{0}.{1}'.format(tags[0], tags[-1])
                            )  # old dup event
                            data['jid'] = load['jid']
                            data['id'] = load['id']
                            data['success'] = False
                            data['return'] = 'Error: {0}.{1}'.format(
                                tags[0], tags[-1])
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
        except:  # pylint: disable=W0702
            pass


class MasterEvent(SaltEvent):
    '''
    Warning! Use the get_event function or the code will not be
    RAET compatible
    Create a master event management object
    '''
    def __init__(self, sock_dir, opts=None, listen=True):
        super(MasterEvent, self).__init__('master', sock_dir, opts, listen=listen)


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
    def __init__(self, opts, listen=True):
        super(MinionEvent, self).__init__(
            'minion', sock_dir=opts.get('sock_dir', None), opts=opts, listen=listen)


class AsyncEventPublisher(object):
    '''
    An event publisher class intended to run in an ioloop (within a single process)

    TODO: remove references to "minion_event" whenever we need to use this for other things
    '''
    def __init__(self, opts, publish_handler, io_loop=None):
        self.opts = opts
        self.publish_handler = publish_handler

        self.io_loop = io_loop or zmq.eventloop.ioloop.ZMQIOLoop()
        self.context = zmq.Context()

        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        # Only use the first 10 chars to keep longer hashes from exceeding the
        # max socket path length.
        id_hash = hash_type(salt.utils.to_bytes(self.opts.get('id', ''))).hexdigest()[:10]
        epub_sock_path = os.path.join(
            self.opts['sock_dir'],
            'minion_event_{0}_pub.ipc'.format(id_hash)
        )
        if os.path.exists(epub_sock_path):
            os.unlink(epub_sock_path)
        epull_sock_path = os.path.join(
            self.opts['sock_dir'],
            'minion_event_{0}_pull.ipc'.format(id_hash)
        )
        if os.path.exists(epull_sock_path):
            os.unlink(epull_sock_path)

        self.epub_sock = self.context.socket(zmq.PUB)

        if self.opts.get('ipc_mode', '') == 'tcp':
            epub_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts['tcp_pub_port']
            )
            epull_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts['tcp_pull_port']
            )
        else:
            epub_uri = 'ipc://{0}'.format(epub_sock_path)
            salt.utils.zeromq.check_ipc_path_max_len(epub_uri)
            epull_uri = 'ipc://{0}'.format(epull_sock_path)
            salt.utils.zeromq.check_ipc_path_max_len(epull_uri)

        log.debug(
            '{0} PUB socket URI: {1}'.format(
                self.__class__.__name__, epub_uri
            )
        )
        log.debug(
            '{0} PULL socket URI: {1}'.format(
                self.__class__.__name__, epull_uri
            )
        )

        # Check to make sure the sock_dir is available, create if not
        default_minion_sock_dir = os.path.join(
            salt.syspaths.SOCK_DIR,
            'minion'
        )
        minion_sock_dir = self.opts.get('sock_dir', default_minion_sock_dir)

        if not os.path.isdir(minion_sock_dir):
            # Let's try to create the directory defined on the configuration
            # file
            try:
                os.makedirs(minion_sock_dir, 0o755)
            except OSError as exc:
                log.error('Could not create SOCK_DIR: {0}'.format(exc))
                # Let's not fail yet and try using the default path
                if minion_sock_dir == default_minion_sock_dir:
                    # We're already trying the default system path, stop now!
                    raise

            if not os.path.isdir(default_minion_sock_dir):
                try:
                    os.makedirs(default_minion_sock_dir, 0o755)
                except OSError as exc:
                    log.error('Could not create SOCK_DIR: {0}'.format(exc))
                    # Let's stop at this stage
                    raise

        # Create the pull socket
        self.epull_sock = self.context.socket(zmq.PULL)

        # Securely bind the event sockets
        if self.opts.get('ipc_mode', '') != 'tcp':
            old_umask = os.umask(0o177)
        try:
            log.info('Starting pub socket on {0}'.format(epub_uri))
            self.epub_sock.bind(epub_uri)
            log.info('Starting pull socket on {0}'.format(epull_uri))
            self.epull_sock.bind(epull_uri)
        finally:
            if self.opts.get('ipc_mode', '') != 'tcp':
                os.umask(old_umask)

        self.stream = zmq.eventloop.zmqstream.ZMQStream(self.epull_sock, io_loop=self.io_loop)
        self.stream.on_recv(self.handle_publish)

    def handle_publish(self, package):
        '''
        Get something from epull, publish it out epub, and return the package (or None)
        '''
        package = package[0]
        try:
            self.epub_sock.send(package)
            self.io_loop.spawn_callback(self.publish_handler, package)
            return package
        # Add an extra fallback in case a forked process leeks through
        except zmq.ZMQError as exc:
            # The interrupt caused by python handling the
            # SIGCHLD. Throws this error with errno == EINTR.
            # Nothing to receive on the zmq socket throws this error
            # with EAGAIN.
            # Both are safe to ignore
            if exc.errno != errno.EAGAIN and exc.errno != errno.EINTR:
                log.critical('Unexpected ZMQError while polling minion',
                             exc_info=True)
            return None

    def destroy(self):
        if hasattr(self, 'stream') and self.stream.closed is False:
            self.stream.close()
        if hasattr(self, 'epub_sock') and self.epub_sock.closed is False:
            self.epub_sock.close()
        if hasattr(self, 'epull_sock') and self.epull_sock.closed is False:
            self.epull_sock.close()
        if hasattr(self, 'context') and self.context.closed is False:
            self.context.term()

    def __del__(self):
        self.destroy()


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
        # Prepare master event pull socket
        self.epull_sock = self.context.socket(zmq.PULL)
        if self.opts.get('ipc_mode', '') == 'tcp':
            epub_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts.get('tcp_master_pub_port', 4512)
                )
            epull_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts.get('tcp_master_pull_port', 4513)
                )
        else:
            epub_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pub.ipc')
                )
            salt.utils.zeromq.check_ipc_path_max_len(epub_uri)
            epull_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pull.ipc')
                )
            salt.utils.zeromq.check_ipc_path_max_len(epull_uri)

        # Start the master event publisher
        old_umask = os.umask(0o177)
        try:
            self.epull_sock.bind(epull_uri)
            self.epub_sock.bind(epub_uri)
            if (self.opts.get('ipc_mode', '') != 'tcp' and (
                    self.opts.get('client_acl') or
                    self.opts.get('external_auth'))):
                os.chmod(os.path.join(
                    self.opts['sock_dir'], 'master_event_pub.ipc'), 0o666)
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
        self.event_queue = []
        self.stop = False

    def sig_stop(self, signum, frame):
        self.stop = True  # tell it to stop

    def flush_events(self):
        event_return = '{0}.event_return'.format(
            self.opts['event_return']
        )
        if event_return in self.minion.returners:
            try:
                self.minion.returners[event_return](self.event_queue)
            except Exception as exc:
                log.error('Could not store events {0}. '
                          'Returner raised exception: {1}'.format(
                    self.event_queue, exc))
            del self.event_queue[:]
        else:
            log.error(
                'Could not store return for event(s) {0}. Returner '
                '\'{1}\' not found.'
                    .format(self.event_queue, self.opts['event_return'])
            )

    def run(self):
        '''
        Spin up the multiprocess event returner
        '''
        # Properly exit if a SIGTERM is signalled
        signal.signal(signal.SIGTERM, self.sig_stop)

        salt.utils.appendproctitle(self.__class__.__name__)
        self.event = get_event('master', opts=self.opts, listen=True)
        events = self.event.iter_events(full=True)
        self.event.fire_event({}, 'salt/event_listen/start')
        try:
            for event in events:
                if self._filter(event):
                    self.event_queue.append(event)
                if len(self.event_queue) >= self.event_return_queue:
                    self.flush_events()
                if self.stop:
                    break
        except KeyboardInterrupt:
            if self.event_queue:
                self.flush_events()
            self.stop = True
        except zmq.error.ZMQError as exc:
            if exc.errno != errno.EINTR:  # Outside interrupt is a normal shutdown case
                raise
        finally:  # flush all we have at this moment
            if self.event_queue:
                self.flush_events()

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

        load.update({
            'id': self.opts['id'],
            'tag': tag,
            'data': data,
            'cmd': '_minion_event',
            'tok': self.auth.gen_token('salt'),
        })

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
            load['events'].append({
                'tag': tag,
                'data': running[stag],
            })
        channel = salt.transport.Channel.factory(self.opts)
        try:
            channel.send(load)
        except Exception:
            pass
        return True

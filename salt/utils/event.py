# -*- coding: utf-8 -*-
'''
Manage events

Events are all fired off via a zeromq 'pub' socket, and listened to with
local zeromq 'sub' sockets


All of the formatting is self contained in the event module, so
we should be able to modify the structure in the future since the same module
used to read events is the same module used to fire off events.

Old style event messages were comprised of two parts delimited
at the 20 char point. The first 20 characters are used for the zeromq
subscriber to match publications and 20 characters was chosen because it was at
the time a few more characters than the length of a jid (Job ID).
Any tags of length less than 20 characters were padded with "|" chars out to 20 characters.
Although not explicit, the data for an event comprised a python dict that was serialized by
msgpack.

New style event messages support event tags longer than 20 characters while still
being backwards compatible with old style tags.
The longer tags better enable name spaced event tags which tend to be longer.
Moreover, the constraint that the event data be a python dict is now an explicit
constraint and fire-event will now raise a ValueError if not. Tags must be
ascii safe strings, that is, have values less than 0x80

Since the msgpack dict (map) indicators have values greater than or equal to 0x80
it can be unambiguously determined if the start of data is at char 21 or not.

In the new style:
When the tag is longer than 20 characters, an end of tag string
is appended to the tag given by the string constant TAGEND, that is, two line feeds '\n\n'.
When the tag is less than 20 characters then the tag is padded with pipes
"|" out to 20 characters as before.
When the tag is exactly 20 characters no padded is done.

The get_event method intelligently figures out if the tag is longer than 20 characters.


The convention for namespacing is to use dot characters "." as the name space delimiter.
The name space "salt" is reserved by SaltStack for internal events.

For example:
Namespaced tag
    'salt.runner.manage.status.start'

'''

# Import python libs
import os
import fnmatch
import glob
import hashlib
import errno
import logging
import time
import datetime
import multiprocessing
from collections import MutableMapping

# Import third party libs
try:
    import zmq
except ImportError:
    # Local mode does not need zmq
    pass
import yaml

# Import salt libs
import salt.payload
import salt.loader
import salt.state
import salt.utils
import salt.utils.cache
import salt.utils.process
from salt._compat import string_types
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
    if transport == 'zeromq':
        if node == 'master':
            return MasterEvent(sock_dir or opts.get('sock_dir', None))
        return SaltEvent(node, sock_dir, opts)
    elif transport == 'raet':
        import salt.utils.raetevent
        return salt.utils.raetevent.SaltEvent(node,
                                              sock_dir=sock_dir,
                                              listen=listen,
                                              opts=opts)


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
        self.pending_events = []

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
            salt.utils.check_ipc_path_max_len(puburi)
            pulluri = 'ipc://{0}'.format(os.path.join(
                    sock_dir,
                    'master_event_pull.ipc'
                    ))
            salt.utils.check_ipc_path_max_len(pulluri)
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
                salt.utils.check_ipc_path_max_len(puburi)
                pulluri = 'ipc://{0}'.format(os.path.join(
                        sock_dir,
                        'minion_event_{0}_pull.ipc'.format(id_hash)
                        ))
                salt.utils.check_ipc_path_max_len(pulluri)
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
        self.sub.setsockopt(zmq.SUBSCRIBE, '')
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
        self.push.connect(self.pulluri)
        self.cpush = True

    @classmethod
    def unpack(cls, raw, serial=None):
        if serial is None:
            serial = salt.payload.Serial({'serial': 'msgpack'})

        if ord(raw[20]) >= 0x80:  # old style
            mtag = raw[0:20].rstrip('|')
            mdata = raw[20:]
        else:  # new style
            mtag, _, mdata = raw.partition(TAGEND)  # split tag from data

        data = serial.loads(mdata)
        return mtag, data

    def _check_pending(self, tag, pending_tags):
        """Check the pending_events list for events that match the tag

        :param tag: The tag to search for
        :type tag: str
        :param pending_tags: List of tags to preserve
        :type pending_tags: list[str]
        :return:
        """
        old_events = self.pending_events
        self.pending_events = []
        ret = None
        for evt in old_events:
            if evt['tag'].startswith(tag):
                if ret is None:
                    ret = evt
                else:
                    self.pending_events.append(evt)
            elif any(evt['tag'].startswith(ptag) for ptag in pending_tags):
                self.pending_events.append(evt)
        return ret

    def _get_event(self, wait, tag, pending_tags):
        start = time.time()
        timeout_at = start + wait
        while not wait or time.time() <= timeout_at:
            # convert to milliseconds
            socks = dict(self.poller.poll(wait * 1000))
            if socks.get(self.sub) != zmq.POLLIN:
                continue

            try:
                # Please do not use non-blocking mode here.
                # Reliability is more important than pure speed on the event bus.
                ret = self.get_event_block()
            except zmq.ZMQError as ex:
                if ex.errno == errno.EAGAIN or ex.errno == errno.EINTR:
                    continue
                else:
                    raise

            if not ret['tag'].startswith(tag):  # tag not match
                if any(ret['tag'].startswith(ptag) for ptag in pending_tags):
                    self.pending_events.append(ret)
                if wait:  # only update the wait timeout if we had one
                    wait = timeout_at - time.time()
                continue

            log.trace('get_event() received = {0}'.format(ret))
            return ret

        return None

    def get_event(self, wait=5, tag='', full=False, use_pending=False, pending_tags=None):
        '''
        Get a single publication.
        IF no publication available THEN block for up to wait seconds
        AND either return publication OR None IF no publication available.

        IF wait is 0 then block forever.

        New in Boron always checks the list of pending events

        use_pending
            Defines whether to keep all unconsumed events in a pending_events
            list, or to discard events that don't match the requested tag.  If
            set to True, MAY CAUSE MEMORY LEAKS.

        pending_tags
            Add any events matching the listed tags to the pending queue.
            Still MAY CAUSE MEMORY LEAKS but less likely than use_pending
            assuming you later get_event for the tags you've listed here

            New in Boron
        '''
        self.subscribe()

        if pending_tags is None:
            pending_tags = []
        if use_pending:
            pending_tags = ['']

        ret = self._check_pending(tag, pending_tags)
        if ret is None:
            ret = self._get_event(wait, tag, pending_tags)

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

        Supports new style long tags.
        The 0MQ push timeout on the send is set to timeout in milliseconds
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

        tagend = ''
        if len(tag) <= 20:  # old style compatible tag
            tag = '{0:|<20}'.format(tag)  # pad with pipes '|' to 20 character length
        else:  # new style longer than 20 chars
            tagend = TAGEND
        serialized_data = salt.utils.trim_dict(self.serial.dumps(data),
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
            self.sub.setsockopt(zmq.LINGER, linger)
            self.sub.close()
        if self.cpush is True and self.push.closed is False:
            self.push.setsockopt(zmq.LINGER, linger)
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
        self.destroy()


class MasterEvent(SaltEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, sock_dir):
        super(MasterEvent, self).__init__('master', sock_dir)


class LocalClientEvent(MasterEvent):
    '''
    This class is just used to differentiate who is handling the events,
    specially on logs, but it's the same as MasterEvent.
    '''


class MinionEvent(SaltEvent):
    '''
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
        salt.utils.check_ipc_path_max_len(epub_uri)
        # Prepare master event pull socket
        self.epull_sock = self.context.socket(zmq.PULL)
        epull_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pull.ipc')
                )
        salt.utils.check_ipc_path_max_len(epull_uri)

        # Start the master event publisher
        old_umask = os.umask(0177)
        try:
            self.epull_sock.bind(epull_uri)
            self.epub_sock.bind(epub_uri)
            if self.opts.get('client_acl') or self.opts.get('external_auth'):
                os.chmod(
                        os.path.join(self.opts['sock_dir'],
                            'master_event_pub.ipc'),
                        0666
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


class Reactor(multiprocessing.Process, salt.state.Compiler):
    '''
    Read in the reactor configuration variable and compare it to events
    processed on the master.
    The reactor has the capability to execute pre-programmed executions
    as reactions to events
    '''
    def __init__(self, opts):
        multiprocessing.Process.__init__(self)
        salt.state.Compiler.__init__(self, opts)

        local_minion_opts = self.opts.copy()
        local_minion_opts['file_client'] = 'local'
        self.minion = salt.minion.MasterMinion(local_minion_opts)

    def render_reaction(self, glob_ref, tag, data):
        '''
        Execute the render system against a single reaction file and return
        the data structure
        '''
        react = {}

        if glob_ref.startswith('salt://'):
            glob_ref = self.minion.functions['cp.cache_file'](glob_ref)

        for fn_ in glob.glob(glob_ref):
            try:
                react.update(self.render_template(
                    fn_,
                    tag=tag,
                    data=data))
            except Exception:
                log.error('Failed to render "{0}"'.format(fn_))
        return react

    def list_reactors(self, tag):
        '''
        Take in the tag from an event and return a list of the reactors to
        process
        '''
        log.debug('Gathering reactors for tag {0}'.format(tag))
        reactors = []
        if isinstance(self.opts['reactor'], string_types):
            try:
                with salt.utils.fopen(self.opts['reactor']) as fp_:
                    react_map = yaml.safe_load(fp_.read())
            except (OSError, IOError):
                log.error(
                    'Failed to read reactor map: "{0}"'.format(
                        self.opts['reactor']
                        )
                    )
            except Exception:
                log.error(
                    'Failed to parse YAML in reactor map: "{0}"'.format(
                        self.opts['reactor']
                        )
                    )
        else:
            react_map = self.opts['reactor']
        for ropt in react_map:
            if not isinstance(ropt, dict):
                continue
            if len(ropt) != 1:
                continue
            key = ropt.iterkeys().next()
            val = ropt[key]
            if fnmatch.fnmatch(tag, key):
                if isinstance(val, string_types):
                    reactors.append(val)
                elif isinstance(val, list):
                    reactors.extend(val)
        return reactors

    def reactions(self, tag, data, reactors):
        '''
        Render a list of reactor files and returns a reaction struct
        '''
        log.debug('Compiling reactions for tag {0}'.format(tag))
        high = {}
        chunks = []
        for fn_ in reactors:
            high.update(self.render_reaction(fn_, tag, data))
        if high:
            errors = self.verify_high(high)
            if errors:
                log.error(('Unable to render reactions for event {0} due to '
                           'errors ({1}) in one or more of the sls files ({2})').format(tag, errors, reactors))
                return []  # We'll return nothing since there was an error
            chunks = self.order_chunks(self.compile_high_data(high))
        return chunks

    def call_reactions(self, chunks):
        '''
        Execute the reaction state
        '''
        for chunk in chunks:
            self.wrap.run(chunk)

    def run(self):
        '''
        Enter into the server loop
        '''
        salt.utils.appendproctitle(self.__class__.__name__)

        # instantiate some classes inside our new process
        self.event = SaltEvent('master', self.opts['sock_dir'])
        self.wrap = ReactWrap(self.opts)

        for data in self.event.iter_events(full=True):
            reactors = self.list_reactors(data['tag'])
            if not reactors:
                continue
            chunks = self.reactions(data['tag'], data['data'], reactors)
            if chunks:
                self.call_reactions(chunks)


class ReactWrap(object):
    '''
    Create a wrapper that executes low data for the reaction system
    '''
    # class-wide cache of clients
    client_cache = None

    def __init__(self, opts):
        self.opts = opts
        if ReactWrap.client_cache is None:
            ReactWrap.client_cache = salt.utils.cache.CacheDict(opts['reactor_refresh_interval'])

        self.pool = salt.utils.process.ThreadPool(
            self.opts['reactor_worker_threads'],  # number of workers for runner/wheel
            queue_size=self.opts['reactor_worker_hwm']  # queue size for those workers
        )

    def run(self, low):
        '''
        Execute the specified function in the specified state by passing the
        LowData
        '''
        l_fun = getattr(self, low['state'])
        try:
            f_call = salt.utils.format_call(l_fun, low)
            l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        except Exception:
            log.error(
                    'Failed to execute {0}: {1}\n'.format(low['state'], l_fun),
                    exc_info=True
                    )

    def local(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        '''
        if 'local' not in self.client_cache:
            self.client_cache['local'] = salt.client.LocalClient(self.opts['conf_file'])
        self.client_cache['local'].cmd_async(*args, **kwargs)

    cmd = local

    def runner(self, fun, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        if 'runner' not in self.client_cache:
            self.client_cache['runner'] = salt.runner.RunnerClient(self.opts)
        self.pool.fire_async(self.client_cache['runner'].low, args=(fun, kwargs))

    def wheel(self, fun, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        if 'wheel' not in self.client_cache:
            self.client_cache['wheel'] = salt.wheel.Wheel(self.opts)
        self.pool.fire_async(self.client_cache['wheel'].low, args=(fun, kwargs))


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

        sreq = salt.transport.Channel.factory(self.opts)
        try:
            sreq.send(load)
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
        sreq = salt.transport.Channel.factory(self.opts)
        try:
            sreq.send(load)
        except Exception:
            pass
        return True

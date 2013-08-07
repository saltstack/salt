'''
Manage events
'''

# Events are all fired off via a zeromq pub socket, and listened to with
# local subscribers. The event messages are comprised of two parts delimited
# at the 20 char point. The first 20 characters are used for the zeromq
# subscriber to match publications and 20 characters were chosen because it is
# a few more characters than the length of a jid. The 20 characters
# are padded with "|" chars so that the msgpack component can be predictably
# extracted. All of the formatting is self contained in the event module, so
# we should be able to modify the structure in the future since the same module
# to read is the same module to fire off events.

# Import python libs
import time
import os
import fnmatch
import glob
import hashlib
import errno
import logging
import multiprocessing
from multiprocessing import Process

# Import third party libs
import zmq
import yaml

# Import salt libs
import salt.payload
import salt.loader
import salt.state
import salt.utils
from salt._compat import string_types
log = logging.getLogger(__name__)

# The SUB_EVENT set is for functions that require events fired based on
# component executions, like the state system
SUB_EVENT = set([
            'state.highstate',
            'state.sls',
            ])


class SaltEvent(object):
    '''
    The base class used to manage salt events
    '''
    def __init__(self, node, sock_dir=None, **kwargs):
        self.serial = salt.payload.Serial({'serial': 'msgpack'})
        self.context = zmq.Context()
        self.poller = zmq.Poller()
        self.cpub = False
        self.cpush = False
        self.puburi, self.pulluri = self.__load_uri(sock_dir, node, **kwargs)

    def __load_uri(self, sock_dir, node, **kwargs):
        '''
        Return the string URI for the location of the pull and pub sockets to
        use for firing and listening to events
        '''
        id_hash = hashlib.md5(kwargs.get('id', '')).hexdigest()
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
            if kwargs.get('ipc_mode', '') == 'tcp':
                puburi = 'tcp://127.0.0.1:{0}'.format(
                        kwargs.get('tcp_pub_port', 4510)
                        )
                pulluri = 'tcp://127.0.0.1:{0}'.format(
                        kwargs.get('tcp_pull_port', 4511)
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

    def subscribe(self, tag):
        '''
        Subscribe to events matching the passed tag.
        '''
        if not self.cpub:
            self.connect_pub()
        self.sub.setsockopt(zmq.SUBSCRIBE, tag)

    def unsubscribe(self, tag):
        '''
        Un-subscribe to events matching the passed tag.
        '''
        if not self.cpub:
            # There's no way we've even subscribed to this tag
            return
        self.sub.setsockopt(zmq.UNSUBSCRIBE, tag)

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(self.puburi)
        self.poller.register(self.sub, zmq.POLLIN)
        self.cpub = True

    def connect_pull(self):
        '''
        Establish a connection with the event pull socket
        '''
        self.push = self.context.socket(zmq.PUSH)
        self.push.connect(self.pulluri)
        self.cpush = True

    def get_event(self, wait=5, tag='', full=False):
        '''
        Get a single publication.
        IF no publication available THEN block for upto wait seconds
        AND either return publication OR None IF no publication available.
        
        IF wait is 0 then block forever.
        
        '''
        self.subscribe(tag)
        socks = dict(self.poller.poll(wait * 1000)) #convert to milliseconds
        if self.sub in socks and socks[self.sub] == zmq.POLLIN:
            raw = self.sub.recv()
            # Double check the tag
            if not raw[:20].rstrip('|').startswith(tag):
                return None
            data = self.serial.loads(raw[20:])
            if full:
                ret = {'data': data,
                        'tag': raw[:20].rstrip('|')}
                return ret
            return data
        return None


    def iter_events(self, tag='', full=False):
        '''
        Creates a generator that continuously listens for events
        '''
        while True:
            data = self.get_event(tag=tag, full=full)
            if data is None:
                continue
            yield data

    def fire_event(self, data, tag=''):
        '''
        Send a single event into the publisher
        '''
        if not self.cpush:
            self.connect_pull()
        tag = '{0:|<20}'.format(tag)
        event = '{0}{1}'.format(tag, self.serial.dumps(data))
        self.push.send(event)
        return True

    def destroy(self):
        if self.cpub is True and self.sub.closed is False:
            # Wait at most 2.5 secs to send any remaining messages in the
            # socket or the context.term() bellow will hang indefinitely.
            # See https://github.com/zeromq/pyzmq/issues/102
            self.sub.setsockopt(zmq.LINGER, 1)
            self.sub.close()
        if self.cpush is True and self.push.closed is False:
            self.push.setsockopt(zmq.LINGER, 1)
            self.push.close()
        # If sockets are not unregistered from a poller, nothing which touches
        # that poller gets garbage collected. The Poller itself, its
        # registered sockets and the Context
        for socket in self.poller.sockets.keys():
            if socket.closed is False:
                # Should already be closed from above, but....
                socket.setsockopt(zmq.LINGER, 1)
                socket.close()
            self.poller.unregister(socket)
        if self.context.closed is False:
            self.context.term()

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
                        tag = tag.split('_|-')
                        if data.get('result') is False:
                            self.fire_event(
                                    data,
                                    '{0}.{1}'.format(tag[0], tag[-1])
                                    )
                except Exception:
                    pass
            else:
                self.fire_event(load, load['fun'])

    def __del__(self):
        self.destroy()


class MasterEvent(SaltEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, sock_dir):
        super(MasterEvent, self).__init__('master', sock_dir)
        self.connect_pub()


class LocalClientEvent(MasterEvent):
    '''
    This class is just used to differentiate who is handling the events,
    specially on logs, but it's the same as MasterEvent.
    '''


class MinionEvent(SaltEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, **kwargs):
        super(MinionEvent, self).__init__('minion', **kwargs)


class EventPublisher(Process):
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
        # Set up the context
        self.context = zmq.Context(1)
        # Prepare the master event publisher
        self.epub_sock = self.context.socket(zmq.PUB)
        epub_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pub.ipc')
                )
        # Prepare master event pull socket
        self.epull_sock = self.context.socket(zmq.PULL)
        epull_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pull.ipc')
                )
        # Start the master event publisher
        self.epub_sock.bind(epub_uri)
        self.epull_sock.bind(epull_uri)
        # Restrict access to the sockets
        pub_mode = 448
        if self.opts.get('client_acl') or self.opts.get('external_auth'):
            pub_mode = 511
        os.chmod(
                os.path.join(self.opts['sock_dir'],
                    'master_event_pub.ipc'),
                pub_mode
                )
        os.chmod(
                os.path.join(self.opts['sock_dir'],
                    'master_event_pull.ipc'),
                448
                )

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
                self.epub_sock.setsockopt(zmq.LINGER, 1)
                self.epub_sock.close()
            if self.epull_sock.closed is False:
                self.epull_sock.setsockopt(zmq.LINGER, 1)
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
        self.wrap = ReactWrap(self.opts)

    def render_reaction(self, glob_ref, tag, data):
        '''
        Execute the render system against a single reaction file and return
        the data structure
        '''
        react = {}
        for fn_ in glob.glob(glob_ref):
            react.update(self.render_template(
                    fn_,
                    tag=tag,
                    data=data))
        return react

    def list_reactors(self, tag):
        '''
        Take in the tag from an event and return a list of the reactors to
        process
        '''
        log.debug('Gathering reactors for tag {0}'.format(tag))
        reactors = []
        if isinstance(self.opts['reactor'], basestring):
            try:
                with open(self.opts['reactor']) as fp_:
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
            key = ropt.keys()[0]
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
                return errors
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
        self.event = SaltEvent('master', self.opts['sock_dir'])
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
    def __init__(self, opts):
        self.opts = opts

    def run(self, low):
        '''
        Execute the specified function in the specified state by passing the
        LowData
        '''
        l_fun = getattr(self, low['state'])
        f_call = salt.utils.format_call(l_fun, low)
        try:
            ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        except Exception:
            log.error(
                    'Failed to execute {0}: {1}\n'.format(low['state'], l_fun),
                    exc_info=True
                    )
            return ret
        return ret

    def cmd(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        '''
        local = salt.client.LocalClient(self.opts['conf_file'])
        return local.cmd_async(*args, **kwargs)

    def runner(self, fun, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        runner = salt.runner.RunnerClient(self.opts)
        return runner.low(fun, kwargs)

    def wheel(self, fun, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.Wheel(self.opts)
        return wheel.call_func(**kwargs)


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

    def fire_master(self, data, tag):
        '''
        Fire an event off on the master server

        CLI Example::

            salt '*' event.fire_master 'stuff to be in the event' 'tag'
        '''
        load = {'id': self.opts['id'],
                'tag': tag,
                'data': data,
                'cmd': '_minion_event'}
        sreq = salt.payload.SREQ(self.opts['master_uri'])
        try:
            sreq.send('aes', self.auth.crypticle.dumps(load))
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
        sreq = salt.payload.SREQ(self.opts['master_uri'])
        try:
            sreq.send('aes', self.auth.crypticle.dumps(load))
        except Exception:
            pass
        return True

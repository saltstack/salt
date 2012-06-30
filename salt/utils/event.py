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
#
#
# Import Python libs
import os
import errno
import multiprocessing

# Import Third Party libs
import zmq

# Import Salt libs
import salt.payload


class SaltEvent(object):
    '''
    The base class used to manage salt events
    '''
    def __init__(self, sock_dir, node):
        self.serial = salt.payload.Serial({'serial': 'msgpack'})
        self.context = zmq.Context()
        self.poller = zmq.Poller()
        self.cpub = False
        self.cpush = False
        if node == 'master':
            self.puburi = 'ipc://{0}'.format(os.path.join(
                    sock_dir,
                    'master_event_pub.ipc'
                    ))
            self.pulluri = 'ipc://{0}'.format(os.path.join(
                    sock_dir,
                    'master_event_pull.ipc'
                    ))
        else:
            self.puburi = 'ipc://{0}'.format(os.path.join(
                    sock_dir,
                    'minion_event_pub.ipc'
                    ))
            self.pulluri = 'ipc://{0}'.format(os.path.join(
                    sock_dir,
                    'minion_event_pull.ipc'
                    ))

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
        Get a single publication
        '''
        if not self.cpub:
            self.connect_pub()
        self.sub.setsockopt(zmq.SUBSCRIBE, tag)
        while True:
            socks = dict(self.poller.poll(wait))
            if self.sub in socks and socks[self.sub] == zmq.POLLIN:
                raw = self.sub.recv()
                data = self.serial.loads(raw[20:])
                if full:
                    ret = {'data': data,
                           'tag': raw[:20].rstrip('|')}
                    return ret
                return data
            else:
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
        tag += 20 * '|'
        tag = tag[:20]
        event = '{0}{1}'.format(tag, self.serial.dumps(data))
        self.push.send(event)
        return True


class MasterEvent(SaltEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, sock_dir):
        super(MasterEvent, self).__init__(sock_dir, 'master')
        self.connect_pub()


class MinionEvent(SaltEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, sock_dir):
        super(MinionEvent, self).__init__(sock_dir, 'minion')


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
        # Set up the context
        context = zmq.Context(1)
        # Prepare the master event publisher
        epub_sock = context.socket(zmq.PUB)
        epub_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pub.ipc')
                )
        # Prepare master event pull socket
        epull_sock = context.socket(zmq.PULL)
        epull_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'master_event_pull.ipc')
                )
        # Start the master event publisher
        epub_sock.bind(epub_uri)
        epull_sock.bind(epull_uri)
        # Restrict access to the sockets
        os.chmod(
                os.path.join(self.opts['sock_dir'],
                    'master_event_pub.ipc'),
                448
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
                    package = epull_sock.recv()
                    epub_sock.send(package)
                except zmq.ZMQError as exc:
                    if exc.errno == errno.EINTR:
                        continue
                    raise exc
        except KeyboardInterrupt:
            epub_sock.close()
            epull_sock.close()

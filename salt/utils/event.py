'''
Manage event listeners.
'''

# Import Python libs
import os

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

    def get_event(self, wait=5, tag=''):
        '''
        Get a single publication
        '''
        if not self.cpub:
            self.connect_pub()
        self.sub.setsockopt(zmq.SUBSCRIBE, tag)
        start = time.time()
        while True:
            socks = dict(self.poller.poll())
            if self.pub in socks and socks[self.pub] == zmq.POLLIN:
                return self.sub.recv()
            if (time.time() - start) > wait:
                return None

    def fire_event(self, data, tag=''):
        '''
        Send a single event into the publisher
        '''
        if not self.cpush:
            self.connect_pull()
        tag += 20*'|'
        tag = tag[:20]
        event = '{0}{1}'.format(tag, self.serial.dump(data))
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

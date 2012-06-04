'''
Manage event listeners.
'''

# Import Python libs
import os

# Import Third Party libs
import zmq


class SaltEvent(object):
    '''
    The base class used to manage salt events
    '''
    def __init__(self, sock_dir, node):
        self.poller = zmq.Poller()
        self.cpub = False
        if node == 'master':
            self.puburi = os.path.join(
                    sock_dir,
                    'master_event_pub.ipc'
                    )
            self.pulluri = os.path.join(
                    sock_dir,
                    'master_event_pull.ipc'
                    )
        else:
            self.puburi = os.path.join(
                    sock_dir,
                    'minion_event_pub.ipc'
                    )
            self.pulluri = os.path.join(
                    sock_dir,
                    'minion_event_pull.ipc'
                    )

    def connect_pub(self):
        '''
        Establish the publish connection
        '''
        self.context = zmq.context()
        self.sub = context.socket(zmq.SUB)
        self.sub.connect(self.puburi)
        self.poller.register(self.pub, zmq.POLLIN)
        self.cpub = True

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


class MasterEvent(SaltEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, sock_dir):
        super(MasterEvent, self).__init__(sock_dir, 'master')


class MinionEvent(SaltEvent):
    '''
    Create a master event management object
    '''
    def __init__(self, sock_dir):
        super(MinionEvent, self).__init__(sock_dir, 'minion')

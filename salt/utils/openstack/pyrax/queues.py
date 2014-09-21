# Import Python libs
import logging
import json
import uuid

client_uuid = str(uuid.uuid4())

log = logging.getLogger(__name__)

# Import pyrax (SDK for Rackspace cloud) third party libs
import pyrax
import pyrax.exceptions

# Import salt classes
import authenticate
from salt._compat import string_types

class RackspaceQueues(object):
    def __init__(self, username, password, region, **kwargs):
        self.auth = authenticate.Authenticate(username, password, region, **kwargs)
        self.conn = self.auth.conn.queues

    def create(self, qname):
        '''
        Create RackSpace Queue.
        '''
        try:
            if self.exists(qname):
                log.error('Queues "%s" already exists. Nothing done.' % qname)
                print "Allready exists"
                return True

            self.conn.create(qname)

            return True
        except pyrax.exceptions as err_msg:
            log.error('RackSpace API got some problems during creation: %s' % err_msg)

    def delete(self, qname):
        '''
        Delete an existings RackSpace Queue.
        '''

        try:
            q = self.exists(qname)
            if not q:
                return False
            q.delete()

        except pyrax.exceptions as err_msg:
            log.error('RackSpace API got some problems during deletion: %s' % err_msg)
            return False

        return True
        
    def exists(self, qname):
        '''
        Check to see if a Queue exists.
        '''
        try:
            # First if not exists() -> exit
            if not self.conn.queue_exists(qname):
                return False
            # If exist, search the queue to return the Queue Object
            for queue in self.conn.list():
                if queue.name == qname:
                    return queue
        except pyrax.exceptions as err_msg:
            log.error('RackSpace API got some problems during existing queue check: %s' % err_msg)
        return False

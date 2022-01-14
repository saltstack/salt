import logging

# pylint: disable=3rd-party-module-not-gated
import pyrax
import pyrax.exceptions  # pylint: disable=no-name-in-module

# Import salt classes
from salt.utils.openstack.pyrax import authenticate

log = logging.getLogger(__name__)


# pylint: enable=3rd-party-module-not-gated


class RackspaceQueues:
    def __init__(self, username, password, region, **kwargs):
        self.auth = authenticate.Authenticate(username, password, region, **kwargs)
        self.conn = self.auth.conn.queues

    def create(self, qname):
        """
        Create RackSpace Queue.
        """
        try:
            if self.exists(qname):
                log.error('Queues "%s" already exists. Nothing done.', qname)
                return True

            self.conn.create(qname)

            return True
        except pyrax.exceptions as err_msg:
            log.error("RackSpace API got some problems during creation: %s", err_msg)
        return False

    def delete(self, qname):
        """
        Delete an existings RackSpace Queue.
        """
        try:
            q = self.exists(qname)
            if not q:
                return False
            queue = self.show(qname)
            if queue:
                queue.delete()
        except pyrax.exceptions as err_msg:
            log.error("RackSpace API got some problems during deletion: %s", err_msg)
            return False

        return True

    def exists(self, qname):
        """
        Check to see if a Queue exists.
        """
        try:
            # First if not exists() -> exit
            if self.conn.queue_exists(qname):
                return True
            return False
        except pyrax.exceptions as err_msg:
            log.error(
                "RackSpace API got some problems during existing queue check: %s",
                err_msg,
            )
        return False

    def show(self, qname):
        """
        Show information about Queue
        """
        try:
            # First if not exists() -> exit
            if not self.conn.queue_exists(qname):
                return {}
            # If exist, search the queue to return the Queue Object
            for queue in self.conn.list():
                if queue.name == qname:
                    return queue
        except pyrax.exceptions as err_msg:
            log.error(
                "RackSpace API got some problems during existing queue check: %s",
                err_msg,
            )
        return {}

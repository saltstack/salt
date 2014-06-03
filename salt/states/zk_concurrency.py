# -*- coding: utf-8 -*-
'''
Control concurrency of steps within state execution using zookeeper
=========================================================================

This module allows you to "wrap" a state's execution with concurrency control.
This is useful to protect against all hosts executing highstate simultaneously
if your services don't all HUP restart. The common way of protecting against this
is to run in batch mode, but that doesn't protect from another person running
the same batch command (and thereby having 2x the number of nodes deploying at once).

This module will bock while acquiring a slot, meaning that however the command gets
called it will coordinate with zookeeper to ensure that no more than max_concurrency
steps are executing with a single path.

.. code-block:: yaml

    acquire_lock:
      zk_concurrency.lock:
        - zk_hosts: 'zookeeper:2181'
        - path: /trafficserver
        - max_concurrency: 4
        - prereq:
            - service: trafficserver

    trafficserver:
      service.running:
        - watch:
          - file: /etc/trafficserver/records.config

    /etc/trafficserver/records.config:
      file.managed:
        - source: salt://records.config

    release_lock:
      zk_concurrency.unlock:
        - path: /trafficserver
        - require:
            - service: trafficserver

This example would allow the file state to change, but would limit the
concurrency of the trafficserver service restart to 4.
'''

import logging

try:
    from kazoo.client import KazooClient

    from kazoo.retry import (
        ForceRetryError
    )
    import kazoo.recipe.lock
    from kazoo.exceptions import CancelledError
    from kazoo.exceptions import NoNodeError

    # TODO: use the kazoo one, waiting for pull req:
    # https://github.com/python-zk/kazoo/pull/206
    class _Semaphore(kazoo.recipe.lock.Semaphore):
        def __init__(self,
                    client,
                    path,
                    identifier=None,
                    max_leases=1,
                    ephemeral_lease=True,
                    ):
            kazoo.recipe.lock.Semaphore.__init__(self,
                                                client,
                                                path,
                                                identifier=identifier,
                                                max_leases=max_leases)
            self.ephemeral_lease = ephemeral_lease

            # if its not ephemeral, make sure we didn't already grab it
            if not self.ephemeral_lease:
                for child in self.client.get_children(self.path):
                    try:
                        data, stat = self.client.get(self.path + "/" + child)
                        if identifier == data.decode('utf-8'):
                            self.create_path = self.path + "/" + child
                            self.is_acquired = True
                            break
                    except NoNodeError:  # pragma: nocover
                        pass

        def _get_lease(self, data=None):
            # Make sure the session is still valid
            if self._session_expired:
                raise ForceRetryError("Retry on session loss at top")

            # Make sure that the request hasn't been canceled
            if self.cancelled:
                raise CancelledError("Semaphore cancelled")

            # Get a list of the current potential lock holders. If they change,
            # notify our wake_event object. This is used to unblock a blocking
            # self._inner_acquire call.
            children = self.client.get_children(self.path,
                                                self._watch_lease_change)

            # If there are leases available, acquire one
            if len(children) < self.max_leases:
                self.client.create(self.create_path, self.data, ephemeral=self.ephemeral_lease)

            # Check if our acquisition was successful or not. Update our state.
            if self.client.exists(self.create_path):
                self.is_acquired = True
            else:
                self.is_acquired = False

            # Return current state
            return self.is_acquired

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

ZK_CONNECTION = None
SEMAPHORE_MAP = {}

__virtualname__ = 'zk_concurrency'


def __virtual__():
    if not HAS_DEPS:
        return False

    return __virtualname__


def _get_zk_conn(hosts):
    global ZK_CONNECTION
    if ZK_CONNECTION is None:
        ZK_CONNECTION = KazooClient(hosts=hosts)
        ZK_CONNECTION.start()

    return ZK_CONNECTION


def _close_zk_conn():
    global ZK_CONNECTION
    if ZK_CONNECTION is None:
        return

    ZK_CONNECTION.stop()
    ZK_CONNECTION = None


def lock(zk_hosts,
         path,
         max_concurrency,
         timeout=None,
         ephemeral_lease=False):
    '''
    Block state execution until you are able to get the lock (or hit the timeout)

    '''
    ret = {'name': path,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'attempt to aqcuire lock'
        return ret

    zk = _get_zk_conn(zk_hosts)
    if path not in SEMAPHORE_MAP:
        SEMAPHORE_MAP[path] = _Semaphore(zk,
                                        path,
                                        __grains__['id'],
                                        max_leases=max_concurrency,
                                        ephemeral_lease=ephemeral_lease)
    # block waiting for lock acquisition
    if timeout:
        logging.info('Acquiring lock with timeout={0}'.format(timeout))
        SEMAPHORE_MAP[path].acquire(timeout=timeout)
    else:
        logging.info('Acquiring lock with no timeout')
        SEMAPHORE_MAP[path].acquire()

    if SEMAPHORE_MAP[path].is_acquired:
        ret['result'] = True
        ret['comment'] = 'lock acquired'
    else:
        ret['comment'] = 'Unable to acquire lock'

    return ret


def unlock(path):
    '''
    Remove lease from semaphore
    '''
    ret = {'name': path,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'released lock if its here'
        return ret

    if path in SEMAPHORE_MAP:
        SEMAPHORE_MAP[path].release()
        del SEMAPHORE_MAP[path]
    else:
        ret['comment'] = 'Unable to find lease for path {0}'.format(path)
        return ret

    ret['result'] = True
    return ret

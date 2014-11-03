# -*- coding: utf-8 -*-
'''
Concurrency controls in zookeeper
=========================================================================

This module allows you to acquire and release a slot. This is primarily useful
for ensureing that no more than N hosts take a specific action at once. This can
also be used to coordinate between masters.
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
                try:
                    for child in self.client.get_children(self.path):
                        try:
                            data, stat = self.client.get(self.path + "/" + child)
                            if identifier == data.decode('utf-8'):
                                self.create_path = self.path + "/" + child
                                self.is_acquired = True
                                break
                        except NoNodeError:  # pragma: nocover
                            pass
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


def lock_holders(path,
                 zk_hosts,
                 identifier=None,
                 max_concurrency=1,
                 timeout=None,
                 ephemeral_lease=False):
    '''
    Return an un-ordered list of lock holders
    '''

    zk = _get_zk_conn(zk_hosts)
    if path not in SEMAPHORE_MAP:
        SEMAPHORE_MAP[path] = _Semaphore(zk,
                                        path,
                                        identifier,
                                        max_leases=max_concurrency,
                                        ephemeral_lease=ephemeral_lease)
    return SEMAPHORE_MAP[path].lease_holders()


def lock(path,
         zk_hosts,
         identifier=None,
         max_concurrency=1,
         timeout=None,
         ephemeral_lease=False,
         force=False,  # foricble get the lock regardless of open slots
         ):
    '''
    Get lock (with optional timeout)
    '''
    zk = _get_zk_conn(zk_hosts)
    if path not in SEMAPHORE_MAP:
        SEMAPHORE_MAP[path] = _Semaphore(zk,
                                        path,
                                        identifier,
                                        max_leases=max_concurrency,
                                        ephemeral_lease=ephemeral_lease)

    # forcibly get the lock regardless of max_concurrency
    if force:
        SEMAPHORE_MAP[path].assured_path = True

    # block waiting for lock acquisition
    if timeout:
        logging.info('Acquiring lock {0} with timeout={1}'.format(path, timeout))
        SEMAPHORE_MAP[path].acquire(timeout=timeout)
    else:
        logging.info('Acquiring lock {0} with no timeout'.format(path))
        SEMAPHORE_MAP[path].acquire()

    return SEMAPHORE_MAP[path].is_acquired


def unlock(path,
           zk_hosts=None,  # in case you need to unlock without having run lock (failed execution for example)
           identifier=None,
           max_concurrency=1,
           ephemeral_lease=False
           ):
    '''
    Remove lease from semaphore
    '''
    # if someone passed in zk_hosts, and the path isn't in SEMAPHORE_MAP, lets
    # see if we can find it
    if zk_hosts is not None and path not in SEMAPHORE_MAP:
        zk = _get_zk_conn(zk_hosts)
        SEMAPHORE_MAP[path] = _Semaphore(zk,
                                        path,
                                        identifier,
                                        max_leases=max_concurrency,
                                        ephemeral_lease=ephemeral_lease)

    if path in SEMAPHORE_MAP:
        SEMAPHORE_MAP[path].release()
        del SEMAPHORE_MAP[path]
        return True
    else:
        logging.error('Unable to find lease for path {0}'.format(path))
        return False

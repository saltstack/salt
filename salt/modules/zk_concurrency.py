# -*- coding: utf-8 -*-
"""
Concurrency controls in zookeeper
=========================================================================

:depends: kazoo
:configuration: See :py:mod:`salt.modules.zookeeper` for setup instructions.

This module allows you to acquire and release a slot. This is primarily useful
for ensureing that no more than N hosts take a specific action at once. This can
also be used to coordinate between masters.
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import sys

try:
    import kazoo.client

    from kazoo.retry import ForceRetryError
    import kazoo.recipe.lock
    import kazoo.recipe.barrier
    import kazoo.recipe.party
    from kazoo.exceptions import CancelledError
    from kazoo.exceptions import NoNodeError
    from socket import gethostname

    # TODO: use the kazoo one, waiting for pull req:
    # https://github.com/python-zk/kazoo/pull/206
    class _Semaphore(kazoo.recipe.lock.Semaphore):
        def __init__(
            self, client, path, identifier=None, max_leases=1, ephemeral_lease=True,
        ):
            identifier = identifier or gethostname()
            kazoo.recipe.lock.Semaphore.__init__(
                self, client, path, identifier=identifier, max_leases=max_leases
            )
            self.ephemeral_lease = ephemeral_lease

            # if its not ephemeral, make sure we didn't already grab it
            if not self.ephemeral_lease:
                try:
                    for child in self.client.get_children(self.path):
                        try:
                            data, stat = self.client.get(self.path + "/" + child)
                            if identifier == data.decode("utf-8"):
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
            children = self.client.get_children(self.path, self._watch_lease_change)

            # If there are leases available, acquire one
            if len(children) < self.max_leases:
                self.client.create(
                    self.create_path, self.data, ephemeral=self.ephemeral_lease
                )

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


__virtualname__ = "zk_concurrency"


def __virtual__():
    if not HAS_DEPS:
        return (False, "Module zk_concurrency: dependencies failed")

    __context__["semaphore_map"] = {}

    return __virtualname__


def _get_zk_conn(profile=None, **connection_args):
    if profile:
        prefix = "zookeeper:" + profile
    else:
        prefix = "zookeeper"

    def get(key, default=None):
        """
        look in connection_args first, then default to config file
        """
        return connection_args.get(key) or __salt__["config.get"](
            ":".join([prefix, key]), default
        )

    hosts = get("hosts", "127.0.0.1:2181")
    scheme = get("scheme", None)
    username = get("username", None)
    password = get("password", None)
    default_acl = get("default_acl", None)

    if isinstance(hosts, list):
        hosts = ",".join(hosts)

    if username is not None and password is not None and scheme is None:
        scheme = "digest"

    auth_data = None
    if scheme and username and password:
        auth_data = [(scheme, ":".join([username, password]))]

    if default_acl is not None:
        if isinstance(default_acl, list):
            default_acl = [
                __salt__["zookeeper.make_digest_acl"](**acl) for acl in default_acl
            ]
        else:
            default_acl = [__salt__["zookeeper.make_digest_acl"](**default_acl)]

    __context__.setdefault("zkconnection", {}).setdefault(
        profile or hosts,
        kazoo.client.KazooClient(
            hosts=hosts, default_acl=default_acl, auth_data=auth_data
        ),
    )

    if not __context__["zkconnection"][profile or hosts].connected:
        __context__["zkconnection"][profile or hosts].start()

    return __context__["zkconnection"][profile or hosts]


def lock_holders(
    path,
    zk_hosts=None,
    identifier=None,
    max_concurrency=1,
    timeout=None,
    ephemeral_lease=False,
    profile=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Return an un-ordered list of lock holders

    path
        The path in zookeeper where the lock is

    zk_hosts
        zookeeper connect string

    identifier
        Name to identify this minion, if unspecified defaults to hostname

    max_concurrency
        Maximum number of lock holders

    timeout
        timeout to wait for the lock. A None timeout will block forever

    ephemeral_lease
        Whether the locks in zookeper should be ephemeral

    Example:

    .. code-block:: bash

        salt minion zk_concurrency.lock_holders /lock/path host1:1234,host2:1234
    """
    zk = _get_zk_conn(
        profile=profile,
        hosts=zk_hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    if path not in __context__["semaphore_map"]:
        __context__["semaphore_map"][path] = _Semaphore(
            zk,
            path,
            identifier,
            max_leases=max_concurrency,
            ephemeral_lease=ephemeral_lease,
        )
    return __context__["semaphore_map"][path].lease_holders()


def lock(
    path,
    zk_hosts=None,
    identifier=None,
    max_concurrency=1,
    timeout=None,
    ephemeral_lease=False,
    force=False,  # foricble get the lock regardless of open slots
    profile=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Get lock (with optional timeout)

    path
        The path in zookeeper where the lock is

    zk_hosts
        zookeeper connect string

    identifier
        Name to identify this minion, if unspecified defaults to the hostname

    max_concurrency
        Maximum number of lock holders

    timeout
        timeout to wait for the lock. A None timeout will block forever

    ephemeral_lease
        Whether the locks in zookeper should be ephemeral

    force
        Forcibly acquire the lock regardless of available slots

    Example:

    .. code-block:: bash

        salt minion zk_concurrency.lock /lock/path host1:1234,host2:1234
    """
    zk = _get_zk_conn(
        profile=profile,
        hosts=zk_hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    if path not in __context__["semaphore_map"]:
        __context__["semaphore_map"][path] = _Semaphore(
            zk,
            path,
            identifier,
            max_leases=max_concurrency,
            ephemeral_lease=ephemeral_lease,
        )

    # forcibly get the lock regardless of max_concurrency
    if force:
        __context__["semaphore_map"][path].assured_path = True
        __context__["semaphore_map"][path].max_leases = sys.maxint

    # block waiting for lock acquisition
    if timeout:
        logging.info("Acquiring lock %s with timeout=%s", path, timeout)
        __context__["semaphore_map"][path].acquire(timeout=timeout)
    else:
        logging.info("Acquiring lock %s with no timeout", path)
        __context__["semaphore_map"][path].acquire()

    return __context__["semaphore_map"][path].is_acquired


def unlock(
    path,
    zk_hosts=None,  # in case you need to unlock without having run lock (failed execution for example)
    identifier=None,
    max_concurrency=1,
    ephemeral_lease=False,
    scheme=None,
    profile=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Remove lease from semaphore

    path
        The path in zookeeper where the lock is

    zk_hosts
        zookeeper connect string

    identifier
        Name to identify this minion, if unspecified defaults to hostname

    max_concurrency
        Maximum number of lock holders

    timeout
        timeout to wait for the lock. A None timeout will block forever

    ephemeral_lease
        Whether the locks in zookeper should be ephemeral

    Example:

    .. code-block:: bash

        salt minion zk_concurrency.unlock /lock/path host1:1234,host2:1234
    """
    # if someone passed in zk_hosts, and the path isn't in __context__['semaphore_map'], lets
    # see if we can find it
    zk = _get_zk_conn(
        profile=profile,
        hosts=zk_hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    if path not in __context__["semaphore_map"]:
        __context__["semaphore_map"][path] = _Semaphore(
            zk,
            path,
            identifier,
            max_leases=max_concurrency,
            ephemeral_lease=ephemeral_lease,
        )

    if path in __context__["semaphore_map"]:
        __context__["semaphore_map"][path].release()
        del __context__["semaphore_map"][path]
        return True
    else:
        logging.error("Unable to find lease for path %s", path)
        return False


def party_members(
    path,
    zk_hosts=None,
    min_nodes=1,
    blocking=False,
    profile=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Get the List of identifiers in a particular party, optionally waiting for the
    specified minimum number of nodes (min_nodes) to appear

    path
        The path in zookeeper where the lock is

    zk_hosts
        zookeeper connect string

    min_nodes
        The minimum number of nodes expected to be present in the party

    blocking
        The boolean indicating if we need to block until min_nodes are available

    Example:

    .. code-block:: bash

        salt minion zk_concurrency.party_members /lock/path host1:1234,host2:1234
        salt minion zk_concurrency.party_members /lock/path host1:1234,host2:1234 min_nodes=3 blocking=True
    """
    zk = _get_zk_conn(
        profile=profile,
        hosts=zk_hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    party = kazoo.recipe.party.ShallowParty(zk, path)
    if blocking:
        barrier = kazoo.recipe.barrier.DoubleBarrier(zk, path, min_nodes)
        barrier.enter()
        party = kazoo.recipe.party.ShallowParty(zk, path)
        barrier.leave()
    return list(party)

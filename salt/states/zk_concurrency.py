'''
This state module is intended soely for controlling concurrency of the state
execution. It maintains no other state
'''

import logging
import os
import time

try:
    from kazoo.client import KazooClient
    import kazoo.exceptions
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

ZK_CONNECTION = None

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
         timeout=None):
    '''
    Block state execution until you are able to get the lock (or hit the timeout)
    '''
    SLEEP_TIME = 0.2
    ret = {'name': path,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'attempt to aqcuire lock'
        return ret

    zk = _get_zk_conn(zk_hosts)
    # makse sure the base lock path
    zk.ensure_path(path)

    slot = False
    if timeout is not None:
        timeout = time.time() + timeout
    # TODO: the timeout
    while slot is False and (timeout is None or time.time() < timeout):
        children, znode = zk.get_children(path, include_data=True)
        if len(children) >= max_concurrency:
            time.sleep(SLEEP_TIME)
            continue
        # if we got here, get a lock
        lock_path = os.path.join(path, __grains__['fqdn'])

        # TODO: fix this obvious race condition (create after len check-- need to check cversion somehow)
        try:
            zk.create(lock_path, '')
        except kazoo.exceptions.NodeExistsError:
            # TODO clobber? Maybe have an option for that
            ret['result'] = False
            ret['comment'] = 'lock already exists for this host... something weird'
            return ret

        # check # of connections again
        children, znode = zk.get_children(path, include_data=True)
        if len(children) > max_concurrency:
            zk.delete(lock_path)
            time.sleep(SLEEP_TIME)
            continue

        slot = True

    if slot:
        ret['result'] = True
        ret['comment'] = 'lock acquired'
    else:
        ret['comment'] = 'Unable to acquire lock'

    return ret


def unlock(zk_hosts, path):
    ret = {'name': path,
           'changes': {},
           'result': False,
           'comment': ''}
    zk = _get_zk_conn(zk_hosts)

    lock_path = os.path.join(path, __grains__['fqdn'])

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'released lock if its here'
        return ret

    try:
        zk.delete(lock_path)
        ret['comment'] = 'lock released'
    except kazoo.exceptions.NoNodeError:
        ret['comment'] = 'lock did not exist'

    zk.stop()

    ret['result'] = True
    return ret

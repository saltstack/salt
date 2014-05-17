'''
This state module is intended soely for controlling concurrency of the state
execution. It maintains no other state
'''

import logging
import os

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

def lock(zk_hosts, path, max_concurrency):
    ret = {'name': path,
           'changes': {},
           'result': False,
           'comment': ''}
    zk = _get_zk_conn(zk_hosts)
    # makse sure the base lock path
    zk.ensure_path(path)

    children, znode = zk.get_children(path, include_data=True)

    lock_path = os.path.join(path, __grains__['fqdn'])

    if len(children) >= max_concurrency:
        ret['comment'] = 'unable to acquire lock curr:{0} >= max:{1}'.format(len(children), max_concurrency)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'could aqcuire lock'
        return ret


    # TODO: fix this obvious race condition (create after len check-- need to check cversion somehow)
    try:
        zk.create(lock_path, '')
    except kazoo.exceptions.NodeExistsError:
        ret['result'] = False
        ret['comment'] = 'lock already exists for this host... something weird'
        return ret

    ret['result'] = True
    ret['comment'] = 'lock acquired'
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

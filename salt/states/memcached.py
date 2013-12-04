# -*- coding: utf-8 -*-
'''

Management of Memcached Server.
=====================================================

This module is used to manage memcached server.
'''

def set(name,
        host=None,
        port=None,
        val=None):
    '''
    Set key to memcached server.

    name
        The key

    host
        The memcached server ip

    port
        The memcached server port

    value
        The value

    .. code-block:: yaml

        k1:
          memcached.set:
            - host: 10.0.0.1
            - port: 11211
            - val: v1
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check memcached server
    if __salt__['memcached.status'](host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('set key {0} to memcached server {1}:{2}'
                    ).format(name, host, port)
            return ret
        if __salt__['memcached.set'](host, port, name, val):
            ret['comment'] = 'set key {0} to memcached server {1}:{2}'.format(name, host, port)
            ret['changes'][name] = 'to be set'
            return ret

    ret['comment'] = ('memcached server {0}:{1} is down or not exists.'
                     ).format(host,port)
    return ret

def get(name,
        host=None,
        port=None):
    '''
    Get key to memcached server.

    name
        The key

    host
        The memcached server ip

    port
        The memcached server port

    .. code-block:: yaml

        k1:
          memcached.get:
            - host: 10.0.0.1
            - port: 11211
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check memcached server
    if __salt__['memcached.status'](host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('get key {0} from memcached server {1}:{2}'
                    ).format(name, host, port)
            return ret
        ret['comment'] = __salt__['memcached.get'](host, port, name)
        return ret

    ret['comment'] = ('memcached server {0}:{1} is down or not exists.'
                     ).format(host,port)
    return ret


def delete(name,
        host=None,
        port=None):
    '''
    Delete key from memcached server.

    name
        The key

    host
        The memcached server ip

    port
        The memcached server port

    .. code-block:: yaml

        k1:
          memcached.delete:
            - host: 10.0.0.1
            - port: 11211
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check memcached server
    if __salt__['memcached.status'](host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('delete key {0} from memcached server {1}:{2}'
                    ).format(name, host, port)
            return ret
        if __salt__['memcached.delete'](host, port, name):
            ret['comment'] = 'delete key {0} from memcached server {1}:{2}'.format(name, host, port)
            ret['changes'][name] = 'to be delete'
            return ret

    ret['comment'] = ('memcached server {0}:{1} is down or not exists.'
                     ).format(host,port)
    return ret


def add(name,
        host=None,
        port=None,
        val=None):
    '''
    Add key to memcached server.

    name
        The key

    host
        The memcached server ip

    port
        The memcached server port
   
    val
        The value

    .. code-block:: yaml

        k1:
          memcached.add:
            - host: 10.0.0.1
            - port: 11211
            - val: v1
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check memcached server
    if __salt__['memcached.status'](host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('add key {0} to memcached server {1}:{2}'
                    ).format(name, host, port)
            return ret
        if __salt__['memcached.add'](host, port, name, val):
            ret['comment'] = 'add key {0} to memcached server {1}:{2}'.format(name, host, port)
            ret['changes'][name] = 'to be add'
            return ret
        else:
            ret['comment'] = 'key {0} is exists in memcached server {1}:{2}'.format(name, host, port)
            return ret

    ret['comment'] = ('memcached server {0}:{1} is down or not exists.'
                     ).format(host,port)
    return ret


def incr(name,
        host=None,
        port=None,
        delta=1):
    '''
    Incr key to memcached server.

    name
        The key

    host
        The memcached server ip

    port
        The memcached server port
   
    delta
        The default value is 1

    .. code-block:: yaml

        k1:
          memcached.incr:
            - host: 10.0.0.1
            - port: 11211
            - delta: 100
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check memcached server
    if __salt__['memcached.status'](host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('incr key {0} to memcached server {1}:{2}'
                    ).format(name, host, port)
            return ret
        ret['comment'] = __salt__['memcached.incr'](host, port, name, delta)
        return ret

    ret['comment'] = ('memcached server {0}:{1} is down or not exists.'
                     ).format(host,port)
    return ret


def decr(name,
        host=None,
        port=None,
        delta=1):
    '''
    Decr key to memcached server.

    name
        The key

    host
        The memcached server ip

    port
        The memcached server port
   
    delta
        The default value is 1

    .. code-block:: yaml

        k1:
          memcached.decr:
            - host: 10.0.0.1
            - port: 11211
            - delta: 100
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check memcached server
    if __salt__['memcached.status'](host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('decr key {0} to memcached server {1}:{2}'
                    ).format(name, host, port)
            return ret
        ret['comment'] = __salt__['memcached.decr'](host, port, name, delta)
        return ret

    ret['comment'] = ('memcached server {0}:{1} is down or not exists.'
                     ).format(host,port)
    return ret



def replace(name,
        host=None,
        port=None,
        val=None):
    '''
    Replace key from memcached server.

    name
        The key

    host
        The memcached server ip

    port
        The memcached server port
   
    Val
        The value

    .. code-block:: yaml

        k1:
          memcached.replace:
            - host: 10.0.0.1
            - port: 11211
            - val: v1
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check memcached server
    if __salt__['memcached.status'](host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('replace key {0} from memcached server {1}:{2}'
                    ).format(name, host, port)
            return ret
        ret['comment'] = __salt__['memcached.replace'](host, port, name, val)
        return ret

    ret['comment'] = ('memcached server {0}:{1} is down or not exists.'
                     ).format(host,port)
    return ret



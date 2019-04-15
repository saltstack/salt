# -*- coding: utf-8 -*-
'''
States for Management of Memcached Keys
=======================================

.. versionadded:: 2014.1.0
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.modules.memcached import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIME,
    DEFAULT_MIN_COMPRESS_LEN
)
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext import six

__virtualname__ = 'memcached'


def __virtual__():
    '''
    Only load if memcache module is available
    '''
    return __virtualname__ \
        if '{0}.status'.format(__virtualname__) in __salt__ \
        else False


def managed(name,
            value=None,
            host=DEFAULT_HOST,
            port=DEFAULT_PORT,
            time=DEFAULT_TIME,
            min_compress_len=DEFAULT_MIN_COMPRESS_LEN):
    '''
    Manage a memcached key.

    name
        The key to manage

    value
        The value to set for that key

    host
        The memcached server IP address

    port
        The memcached server port


    .. code-block:: yaml

        foo:
          memcached.managed:
            - value: bar
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    try:
        cur = __salt__['memcached.get'](name, host, port)
    except CommandExecutionError as exc:
        ret['comment'] = six.text_type(exc)
        return ret

    if cur == value:
        ret['result'] = True
        ret['comment'] = 'Key \'{0}\' does not need to be updated'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        if cur is None:
            ret['comment'] = 'Key \'{0}\' would be added'.format(name)
        else:
            ret['comment'] = 'Value of key \'{0}\' would be changed'.format(name)
        return ret

    try:
        ret['result'] = __salt__['memcached.set'](
            name, value, host, port, time, min_compress_len
        )
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret['comment'] = six.text_type(exc)
    else:
        if ret['result']:
            ret['comment'] = 'Successfully set key \'{0}\''.format(name)
            if cur is not None:
                ret['changes'] = {'old': cur, 'new': value}
            else:
                ret['changes'] = {'key added': name, 'value': value}
        else:
            ret['comment'] = 'Failed to set key \'{0}\''.format(name)
    return ret


def absent(name,
           value=None,
           host=DEFAULT_HOST,
           port=DEFAULT_PORT,
           time=DEFAULT_TIME):
    '''
    Ensure that a memcached key is not present.

    name
        The key

    value : None
        If specified, only ensure that the key is absent if it matches the
        specified value.

    host
        The memcached server IP address

    port
        The memcached server port


    .. code-block:: yaml

        foo:
          memcached.absent

        bar:
          memcached.absent:
            - host: 10.0.0.1
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    try:
        cur = __salt__['memcached.get'](name, host, port)
    except CommandExecutionError as exc:
        ret['comment'] = six.text_type(exc)
        return ret

    if value is not None:
        if cur is not None and cur != value:
            ret['result'] = True
            ret['comment'] = (
                'Value of key \'{0}\' (\'{1}\') is not \'{2}\''
                .format(name, cur, value)
            )
            return ret
    if cur is None:
        ret['result'] = True
        ret['comment'] = 'Key \'{0}\' does not exist'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Key \'{0}\' would be deleted'.format(name)
        return ret

    try:
        ret['result'] = __salt__['memcached.delete'](name, host, port, time)
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret['comment'] = six.text_type(exc)
    else:
        if ret['result']:
            ret['comment'] = 'Successfully deleted key \'{0}\''.format(name)
            ret['changes'] = {'key deleted': name, 'value': cur}
        else:
            ret['comment'] = 'Failed to delete key \'{0}\''.format(name)
    return ret

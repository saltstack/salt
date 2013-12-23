# -*- coding: utf-8 -*-
'''
The function cache system allows for data to be stored on the master so it can be easily read by other minions
'''

# Import python libs
import copy
import logging

# Import salt libs
import salt.crypt
import salt.payload


log = logging.getLogger(__name__)


def _auth():
    '''
    Return the auth object
    '''
    if 'auth' not in __context__:
        __context__['auth'] = salt.crypt.SAuth(__opts__)
    return __context__['auth']


def update(clear=False):
    '''
    Execute the configured functions and send the data back up to the master
    The functions to be executed are merged from the master config, pillar and
    minion config under the option "function_cache":

    .. code-block:: yaml

        mine_functions:
          network.ip_addrs:
            - eth0
          disk.usage: []

    The function cache will be populated with information from executing these
    functions

    CLI Example:

    .. code-block:: bash

        salt '*' mine.update
    '''
    m_data = __salt__['config.option']('mine_functions', {})
    data = {}
    for func in m_data:
        if func not in __salt__:
            log.error('Function {0} in mine_functions not available'
                      .format(func))
            continue
        try:
            if m_data[func] and isinstance(m_data[func], dict):
                data[func] = __salt__[func](**m_data[func])
            elif m_data[func] and isinstance(m_data[func], list):
                data[func] = __salt__[func](*m_data[func])
            else:
                data[func] = __salt__[func]()
        except Exception:
            log.error('Function {0} in mine_functions failed to execute'
                      .format(func))
            continue
    if __opts__['file_client'] == 'local':
        if not clear:
            old = __salt__['data.getval']('mine_cache')
            if isinstance(old, dict):
                old.update(data)
                data = old
        return __salt__['data.update']('mine_cache', data)
    auth = _auth()
    load = {
            'cmd': '_mine',
            'data': data,
            'id': __opts__['id'],
            'clear': clear,
            'tok': auth.gen_token('salt'),
    }
    # Changed for transport plugin
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
    # ret = sreq.send('aes', auth.crypticle.dumps(load))
    # return auth.crypticle.loads(ret)
    sreq = salt.transport.Channel.factory(__opts__)
    ret = sreq.send(load)
    return ret


def send(func, *args, **kwargs):
    '''
    Send a specific function to the mine.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.send network.interfaces eth0
    '''
    if not func in __salt__:
        return False
    data = {}
    arg_data = salt.utils.arg_lookup(__salt__[func])
    func_data = copy.deepcopy(kwargs)
    for ind, _ in enumerate(arg_data.get('args', [])):
        try:
            func_data[arg_data['args'][ind]] = args[ind]
        except IndexError:
            # Safe error, arg may be in kwargs
            pass
    f_call = salt.utils.format_call(__salt__[func], func_data)
    try:
        if 'kwargs' in f_call:
            data[func] = __salt__[func](*f_call['args'], **f_call['kwargs'])
        else:
            data[func] = __salt__[func](*f_call['args'])
    except Exception as exc:
        log.error('Function {0} in mine.send failed to execute: {1}'
                  .format(func, exc))
        return False
    if __opts__['file_client'] == 'local':
        old = __salt__['data.getval']('mine_cache')
        if isinstance(old, dict):
            old.update(data)
            data = old
        return __salt__['data.update']('mine_cache', data)
    auth = _auth()
    load = {
            'cmd': '_mine',
            'data': data,
            'id': __opts__['id'],
            'tok': auth.gen_token('salt'),
    }
    # Changed for transport plugin
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
    # ret = sreq.send('aes', auth.crypticle.dumps(load))
    # return auth.crypticle.loads(ret)
    sreq = salt.transport.Channel.factory(__opts__)
    ret = sreq.send(load)
    return ret


def get(tgt, fun, expr_form='glob'):
    '''
    Get data from the mine based on the target, function and expr_form

    Targets can be matched based on any standard matching system that can be
    matched on the master via these keywords::

        glob
        pcre
        grain
        grain_pcre

    CLI Example:

    .. code-block:: bash

        salt '*' mine.get '*' network.interfaces
        salt '*' mine.get 'os:Fedora' network.interfaces grain
    '''
    if expr_form.lower == 'pillar':
        log.error('Pillar matching not supported on mine.get')
        return ''
    if __opts__['file_client'] == 'local':
        ret = {}
        is_target = {'glob': __salt__['match.glob'],
                     'pcre': __salt__['match.pcre'],
                     'list': __salt__['match.list'],
                     'grain': __salt__['match.grain'],
                     'grain_pcre': __salt__['match.grain_pcre'],
                     'compound': __salt__['match.compound'],
                     'ipcidr': __salt__['match.ipcidr'],
                     }[expr_form](tgt)
        if is_target:
            data = __salt__['data.getval']('mine_cache')
            if isinstance(data, dict) and fun in data:
                ret[__opts__['id']] = data[fun]
        return ret
    auth = _auth()
    load = {
            'cmd': '_mine_get',
            'id': __opts__['id'],
            'tgt': tgt,
            'fun': fun,
            'expr_form': expr_form,
            'tok': auth.gen_token('salt'),
    }
    # Changed for transport plugin
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
    # ret = sreq.send('aes', auth.crypticle.dumps(load))
    # return auth.crypticle.loads(ret)
    sreq = salt.transport.Channel.factory(__opts__)
    ret = sreq.send(load)
    return ret


def delete(fun):
    '''
    Remove specific function contents of minion. Returns True on success.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.delete 'network.interfaces'
    '''
    if __opts__['file_client'] == 'local':
        data = __salt__['data.getval']('mine_cache')
        if isinstance(data, dict) and fun in data:
            del data[fun]
        return __salt__['data.update']('mine_cache', data)
    auth = _auth()
    load = {
            'cmd': '_mine_delete',
            'id': __opts__['id'],
            'fun': fun,
            'tok': auth.gen_token('salt'),
    }
    # Changed for transport plugin
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
    # ret = sreq.send('aes', auth.crypticle.dumps(load))
    # return auth.crypticle.loads(ret)
    sreq = salt.transport.Channel.factory(__opts__)
    ret = sreq.send(load)
    return ret


def flush():
    '''
    Remove all mine contents of minion. Returns True on success.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.flush
    '''
    if __opts__['file_client'] == 'local':
        return __salt__['data.update']('mine_cache', {})
    auth = _auth()
    load = {
            'cmd': '_mine_flush',
            'id': __opts__['id'],
            'tok': auth.gen_token('salt'),
    }
    # Changed for transport plugin
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
    # ret = sreq.send('aes', auth.crypticle.dumps(load))
    # return auth.crypticle.loads(ret)
    sreq = salt.transport.Channel.factory(__opts__)
    ret = sreq.send(load)
    return ret

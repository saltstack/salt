'''
The function cache system allows for data to be stored on the master so it
can be easily read by other minions
'''

# Import python libs
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

    CLI Example::

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
    load = {
            'cmd': '_mine',
            'data': data,
            'id': __opts__['id'],
            'clear': clear,
    }
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    auth = _auth()
    try:
        sreq.send('aes', auth.crypticle.dumps(load), 1, 0)
    except Exception:
        pass
    return True


def send(func, *args, **kwargs):
    '''
    Send a specific function to the mine.

    CLI Example::

        salt '*' mine.send network.interfaces eth0
    '''
    if not func in __salt__:
        return False
    data = {}
    arg_data = salt.utils.arg_lookup(__salt__[func])
    func_data = {}
    for ind in range(len(arg_data.get('args', []))):
        try:
            func_data[arg_data[ind]] = args[ind]
        except IndexError:
            # Safe error, arg may be in kwargs
            pass
    func_data.update(kwargs)
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
    load = {
            'cmd': '_mine',
            'data': data,
            'id': __opts__['id'],
    }
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    auth = _auth()
    try:
        sreq.send('aes', auth.crypticle.dumps(load), 1, 10)
    except Exception:
        return True
    return True


def get(tgt, fun, expr_form='glob'):
    '''
    Get data from the mine based on the target, function and expr_form

    Targets can be matched based on any standard matching system that can be
    matched on the master via these keywords:

        glob
        pcre
        grain
        grain_pcre
        pillar

    CLI Example::

        salt '*' mine.get '*' network.interfaces
        salt '*' mine.get 'os:Fedora' network.interfaces grain
    '''
    auth = _auth()
    load = {
            'cmd': '_mine_get',
            'id': __opts__['id'],
            'tgt': tgt,
            'fun': fun,
            'expr_form': expr_form,
    }
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    ret = sreq.send('aes', auth.crypticle.dumps(load))
    return auth.crypticle.loads(ret)

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


def update():
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
            log.error(
                    'Function {0} in mine_functions not available'.format(
                        func
                        )
                    )
            continue
        try:
            if m_data[func] and isinstance(m_data[func], dict):
                data[func] = __salt__[func](**m_data[func])
            elif m_data[func] and isinstance(m_data[func], list):
                data[func] = __salt__[func](*m_data[func])
            else:
                data[func] = __salt__[func]()
        except Exception:
            log.error(
                    'Function {0} in mine_functions failed to execute'.format(
                        func
                        )
                    )
            continue
    load = {
            'cmd': '_mine',
            'data': data,
            'id': __opts__['id']
            }
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    auth = _auth()
    try:
        sreq.send('aes', auth.crypticle.dumps(load), 1, 0)
    except Exception:
        pass


def get(tgt, fun, expr_form='glob'):
    '''
    Get data from the mine based on the target, function and expr_form

    CLI Example::

        salt '*' mine.get '*' network.interfaces
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
    return sreq.send('aes', auth.crypticle.dumps(load))

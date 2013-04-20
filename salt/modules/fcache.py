'''
The function cache system allows for data to be stored on the master so it
can be easily read by other minions
'''

# Import salt libs
import salt.crypt
import salt.payload


def _auth():
    '''
    Return the auth object
    '''
    if not 'fcache.auth' in __context__:
        __context__['fcache.auth'] = salt.crypt.SAuth(__opts__)
    return __context__['fcache.auth']


def update():
    '''
    Execute the configured functions and send the data back up to the master
    The functions to be executed are merged from the master config, pillar and
    minion config under the option "function_cache":

    .. code-block:: yaml

        function_cache:
          network.ip_addrs:
            - eth0
          disk.usage: []

    The function cache will be populated with information from executing these
    functions

    CLI Example::

        salt '*' fcache.update
    '''
    f_data = __salt__['config.option']('function_cache', {})
    data = {}
    for func in f_data:
        if not func in __salt__:
            continue
        try:
            if f_data[func] and isinstance(f_data[func], dict):
                data[func] = __salt__[func](**f_data[func])
            elif f_data[func] and isinstance(f_data[func], list):
                data[func] = __salt__[func](*f_data[func])
            else:
                data[func] = __salt__[func]()
        except Exception:
            continue
    load = {
            'cmd': '_fcache',
            'data': data,
            'id': __opts__['id']
            }
    serial = salt.payload.Serial(__opts__)
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    auth = _auth()
    try:
        sreq.send('aes', auth.crypticle.dumps(load), 1, 0)
    except Exception:
        pass


def get(tgt, fun, expr_form='glob'):
    '''
    Get data from the fcache based on the target, function and expr_form

    CLI Example::

        salt '*' fcache.get '*' network.interfaces
    '''
    auth = _auth()
    load = {
            'cmd': '_fcache_get',
            'id': __opts__['id'],
            'tgt': tgt,
            'fun': fun,
            'expr_form': expr_form,
            }
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    return sreq.send('aes', auth.crypticle.dumps(load))

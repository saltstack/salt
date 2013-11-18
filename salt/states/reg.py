# -*- coding: utf-8 -*-
'''
Manage the registry on Windows
'''


def __virtual__():
    '''
    Load this state if the reg module exists
    '''
    return 'reg' if 'reg.read_key' in __salt__ else False


def _parse_key(key):
    '''
    split the full path in the registry to the key and the rest
    '''
    splt = key.split('\\')
    hive = splt.pop(0)
    key = splt.pop(-1)
    path = '\\'.join(splt)
    return hive, path, key


def present(name, value, vtype='REG_DWORD'):
    '''
    Set a registry entry

    Example::

        'HKEY_CURRENT_USER\\SOFTWARE\\Salt\\version':
          reg.present:
            - value: 0.15.3
            - vtype: REG_SZ
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # determine what to do
    hive, path, key = _parse_key(name)
    if value == __salt__['reg.read_key'](hive, path, key):
        ret['comment'] = '{0} is already configured'.format(name)
        return ret
    else:
        ret['changes'] = {'reg': 'configured to {0}'.format(value)}

    if __opts__['test']:
        ret['result'] = None
        return ret

    # configure the key
    ret['result'] = __salt__['reg.set_key'](hive, path, key, value, vtype)
    if not ret:
        ret['changes'] = {}
        ret['comment'] = 'could not configure the registry key'

    return ret

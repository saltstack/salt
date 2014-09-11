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
    splt = key.split("\\")
    hive = splt.pop(0)
    key = splt.pop(-1)
    path = r'\\'.join(splt)
    return hive, path, key


def present(name, value, vtype='REG_DWORD', reflection=True):
    '''
    Set a registry entry

    Optionally set ``reflection`` to ``False`` to disable reflection.
    ``reflection`` has no effect on a 32-bit OS.

    In the example below, this will prevent Windows from silently creating
    the key in:
    ``HKEY_CURRENT_USER\\SOFTWARE\\Wow6432Node\\Salt\\version``

    Example:

    .. code-block:: yaml

        HKEY_CURRENT_USER\\SOFTWARE\\Salt\\version:
          reg.present:
            - value: 0.15.3
            - vtype: REG_SZ
            - reflection: False
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # determine what to do
    hive, path, key = _parse_key(name)
    if value == __salt__['reg.read_key'](hive, path, key, reflection):
        ret['comment'] = '{0} is already configured'.format(name)
        return ret
    else:
        ret['changes'] = {'reg': 'configured to {0}'.format(value)}

    if __opts__['test']:
        ret['result'] = None
        return ret

    # configure the key
    ret['result'] = __salt__['reg.set_key'](hive, path, key, value, vtype,
                                            reflection)
    if not ret:
        ret['changes'] = {}
        ret['comment'] = 'could not configure the registry key'

    return ret


def absent(name):
    '''
    Remove a registry key

    Example::

        'HKEY_CURRENT_USER\\SOFTWARE\\Salt\\version':
          reg.absent
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, path, key = _parse_key(name)
    if not __salt__['reg.read_key'](hive, path, key):
        ret['comment'] = '{0} is already absent'.format(name)
        return ret
    else:
        ret['changes'] = {'reg': 'Removed {0}'.format(name)}

    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['result'] = __salt__['reg.delete_key'](hive, path, key)
    if not ret['result']:
        ret['changes'] = {}
        ret['comment'] = 'failed to remove registry key {0}'.format(name)

    return ret

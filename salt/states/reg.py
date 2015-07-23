# -*- coding: utf-8 -*-
'''
Manage the registry on Windows
'''
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Load this state if the reg module exists
    '''
    return 'reg' if 'reg.read_key' in __salt__ else False


def _parse_key_value(key):
    '''
    split the full path in the registry to the key and the rest
    '''
    splt = key.split("\\")
    hive = splt.pop(0)
    vname = splt.pop(-1)
    key = r'\\'.join(splt)
    return hive, key, vname


def _parse_key(key):
    '''
    split the hive from the key
    '''
    splt = key.split("\\")
    hive = splt.pop(0)
    key = r'\\'.join(splt)
    return hive, key


def present(name, value, vtype='REG_SZ', reflection=True):
    '''
    Set a registry value

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

    In the above example the path is interpreted as follows:
    - ``HKEY_CURRENT_USER`` is the hive
    - ``SOFTWARE\\Salt`` is the key
    - ``version`` is the value name
    So ``version`` will be created in the ``SOFTWARE\\Salt`` key in the
    ``HKEY_CURRENT_USER`` hive and given the ``REG_SZ`` value of ``0.15.3``.
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, key, vname = _parse_key_value(name)

    # Determine what to do
    if value == __salt__['reg.read_value'](hive, key, vname)['vdata']:
        ret['comment'] = '{0} is already configured'.format(name)
        return ret
    else:
        ret['changes'] = {'reg': 'configured to {0}'.format(value)}

    # Check for test option
    if __opts__['test']:
        ret['result'] = None
        return ret

    # Configure the value
    ret['result'] = __salt__['reg.set_value'](hive, key, vname, value, vtype,
                                              reflection)

    if not ret:
        ret['changes'] = {}
        ret['comment'] = 'could not configure the registry key'

    return ret


def absent(name):
    '''
    Remove a registry value

    Example::

        'HKEY_CURRENT_USER\\SOFTWARE\\Salt\\version':
          reg.absent

    In the above example the path is interpreted as follows:
    - ``HKEY_CURRENT_USER`` is the hive
    - ``SOFTWARE\\Salt`` is the key
    - ``version`` is the value name
    So the value ``version`` will be deleted from the ``SOFTWARE\\Salt`` key in
    the ``HKEY_CURRENT_USER`` hive.
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, key, vname = _parse_key_value(name)

    # Determine what to do
    if not __salt__['reg.read_value'](hive, key, vname)['success']:
        ret['comment'] = '{0} is already absent'.format(name)
        return ret
    else:
        ret['changes'] = {'reg': 'Removed {0}'.format(name)}

    # Check for test option
    if __opts__['test']:
        ret['result'] = None
        return ret

    # Delete the value
    ret['result'] = __salt__['reg.delete_value'](hive, key, vname)
    if not ret['result']:
        ret['changes'] = {}
        ret['comment'] = 'failed to remove registry key {0}'.format(name)

    return ret

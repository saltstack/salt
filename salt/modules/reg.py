'''
Manage the registry on Windows
'''

import _winreg

def __virtual__():
    '''
    Only works on Windows systems
    '''
    if __grains__['os'] == 'Windows':
        return 'reg'
    return False


hkeys = {'HKEY_CURRENT_USER': _winreg.HKEY_CURRENT_USER,
        'HKEY_LOCAL_MACHINE': _winreg.HKEY_LOCAL_MACHINE,
        'HKEY_USERS': _winreg.HKEY_USERS,
        }


def read_key(hkey, path, key):
    '''
        Read registry key value

        CLI Example::

        salt '*' reg.read_key HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version'
    '''
    hkey2 = hkeys[hkey]
    fullpath = '\\\\'.join([path, key])
    try:
        handle = _winreg.OpenKey(hkey2, fullpath, 0, _winreg.KEY_READ)
        return _winreg.QueryValueEx(handle, key)[0]
    except:
        return False


def set_key(hkey, path, key, value):
    '''
        Set a registry key

        CLI Example::

        salt '*' reg.set_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' '0.97'
    '''
    hkey2 = hkeys[hkey]
    fullpath = '\\\\'.join([path, key])
    try:
        handle = _winreg.OpenKey(hkey2, fullpath, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.SetValueEx(handle, key, 0, _winreg.REG_SZ, value)
        _winreg.CloseKey(handle)
        return True
    except:
        handle = _winreg.CreateKey(hkey2, fullpath)
        _winreg.SetValueEx(handle, key, 0, _winreg.REG_SZ, value)
        _winreg.CloseKey(handle)
        return True


def create_key(hkey, path, key, value=None):
    '''
        Create a registry key

        CLI Example::

        salt '*' reg.create_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' '0.97'
    '''
    hkey2 = hkeys[hkey]
    fullpath = '\\\\'.join([path, key])
    try:
        handle = _winreg.OpenKey(hkey2, fullpath, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.CloseKey(handle)
        return True
    except:
        handle = _winreg.CreateKey(hkey2, fullpath)
        if value:
            _winreg.SetValueEx(handle, key, 0, _winreg.REG_SZ, value)
        _winreg.CloseKey(handle)
        return True


def delete_key(hkey, path, key):
    '''
        Delete a registry key

        Note: This cannot delete a key with subkeys

        CLI Example::

        salt '*' reg.delete_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' 
    '''
    hkey2 = hkeys[hkey]
    try:
        handle = _winreg.OpenKey(hkey2, path, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.DeleteKeyEx(handle, key)
        _winreg.CloseKey(handle)
        return True
    except:
        _winreg.CloseKey(handle)
        return True

'''
Manage the registry on Windows

Required python modules: _winreg
'''

# TODO: Figure out the exceptions _winreg can raise and properly  catch
#       them instead of a bare except that catches any exception at all

try:
    import _winreg
    has_windows_modules = True
except ImportError:
    try:
        import winreg as _winreg
        has_windows_modules = True
    except ImportError:
        has_windows_modules = False

import salt.utils
import logging
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


class Registry(object):
    '''
    Delay '_winreg' usage until this module is used
    '''
    def __init__(self):
        hkeys = {
            "HKEY_USERS":         _winreg.HKEY_USERS,
            "HKEY_CURRENT_USER":  _winreg.HKEY_CURRENT_USER,
            "HKEY_LOCAL_MACHINE": _winreg.HKEY_LOCAL_MACHINE,
        }
    def __getattr__(self, k):
        try:
            return self.hkeys[k]
        except KeyError:
            msg = 'No hkey named \'{0}. Try one of {1}\''
            hkeys = ', '.join(self.hkeys)
            raise CommandExecutionError(msg.format(k, hkeys))

def __virtual__():
    '''
    Only works on Windows systems
    '''
    if __grains__['os'] == 'Windows':
        if has_windows_modules:
            return 'reg'
        log.warn(salt.utils.required_modules_error(__file__, __doc__))
    return False

def read_key(hkey, path, key):
    '''
    Read registry key value

    CLI Example::

        salt '*' reg.read_key HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version'
    '''

    registry = Registry()
    hkey2 = getattr(registry, hkey)
    fullpath = '\\\\'.join([path, key])
    try:
        handle = _winreg.OpenKey(hkey2, fullpath, 0, _winreg.KEY_READ)
        return _winreg.QueryValueEx(handle, key)[0]
    except Exception:
        return False


def set_key(hkey, path, key, value):
    '''
    Set a registry key

    CLI Example::

        salt '*' reg.set_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' '0.97'
    '''
    registry = Registry()
    hkey2 = getattr(registry, hkey)
    fullpath = '\\\\'.join([path, key])

    try:
        handle = _winreg.OpenKey(hkey2, fullpath, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.SetValueEx(handle, key, 0, _winreg.REG_SZ, value)
        _winreg.CloseKey(handle)
        return True
    except Exception:
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
    registry = Registry()
    hkey2 = getattr(registry, hkey)
    fullpath = '\\\\'.join([path, key])

    try:
        handle = _winreg.OpenKey(hkey2, fullpath, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.CloseKey(handle)
        return True
    except Exception:
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
    registry = Registry()
    hkey2 = getattr(registry, hkey)

    try:
        handle = _winreg.OpenKey(hkey2, path, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.DeleteKeyEx(handle, key)
        _winreg.CloseKey(handle)
        return True
    except Exception:
        _winreg.CloseKey(handle)
    return True

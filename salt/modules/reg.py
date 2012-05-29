'''
Manage the registry on Windows

Required python modules: _winreg
'''

# TODO: Figure out the exceptions _winreg can raise and properly catch
#       them instead of a bare except that catches any exception at all

try:
    import _winreg as winreg
    has_windows_modules = True
except ImportError:
    # for Python > 3
    try:
        import winreg as winreg
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
            "HKEY_USERS": winreg.HKEY_USERS,
            "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
            "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
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
        handle = winreg.OpenKey(hkey2, fullpath, 0, winreg.KEY_READ)
        return winreg.QueryValueEx(handle, key)[0]
    except:
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
        handle = winreg.OpenKey(hkey2, fullpath, 0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(handle, key, 0, winreg.REG_SZ, value)
        winreg.CloseKey(handle)
        return True
    except:
        handle = winreg.CreateKey(hkey2, fullpath)
        winreg.SetValueEx(handle, key, 0, winreg.REG_SZ, value)
        winreg.CloseKey(handle)
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
        handle = winreg.OpenKey(hkey2, fullpath, 0, winreg.KEY_ALL_ACCESS)
        winreg.CloseKey(handle)
        return True
    except:
        handle = winreg.CreateKey(hkey2, fullpath)
        if value:
            winreg.SetValueEx(handle, key, 0, winreg.REG_SZ, value)
        winreg.CloseKey(handle)
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
        handle = winreg.OpenKey(hkey2, path, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteKeyEx(handle, key)
        winreg.CloseKey(handle)
        return True
    except:
        winreg.CloseKey(handle)
    return True

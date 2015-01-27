# -*- coding: utf-8 -*-
'''
Manage the registry on Windows

:depends:   - winreg Python module
'''

# TODO: Figure out the exceptions _winreg can raise and properly  catch
#       them instead of a bare except that catches any exception at all

# Import third party libs
try:
    import _winreg
    HAS_WINDOWS_MODULES = True
except ImportError:
    try:
        import winreg as _winreg
        HAS_WINDOWS_MODULES = True
    except ImportError:
        HAS_WINDOWS_MODULES = False

# Import python libs
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'reg'


class Registry(object):
    '''
    Delay '_winreg' usage until this module is used
    '''
    def __init__(self):
        self.hkeys = {
            "HKEY_USERS": _winreg.HKEY_USERS,
            "HKEY_CURRENT_USER": _winreg.HKEY_CURRENT_USER,
            "HKEY_LOCAL_MACHINE": _winreg.HKEY_LOCAL_MACHINE,
            }

        self.reflection_mask = {
            True: _winreg.KEY_ALL_ACCESS,
            False: _winreg.KEY_ALL_ACCESS | _winreg.KEY_WOW64_64KEY,
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
    if salt.utils.is_windows() and HAS_WINDOWS_MODULES:
        return __virtualname__
    return False


def read_key(hkey, path, key, reflection=True):
    '''
    Read registry key value

    CLI Example:

    .. code-block:: bash

        salt '*' reg.read_key HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version'
    '''

    registry = Registry()
    hkey2 = getattr(registry, hkey)
    access_mask = registry.reflection_mask[reflection]
    try:
        handle = _winreg.OpenKeyEx(hkey2, path, 0, access_mask)
        return _winreg.QueryValueEx(handle, key)[0]
    except Exception:
        return None


def set_key(hkey, path, key, value, vtype='REG_DWORD', reflection=True):
    '''
    Set a registry key
    vtype: http://docs.python.org/2/library/_winreg.html#value-types

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' '0.97' REG_DWORD
    '''
    registry = Registry()
    hkey2 = getattr(registry, hkey)
    access_mask = registry.reflection_mask[reflection]

    try:
        _type = getattr(_winreg, vtype)
    except AttributeError:
        return False

    try:
        handle = _winreg.OpenKey(hkey2, path, 0, access_mask)
        _winreg.SetValueEx(handle, key, 0, _type, value)
        _winreg.CloseKey(handle)
        return True
    except Exception:
        handle = _winreg.CreateKeyEx(hkey2, path, 0, access_mask)
        _winreg.SetValueEx(handle, key, 0, _type, value)
        _winreg.CloseKey(handle)
    return True


def create_key(hkey, path, key, value=None, reflection=True):
    '''
    Create a registry key

    CLI Example:

    .. code-block:: bash

        salt '*' reg.create_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' '0.97'
    '''
    registry = Registry()
    hkey2 = getattr(registry, hkey)
    access_mask = registry.reflection_mask[reflection]

    try:
        handle = _winreg.OpenKey(hkey2, path, 0, access_mask)
        _winreg.CloseKey(handle)
        return True
    except Exception:
        handle = _winreg.CreateKeyEx(hkey2, path, 0, access_mask)
        if value:
            _winreg.SetValueEx(handle, key, 0, _winreg.REG_DWORD, value)
        _winreg.CloseKey(handle)
    return True


def delete_key(hkey, path, key, reflection=True):
    '''
    Delete a registry key

    Note: This cannot delete a key with subkeys

    CLI Example:

    .. code-block:: bash

        salt '*' reg.delete_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version'
    '''
    registry = Registry()
    hkey2 = getattr(registry, hkey)
    access_mask = registry.reflection_mask[reflection]

    try:
        handle = _winreg.OpenKey(hkey2, path, 0, access_mask)
        _winreg.DeleteKeyEx(handle, key)
        _winreg.CloseKey(handle)
        return True
    except Exception:
        pass

    try:
        _winreg.DeleteValue(handle, key)
        _winreg.CloseKey(handle)
        return True
    except Exception:
        _winreg.CloseKey(handle)
        return False

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


class Registry(object):
    '''
    Delay '_winreg' usage until this module is used
    '''
    def __init__(self):
        self.hkeys = {
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
    if salt.utils.is_windows():
        if HAS_WINDOWS_MODULES:
            return 'reg'
            # TODO: This needs to be reworked after the module dependency
        # docstring was changed to :depends
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
    # handle = _winreg.OpenKey(hkey2, path)
    # value, type = _winreg.QueryValueEx(handle, key)
    # return value
    try:
        handle = _winreg.OpenKey(hkey2, path)
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
    # fullpath = '\\\\'.join([path, key])

    try:
        # handle = _winreg.OpenKey(hkey2, fullpath, 0, _winreg.KEY_ALL_ACCESS)
        handle = _winreg.OpenKey(hkey2, path, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.SetValueEx(handle, key, 0, _winreg.REG_DWORD, value)
        _winreg.CloseKey(handle)
        return True
    except Exception:
        handle = _winreg.CreateKey(hkey2, path)
        _winreg.SetValueEx(handle, key, 0, _winreg.REG_DWORD, value)
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
    # fullpath = '\\\\'.join([path, key])

    try:
        handle = _winreg.OpenKey(hkey2, path, 0, _winreg.KEY_ALL_ACCESS)
        _winreg.CloseKey(handle)
        return True
    except Exception:
        handle = _winreg.CreateKey(hkey2, path)
        if value:
            _winreg.SetValueEx(handle, key, 0, _winreg.REG_DWORD, value)
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

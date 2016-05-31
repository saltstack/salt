# -*- coding: utf-8 -*-
'''
Install features/packages for Windows using DISM, which is useful for minions
not running server versions of Windows. Some functions are only available on
Windows 10.

'''
from __future__ import absolute_import

# Import python libs
import re
import logging

# Import salt libs
import salt.utils
from salt.exceptions import NotImplemented

log = logging.getLogger(__name__)
__virtualname__ = "dism"


def __virtual__():
    '''
    Only work on Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def _install_component(name, component_type, install_name, source=None, limit_access=False):
    cmd = 'DISM /Online /{0}-{1} /{1}Name:{2}'.format(install_name, component_type, name)
    if source:
        cmd += ' /Source:{0}'.format(source)
    if limit_access:
        cmd += ' /LimitAccess'

    return __salt__['cmd.run_all'](cmd)


def _uninstall_component(name, component_type, uninstall_name):
    cmd = 'DISM /Online /{0}-{1} /{1}Name:{2}'\
          .format(uninstall_name, component_type, name)

    return __salt__['cmd.run_all'](cmd)


def _get_components(type_regex, plural_type, install_value):
    cmd = 'DISM /Online /Get-{0}'.format(plural_type)
    out = __salt__['cmd.run'](cmd)
    pattern = r'{0} : (.*)\r\n.*State : {1}\r\n'\
              .format(type_regex, install_value)
    capabilities = re.findall(pattern, out, re.MULTILINE)
    return capabilities


def install_capability(capability, source=None, limit_access=False):
    '''
    Install a capability

    Args:
        capability (str): The capability to install
        source (Optional[str]): The optional source of the capability
        limit_access (Optional[bool]): Prevent DISM from contacting Windows
            for online images

    Raises:
        NotImplemented Error for all versions of Windows that are not Windows 10
        and later. Server editions of Windows use ServerManager instead.

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.install_capability Tools.Graphics.DirectX~~~~0.0.1.0
    '''
    if salt.utils.version_cmp(__grains__['osversion'], '10') == -1:
        raise NotImplemented(
            '`install_capability` is not available on this version of Windows: '
            '{0}'.format(__grains__['osversion']))
    return _install_component(capability, "Capability", "Add", source, limit_access)


def uninstall_capability(capability):
    '''
    Uninstall a capability

    Args:
        capability(str): The capability to be uninstalled

    Raises:
        NotImplemented Error for all versions of Windows that are not Windows 10
        and later. Server editions of Windows use ServerManager instead.

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.uninstall_capability Tools.Graphics.DirectX~~~~0.0.1.0
    '''
    if salt.utils.version_cmp(__grains__['osversion'], '10') == -1:
        raise NotImplemented(
            '`uninstall_capability` is not available on this version of '
            'Windows: {0}'.format(__grains__['osversion']))
    return _uninstall_component(capability, "Capability", "Remove")


def installed_capabilities():
    '''
    List the capabilities installed on the system

    Raises:
        NotImplemented Error for all versions of Windows that are not Windows 10
        and later. Server editions of Windows use ServerManager instead.

    Returns:
        list: A list of installed capabilities

    CLI Example:

    .. code-block:: bash

        salt '*' dism.installed_capabilities
    '''
    if salt.utils.version_cmp(__grains__['osversion'], '10') == -1:
        raise NotImplemented(
            '`installed_capabilities` is not available on this version of '
            'Windows: {0}'.format(__grains__['osversion']))
    return _get_components("Capability Identity", "Capabilities", "Installed")


def install_feature(feature, source=None, limit_access=False):
    '''
    Install a feature using DISM

    Args:
        feature (str): The feature to install
        source (Optional[str]): The path to the source for the feature. If not
            passed, Windows Update will be used.
        limit_access (Optional[bool]): Prevent DISM from contacting Windows
            Update for online images

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.install_feature NetFx3
    '''
    return _install_component(feature, "Feature", "Enable", source, limit_access)


def uninstall_feature(feature):
    '''
    Uninstall a feature

    Args:
        feature (str): The feature to uninstall

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.uninstall_feature NetFx3
    '''
    return _uninstall_component(feature, "Feature", "Disable")


def installed_features():
    '''
    List the features installed on the system

    Returns:
        list: A list of installed features

    CLI Example:

    .. code-block:: bash

        salt '*' dism.installed_features
    '''
    return _get_components("Feature Name", "Features", "Enabled")


def available_features():
    '''
    List the features available on the system

    Returns:
        list: A list of available features

    CLI Example:

    .. code-block:: bash

        salt '*' dism.available_features
    '''
    return _get_components("Feature Name", "Features", "Disabled")


def installed_packages():
    '''
    List the packages installed on the system

    Returns:
        list: A list of installed packages

    CLI Example:

    .. code-block:: bash

        salt '*' dism.installed_packages
    '''
    return _get_components("Package Identity", "Features", "Installed")


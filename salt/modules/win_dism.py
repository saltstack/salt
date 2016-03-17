# -*- coding: utf-8 -*-
'''
Install features/packages for Windows using DISM, which
is useful for minions not running server versions of
windows

'''
from __future__ import absolute_import

# Import python libs
import re
import logging

# Import salt libs
import salt.utils

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
    cmd = 'DISM /Online /{0}-{1} /{1}Name:{2}'.format(uninstall_name, component_type, name)

    return __salt__['cmd.run_all'](cmd)


def _get_components(type_regex, plural_type, install_value):
    cmd = 'DISM /Online /Get-{0}'.format(plural_type)
    out = __salt__['cmd.run'](cmd)
    pattern = r'{0} : (.*)\r\n.*State : {1}\r\n'.format(type_regex, install_value)
    capabilities = re.findall(pattern, out, re.MULTILINE)
    return capabilities


def install_capability(capability, source=None, limit_access=False):
    '''
    Install a capability

    CLI Example:

    .. code-block:: bash

        salt '*' dism.install_capability Tools.Graphics.DirectX~~~~0.0.1.0

    capability
        The capability in which to install

    source
        The optional source of the capability

    limit_access
        Prevent DISM from contacting Windows Update for online images

    '''
    return _install_component(capability, "Capability", "Add", source, limit_access)


def uninstall_capability(capability):
    '''
    Uninstall a capability

    CLI Example:

    .. code-block:: bash

        salt '*' dism.uninstall_capability Tools.Graphics.DirectX~~~~0.0.1.0

    capability
        The capability in which to uninstall

    '''
    return _uninstall_component(capability, "Capability", "Remove")


def installed_capabilities():
    '''
    List the capabilities installed on the system

    CLI Example:

    .. code-block:: bash

        salt '*' dism.installed_capabilities
    '''
    return _get_components("Capability Identity", "Capabilities", "Installed")


def install_feature(capability, source=None, limit_access=False):
    '''
    Install a feature using DISM

    CLI Example:

    .. code-block:: bash

        salt '*' dism.install_feature NetFx3

    feature
        The feature in which to install

    source
        The optional source of the feature

    limit_access
        Prevent DISM from contacting Windows Update for online images

    '''
    return _install_component(capability, "Feature", "Enable", source, limit_access)


def uninstall_feature(capability):
    '''
    Uninstall a feature

    CLI Example:

    .. code-block:: bash

        salt '*' dism.uninstall_feature NetFx3

    feature
        The feature in which to uninstall

    '''
    return _uninstall_component(capability, "Feature", "Disable")


def installed_features():
    '''
    List the features installed on the system

    CLI Example:

    .. code-block:: bash

        salt '*' dism.installed_features
    '''
    return _get_components("Feature Name", "Features", "Enabled")

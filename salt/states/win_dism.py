# -*- coding: utf-8 -*-
'''
Installing of Windows features using DISM
=======================

Install windows features/capabilties with DISM

.. code-block:: yaml

    Language.Basic~~~en-US~0.0.1.0:
      dism.capability_installed

    NetFx3:
      dism.feature_installed
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = "dism"


def __virtual__():
    '''
    Only work on Windows where the DISM module is available
    '''
    if not salt.utils.is_windows():
        return False, 'Module only available on Windows'

    if 'dism.add_capability' not in __salt__:
        return False, 'DISM module not available'

    return __virtualname__


def capability_installed(name, source=None, limit_access=False):
    '''
    Install a DISM capability

    Args:
        name (str): The capability to install
        source (str): The optional source of the capability
        limit_access (bool): Prevent DISM from contacting Windows Update for
            online images

    Example:
        Run ``dism.available_capabilities`` to get a list of available
        capabilities. This will help you get the proper name to use.

        .. code-block:: yaml

            install_dotnet35:
              dism.capability_installed:
                - name: NetFX3~~~~
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    old = __salt__['dism.installed_capabilities']()

    if name in old:
        ret['comment'] = 'The capability {0} is already installed'.format(name)
        return ret

    if __opts__['test']:
        ret['changes']['capability'] = '{0} will be installed'.format(name)
        ret['result'] = None
        return ret

    # Install the capability
    status = __salt__['dism.add_capability'](name, source, limit_access)

    if status['retcode'] != 0:
        ret['comment'] = 'Failed to install {0}: {1}'\
            .format(name, status['stdout'])

    new = __salt__['dism.installed_capabilities']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Installed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['capability'] = changes

    return ret


def capability_removed(name):
    '''
    Uninstall a DISM capability

    Args:
        name (str): The capability to uninstall

    Example:
        Run ``dism.installed_capabilities`` to get a list of installed
        capabilities. This will help you get the proper name to use.

        .. code-block:: yaml

            remove_dotnet35:
              dism.capability_removed:
                - name: NetFX3~~~~
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    old = __salt__['dism.installed_capabilities']()

    if name not in old:
        ret['comment'] = 'The capability {0} is already removed'.format(name)
        return ret

    if __opts__['test']:
        ret['changes']['capability'] = '{0} will be removed'.format(name)
        ret['result'] = None
        return ret

    # Remove the capability
    status = __salt__['dism.remove_capability'](name)

    if status['retcode'] != 0:
        ret['comment'] = 'Failed to remove {0}: {1}' \
            .format(name, status['stdout'])

    new = __salt__['dism.installed_capabilities']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Removed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['capability'] = changes

    return ret


def feature_installed(name, source=None, limit_access=False):
    '''
    Install a DISM feature

    Args:
        name (str): The feature in which to install
        source (str): The optional source of the feature
        limit_access (bool): Prevent DISM from contacting Windows Update for
            online images

    Example:
        Run ``dism.available_features`` to get a list of available features.
        This will help you get the proper name to use.

        .. code-block:: yaml

            install_telnet_client:
              dism.feature_installed:
                - name: TelnetClient
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    old = __salt__['dism.installed_features']()

    if name in old:
        ret['comment'] = 'The feature {0} is already installed'.format(name)
        return ret

    if __opts__['test']:
        ret['changes']['feature'] = '{0} will be installed'.format(name)
        ret['result'] = None
        return ret

    # Install the feature
    status = __salt__['dism.add_feature'](name, source, limit_access)

    if status['retcode'] != 0:
        ret['comment'] = 'Failed to install {0}: {1}' \
            .format(name, status['stdout'])

    new = __salt__['dism.installed_features']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Installed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['feature'] = changes

    return ret


def feature_removed(name, remove_payload=False):
    '''
    Disables a feature.

    Args:
        name (str): The feature to disable
        remove_payload (Optional[bool]): Remove the feature's payload. Must
            supply source when enabling in the future.

    Example:
        Run ``dism.installed_features`` to get a list of installed features.
        This will help you get the proper name to use.

        .. code-block:: yaml

            remove_telnet_client:
              dism.feature_removed:
                - name: TelnetClient
                - remove_payload: True
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    old = __salt__['dism.installed_features']()

    if name not in old:
        ret['comment'] = 'The feature {0} is already removed'.format(name)
        return ret

    if __opts__['test']:
        ret['changes']['feature'] = '{0} will be removed'.format(name)
        ret['result'] = None
        return ret

    # Install the feature
    status = __salt__['dism.remove_feature'](name, source, limit_access)

    if status['retcode'] != 0:
        ret['comment'] = 'Failed to remove {0}: {1}' \
            .format(name, status['stdout'])

    new = __salt__['dism.installed_features']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Removed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['feature'] = changes

    return ret


def package_installed(name, ignore_check=False, prevent_pending=False):
    '''
    Install a package.

    Args:
        package (str): The package to install. Can be a .cab file, a .msu file,
            or a folder
        ignore_check (Optional[bool]): Skip installation of the package if the
            applicability checks fail
        prevent_pending (Optional[bool]): Skip the installation of the package
            if there are pending online actions

    Example:

        .. code-block:: yaml

            install_KB123123123:
              dism.package_installed:
                - name: C:\\Packages\\KB123123123.cab
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    old = __salt__['dism.installed_packages']()

    # Get package info so we can see if it's already installed
    package_info = __salt__['dism.package_info'](name)

    if package_info['Package Identity'] in old:
        ret['comment'] = 'The package {0} is already installed: {1}'\
            .format(name, package_info['Package Identity'])
        return ret

    if __opts__['test']:
        ret['changes']['package'] = '{0} will be installed'.format(name)
        ret['result'] = None
        return ret

    # Install the feature
    status = __salt__['dism.add_package'](name, ignore_check, prevent_pending)

    if status['retcode'] != 0:
        ret['comment'] = 'Failed to install {0}: {1}' \
            .format(name, status['stdout'])

    new = __salt__['dism.installed_packages']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Installed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['feature'] = changes

    return ret


def package_removed(name, ignore_check=False, prevent_pending=False):
    '''
    Uninstall a package

    Args:
        package (str): The full path to the package. Can be either a .cab file
            or a folder. Should point to the original source of the package, not
            to where the file is installed.

            This can also be the name of a package as listed in
            ``dism.installed_packages``

    Example:

        .. code-block:: yaml

            # Example using source
            remove_KB1231231:
              dism.package_installed:
                - name: C:\\Packages\\KB1231231.cab

            # Example using name from ``dism.installed_packages``
            remove_KB1231231:
              dism.package_installed:
                - name: Package_for_KB1231231~31bf3856ad364e35~amd64~~10.0.1.3
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    old = __salt__['dism.installed_packages']()

    # Get package info so we can see if it's already removed
    package_info = __salt__['dism.package_info'](name)

    # If `Package Identity` isn't returned or if they passed a cab file, if
    # `Package Identity` isn't in the list of installed packages
    if 'Package Identity' not in package_info or \
            package_info['Package Identity'] not in old:
        ret['comment'] = 'The package {0} is already removed'
        return ret

    if __opts__['test']:
        ret['changes']['package'] = '{0} will be removed'.format(name)
        ret['result'] = None
        return ret

    # Install the feature
    status = __salt__['dism.remove_package'](name, ignore_check, prevent_pending)

    if status['retcode'] != 0:
        ret['comment'] = 'Failed to remove {0}: {1}' \
            .format(name, status['stdout'])

    new = __salt__['dism.installed_packages']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Removed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['feature'] = changes

    return ret


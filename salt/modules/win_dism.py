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
    if not salt.utils.is_windows():
        return False, "Only available on Windows systems"

    return __virtualname__


def _get_components(type_regex, plural_type, install_value):
    cmd = 'DISM /Online /Get-{0}'.format(plural_type)
    out = __salt__['cmd.run'](cmd)
    pattern = r'{0} : (.*)\r\n.*State : {1}\r\n'\
              .format(type_regex, install_value)
    capabilities = re.findall(pattern, out, re.MULTILINE)
    capabilities.sort()
    return capabilities


def add_capability(capability, source=None, limit_access=False):
    '''
    Install a capability

    Args:
        capability (str): The capability to install
        source (Optional[str]): The optional source of the capability. Default
            is set by group policy and can be Windows Update.
        limit_access (Optional[bool]): Prevent DISM from contacting Windows
            Update for the source package

    Raises:
        NotImplemented Error for all versions of Windows that are not Windows 10
        and later. Server editions of Windows use ServerManager instead.

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.add_capability Tools.Graphics.DirectX~~~~0.0.1.0
    '''
    if salt.utils.version_cmp(__grains__['osversion'], '10') == -1:
        raise NotImplemented(
            '`install_capability` is not available on this version of Windows: '
            '{0}'.format(__grains__['osversion']))

    cmd = 'DISM /Online /Add-Capability /CapabilityName:{0}'.format(capability)

    if source:
        cmd += ' /Source:{0}'.format(source)
    if limit_access:
        cmd += ' /LimitAccess'

    return __salt__['cmd.run_all'](cmd)


def remove_capability(capability):
    '''
    Uninstall a capability

    Args:
        capability(str): The capability to be removed

    Raises:
        NotImplemented Error for all versions of Windows that are not Windows 10
        and later. Server editions of Windows use ServerManager instead.

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.remove_capability Tools.Graphics.DirectX~~~~0.0.1.0
    '''
    if salt.utils.version_cmp(__grains__['osversion'], '10') == -1:
        raise NotImplemented(
            '`uninstall_capability` is not available on this version of '
            'Windows: {0}'.format(__grains__['osversion']))

    cmd = 'DISM /Online /Remove-Capability ' \
          '/CapabilityName:{0}'.format(capability)

    return __salt__['cmd.run_all'](cmd)


def get_capabilities():
    '''
    List all capabilities on the system

    Raises:
        NotImplemented Error for all versions of Windows that are not Windows 10
        and later. Server editions of Windows use ServerManager instead.

    Returns:
        list: A list of capabilities

    CLI Example:

    .. code-block:: bash

        salt '*' dism.get_capabilities
    '''
    if salt.utils.version_cmp(__grains__['osversion'], '10') == -1:
        raise NotImplemented(
            '`installed_capabilities` is not available on this version of '
            'Windows: {0}'.format(__grains__['osversion']))

    cmd = 'DISM /Online /Get-Capabilities'
    out = __salt__['cmd.run'](cmd)

    pattern = r'Capability Identity : (.*)'
    capabilities = re.findall(pattern, out, re.MULTILINE)
    capabilities.sort()

    return capabilities


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


def available_capabilities():
    '''
    List the capabilities available on the system

    Raises:
        NotImplemented Error for all versions of Windows that are not Windows 10
        and later. Server editions of Windows use ServerManager instead.

    Returns:
        list: A list of available capabilities

    CLI Example:

    .. code-block:: bash

        salt '*' dism.installed_capabilities
    '''
    if salt.utils.version_cmp(__grains__['osversion'], '10') == -1:
        raise NotImplemented(
            '`installed_capabilities` is not available on this version of '
            'Windows: {0}'.format(__grains__['osversion']))
    return _get_components("Capability Identity", "Capabilities", "Not Present")


def add_feature(feature,
                package=None,
                source=None,
                limit_access=False,
                enable_parent=False,):
    '''
    Install a feature using DISM

    Args:
        feature (str): The feature to install
        package (Optional[str]): The parent package for the feature. You do not
            have to specify the package if it is the Windows Foundation Package.
            Otherwise, use package to specify the parent package of the feature
        source (Optional[str]): The optional source of the capability. Default
            is set by group policy and can be Windows Update
        limit_access (Optional[bool]): Prevent DISM from contacting Windows
            Update for the source package
        enable_parent (Optional[bool]): True will enable all parent features of
            the specified feature

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.add_feature NetFx3
    '''
    cmd = 'DISM /Online /Enable-Feature /FeatureName:{0}'.format(feature)
    if package:
        cmd += ' /PackageName:{0}'.format(package)
    if source:
        cmd += ' /Source:{0}'.format(source)
    if limit_access:
        cmd += ' /LimitAccess'
    if enable_parent:
        cmd += ' /All'

    return __salt__['cmd.run_all'](cmd)


def remove_feature(feature, remove_payload=False):
    '''
    Disables the feature.

    Args:
        feature (str): The feature to uninstall
        remove_payload (Optional[bool]): Remove the feature's payload. Must
            supply source when enabling in the future.

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.remove_feature NetFx3
    '''
    cmd = 'DISM /Online /Disable-Feature /FeatureName:{0}'.format(feature)

    if remove_payload:
        cmd += ' /Remove'

    return __salt__['cmd.run_all'](cmd)


def get_features(package=None):
    '''
    List features on the system or in a package

    Args:
        package (Optional[str]): The full path to the package. Can be either a
            .cab file or a folder. Should point to the original source of the
            package, not to where the file is installed. You cannot use this
            command to get package information for .msu files

            This can also be the name of a package as listed in
            ``dism.installed_packages``

    Returns:
        list: A list of features

    CLI Example:

        .. code-block:: bash

            # Return all features on the system
            salt '*' dism.get_features

            # Return all features in package.cab
            salt '*' dism.get_features C:\\packages\\package.cab

            # Return all features in the calc package
            salt '*' dism.get_features Microsoft.Windows.Calc.Demo~6595b6144ccf1df~x86~en~1.0.0.0
    '''

    cmd = 'DISM /Online /Get-Features'

    if package:
        if '~' in package:
            cmd += ' /PackageName:{0}'.format(package)
        else:
            cmd += ' /PackagePath:{0}'.format(package)

    out = __salt__['cmd.run'](cmd)

    pattern = r'Feature Name : (.*)'
    capabilities = re.findall(pattern, out, re.MULTILINE)
    capabilities.sort()

    return capabilities


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


def add_package(package, ignore_check=False, prevent_pending=False):
    '''
    Install a package using DISM

    Args:
        package (str): The package to install. Can be a .cab file, a .msu file,
            or a folder
        ignore_check (Optional[bool]): Skip installation of the package if the
            applicability checks fail
        prevent_pending (Optional[bool]): Skip the installation of the package
            if there are pending online actions

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism.add_package C:\\Packages\\package.cab
    '''
    cmd = 'DISM /Online /Add-Package ' \
          '/PackagePath:{0}'.format(package)

    if ignore_check:
        cmd += ' /IgnoreCheck'
    if prevent_pending:
        cmd += ' /PreventPending'

    return __salt__['cmd.run_all'](cmd)


def remove_package(package):
    '''
    Uninstall a package

    Args:
        package (str): The full path to the package. Can be either a .cab file
            or a folder. Should point to the original source of the package, not
            to where the file is installed.

            This can also be the name of a package as listed in
            ``dism.installed_packages``

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        # Remove the Calc Package
        salt '*' dism.remove_package Microsoft.Windows.Calc.Demo~6595b6144ccf1df~x86~en~1.0.0.0

        # Remove the package.cab (does not remove C:\\packages\\package.cab)
        salt '*' dism.remove_package C:\\packages\\package.cab
    '''
    cmd = 'DISM /Online /Remove-Package'

    if '~' in package:
        cmd += ' /PackageName:{0}'.format(package)
    else:
        cmd += ' /PackagePath:{0}'.format(package)

    return __salt__['cmd.run_all'](cmd)


def installed_packages():
    '''
    List the packages installed on the system

    Returns:
        list: A list of installed packages

    CLI Example:

    .. code-block:: bash

        salt '*' dism.installed_packages
    '''
    return _get_components("Package Identity", "Packages", "Installed")


def package_info(package):
    '''
    Display information about a package

    Args:
        package (str): The full path to the package. Can be either a .cab file
            or a folder. Should point to the original source of the package, not
            to where the file is installed. You cannot use this command to get
            package information for .msu files

    Returns:
        dict: A dictionary containing the results of the command

    CLI Example:

    .. code-block:: bash

        salt '*' dism. package_info C:\\packages\\package.cab
    '''
    cmd = 'DISM /Online /Get-PackageInfo'

    if '~' in package:
        cmd += ' /PackageName:{0}'.format(package)
    else:
        cmd += ' /PackagePath:{0}'.format(package)

    out = __salt__['cmd.run_all'](cmd)

    if out['retcode'] == 0:
        ret = dict()
        for line in str(out['stdout']).splitlines():
            if ' : ' in line:
                info = line.split(' : ')
                if len(info) < 2:
                    continue
                ret[info[0]] = info[1]
    else:
        ret = out

    return ret

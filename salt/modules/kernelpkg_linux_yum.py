# -*- coding: utf-8 -*-
'''
Manage Linux kernel packages on YUM-based systems
'''
from __future__ import absolute_import
import functools
import logging

# Import Salt libs
import salt.ext.six as six

try:
    from salt.utils.versions import LooseVersion as _LooseVersion
    HAS_REQUIRED_LIBS = True
except ImportError:
    HAS_REQUIRED_LIBS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'kernelpkg'


def __virtual__():
    '''
    Load this module on RedHat-based systems only
    '''

    if not HAS_REQUIRED_LIBS:
        return (False, "Required library could not be imported")

    if __grains__.get('os_family', '') == 'RedHat':
        return __virtualname__
    elif __grains__.get('os', '').lower() \
            in ('amazon', 'xcp', 'xenserver', 'virtuozzolinux'):
        return __virtualname__

    return (False, "Module kernelpkg_linux_yum: no YUM based system detected")


def active():
    '''
    Return the version of the running kernel.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.active
    '''
    if 'pkg.normalize_name' in __salt__:
        return __salt__['pkg.normalize_name'](__grains__['kernelrelease'])

    return __grains__['kernelrelease']


def list_installed():
    '''
    Return a list of all installed kernels.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.list_installed
    '''
    result = __salt__['pkg.version'](_package_name(), versions_as_list=True)
    if result is None:
        return []

    if six.PY2:
        return sorted(result, cmp=_cmp_version)
    else:
        return sorted(result, key=functools.cmp_to_key(_cmp_version))


def latest_available():
    '''
    Return the version of the latest kernel from the package repositories.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.latest_available
    '''
    result = __salt__['pkg.latest_version'](_package_name())
    if result == '':
        result = latest_installed()
    return result


def latest_installed():
    '''
    Return the version of the latest installed kernel.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.latest_installed

    .. note::

        This function may not return the same value as
        :py:func:`~salt.modules.kernelpkg.active` if a new kernel
        has been installed and the system has not yet been rebooted.
        The :py:func:`~salt.modules.kernelpkg.needs_reboot` function
        exists to detect this condition.
    '''
    pkgs = list_installed()
    if pkgs:
        return pkgs[-1]

    return None


def needs_reboot():
    '''
    Detect if a new kernel version has been installed but is not running.
    Returns True if a new kernel is installed, False otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.needs_reboot
    '''
    return _LooseVersion(active()) < _LooseVersion(latest_installed())


def upgrade(reboot=False, at_time=None):
    '''
    Upgrade the kernel and optionally reboot the system.

    reboot : False
        Request a reboot if a new kernel is available.

    at_time : immediate
        Schedule the reboot at some point in the future. This argument
        is ignored if ``reboot=False``. See
        :py:func:`~salt.modules.system.reboot` for more details
        on this argument.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.upgrade
        salt '*' kernelpkg.upgrade reboot=True at_time=1

    .. note::
    An immediate reboot often shuts down the system before the minion
    has a chance to return, resulting in errors. A minimal delay (1 minute)
    is useful to ensure the result is delivered to the master.
    '''
    result = __salt__['pkg.upgrade'](name=_package_name())
    _needs_reboot = needs_reboot()

    ret = {
        'upgrades': result,
        'active': active(),
        'latest_installed': latest_installed(),
        'reboot_requested': reboot,
        'reboot_required': _needs_reboot
    }

    if reboot and _needs_reboot:
        log.warning('Rebooting system due to kernel upgrade')
        __salt__['system.reboot'](at_time=at_time)

    return ret


def upgrade_available():
    '''
    Detect if a new kernel version is available in the repositories.
    Returns True if a new kernel is avaliable, False otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' kernelpkg.upgrade_available
    '''
    return _LooseVersion(latest_available()) > _LooseVersion(latest_installed())


def _package_name():
    '''
    Return static string for the package name
    '''
    return 'kernel'


def _cmp_version(item1, item2):
    '''
    Compare function for package version sorting
    '''
    v1 = _LooseVersion(item1)
    v2 = _LooseVersion(item2)

    if v1 < v2:
        return -1
    if v1 > v2:
        return 1
    return 0

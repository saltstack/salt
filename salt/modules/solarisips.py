# -*- coding: utf-8 -*-
'''
IPS pkg support for Solaris

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

This module provides support for Solaris 11 new package management - IPS (Image Packaging System).
This is the default pkg module for Solaris 11 (and later).

If you want to use also other packaging module (e.g. pkgutil) together with IPS, you need to override the ``pkg`` provider
in sls for each package:

.. code-block:: yaml

    mypackage:
      pkg.installed:
        - provider: pkgutil

Or you can override it globally by setting the :conf_minion:`providers` parameter in your Minion config file like this:

.. code-block:: yaml

    providers:
      pkg: pkgutil

Or you can override it globally by setting the :conf_minion:`providers` parameter in your Minion config file like this:

.. code-block:: yaml

    providers:
      pkg: pkgutil

'''
# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import logging


# Import salt libs
import salt.utils

# Define the module's virtual name
__virtualname__ = 'pkg'
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is Solaris 11
    '''
    if __grains__['os'] == 'Solaris' and float(__grains__['kernelrelease']) > 5.10:
        return __virtualname__
    return False


ips_pkg_return_values = {
        0: 'Command succeeded.',
        1: 'An error occurred.',
        2: 'Invalid command line options were specified.',
        3: 'Multiple operations were requested, but only some of them succeeded.',
        4: 'No changes were made - nothing to do.',
        5: 'The requested operation cannot be performed on a  live image.',
        6: 'The requested operation cannot  be  completed  because the  licenses  for  the  packages  being  installed or updated have not been accepted.',
        7: 'The image is currently in use by another process and cannot be modified.'
        }


def _ips_get_pkgname(line):
    '''
    Extracts package name from "pkg list -v" output.
    Input: one line of the command output
    Output: pkg name (e.g.: "pkg://solaris/x11/library/toolkit/libxt")
    Example use:
    line = "pkg://solaris/x11/library/toolkit/libxt@1.1.3,5.11-0.175.1.0.0.24.1317:20120904T180030Z i--"
    name = _ips_get_pkgname(line)
    '''
    return line.split()[0].split('@')[0].strip()


def _ips_get_pkgversion(line):
    '''
    Extracts package version from "pkg list -v" output.
    Input: one line of the command output
    Output: package version (e.g.: "1.1.3,5.11-0.175.1.0.0.24.1317:20120904T180030Z")
    Example use:
    line = "pkg://solaris/x11/library/toolkit/libxt@1.1.3,5.11-0.175.1.0.0.24.1317:20120904T180030Z i--"
    name = _ips_get_pkgversion(line)
    '''
    return line.split()[0].split('@')[1].strip()


def refresh_db(full=False):
    '''
    Updates the remote repos database. You can force the full pkg DB refresh from all publishers regardless the last refresh time.

    CLI Example::

        salt '*' pkg.refresh_db
        salt '*' pkg.refresh_db full=True
    '''
    if full:
        return __salt__['cmd.retcode']('/bin/pkg refresh --full') == 0
    else:
        return __salt__['cmd.retcode']('/bin/pkg refresh') == 0


def upgrade_available(name):
    '''
    Check if there is an upgrade available for a certain package
    Accepts full or partial FMRI. Returns all matches found.

    CLI Example::

        salt '*' pkg.upgrade_available apache-22
    '''
    version = None
    cmd = 'pkg list -Huv {0}'.format(name)
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    if not lines:
        return {}
    ret = {}
    for line in lines:
        ret[_ips_get_pkgname(line)] = _ips_get_pkgversion(line)
    return ret


def list_upgrades(refresh=False):
    '''
    Lists all packages available for update.
    When run in global zone, it reports only upgradable packages for the global zone.
    When run in non-global zone, it can report more upgradable packages than "pkg update -vn" because "pkg update" hides packages that require newer version of pkg://solaris/entire (which means that they can be upgraded only from global zone). Simply said: if you see pkg://solaris/entire in the list of upgrades, you should upgrade the global zone to get all possible updates.
    You can force full pkg DB refresh before listing.

    CLI Example::

        salt '*' pkg.list_upgrades
        salt '*' pkg.list_upgrades refresh=True
    '''
    if salt.utils.is_true(refresh):
        refresh_db(full=True)
    upgrades = {}
    # awk is in core-os package so we can use it without checking
    lines = __salt__['cmd.run_stdout']("/bin/pkg list -Huv").splitlines()
    for line in lines:
        upgrades[_ips_get_pkgname(line)] = _ips_get_pkgversion(line)
    return upgrades


def upgrade(refresh=False, **kwargs):
    '''
    Upgrade all packages to the latest possible version.
    When run in global zone, it updates also all non-global zones.
    In non-global zones upgrade is limited by dependency constrains linked to the version of pkg://solaris/entire.

    Returns also a raw output of "pkg update" command (because if update creates a new boot environment, no immediate changes are visible in "pkg list").

    CLI Example::

        salt '*' pkg.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = list_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd = 'pkg update -v --accept '
    ret = __salt__['cmd.run_all'](cmd)

    # Get a list of the packages again, including newly installed ones.
    new = list_pkgs()

    changes = salt.utils.compare_dicts(old, new)

    output = {}
    output['changes_in_current_be'] = changes
    if ret['retcode']:
        output['retcode'] = ips_pkg_return_values[ret['retcode']]   # translate error code if applicable
        output['message'] = ret['stderr'] + '\n'
    else:
        output['raw_out'] = ret['stdout'] + '\n'
    return output


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the currently installed packages as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    # not yet implemented or not applicable
    if any([salt.utils.is_true(kwargs.get(x))
        for x in ('removed', 'purge_desired')]):
        return {}

    ret = {}
    cmd = '/bin/pkg list -Hv'
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    # column 1 is full FMRI name in form pkg://publisher/class/name@version
    for line in lines:
        name = _ips_get_pkgname(line)
        version = _ips_get_pkgversion(line)
        __salt__['pkg_resource.add_pkg'](ret, name, version)

    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def version(*names, **kwargs):
    '''
    Common interface for obtaining the version of installed packages.
    Accepts full or partial FMRI. If called using pkg_resource, full FMRI is required.

    CLI Example::

        salt '*' pkg.version vim
        salt '*' pkg.version foo bar baz
        salt '*' pkg_resource.version pkg://solaris/entire

    '''
    namelist = ''
    for pkgname in names:
        namelist += '{0} '.format(pkgname)
    cmd = '/bin/pkg list -Hv {0}'.format(namelist)
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    ret = {}
    for line in lines:
        ret[_ips_get_pkgname(line)] = _ips_get_pkgversion(line)
    if ret:
        return ret
    return ''


def latest_version(name, **kwargs):
    '''
    The available version of the package in the repository.
    In case of multiple match, it returns list of all matched packages.
    Accepts full or partial FMRI.
    Please use pkg.latest_version as pkg.available_version is being deprecated.

    CLI Example::

        salt '*' pkg.latest_version pkg://solaris/entire
    '''
    cmd = '/bin/pkg list -Hnv {0}'.format(name)
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    ret = {}
    for line in lines:
        ret[_ips_get_pkgname(line)] = _ips_get_pkgversion(line)
    if ret:
        return ret
    return ''

# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def get_fmri(name, **kwargs):
    '''
    Returns FMRI from partial name. Returns empty string ('') if not found.
    In case of multiple match, the function returns list of all matched packages.

    CLI Example::

        salt '*' pkg.get_fmri bash
    '''
    if name.startswith('pkg://'):
        # already full fmri
        return name
    cmd = '/bin/pkg list -aHv {0}'.format(name)
    # there can be more packages matching the name
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    if not lines:
        # empty string = package not found
        return ''
    ret = []
    for line in lines:
        ret.append(_ips_get_pkgname(line))

    return ret


def normalize_name(name, **kwargs):
    '''
    Internal function. Normalizes pkg name to full FMRI before running pkg.install.
    In case of multiple match or no match, it returns the name without modifications and lets the "pkg install" to decide what to do.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.normalize_name vim
    '''
    if name.startswith('pkg://'):
        # already full fmri
        return name
    cmd = '/bin/pkg list -aHv {0}'.format(name)
    # there can be more packages matching the name
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    # if we get more lines, it's multiple match (name not unique)
    # if we get zero lines, pkg is not installed
    # in both ways it's safer to return original (unmodified) name and let "pkg install" to deal with it
    if len(lines) != 1:
        return name
    # return pkg name
    return _ips_get_pkgname(lines[0])


def is_installed(name, **kwargs):
    '''
    Returns True if the package is installed. Otherwise returns False.
    Name can be full or partial FMRI.
    In case of multiple match from partial FMRI name, it returns True.

    CLI Example::

        salt '*' pkg.is_installed bash
    '''

    cmd = '/bin/pkg list -Hv {0}'.format(name)
    return __salt__['cmd.retcode'](cmd) == 0


def search(name, versions_as_list=False, **kwargs):
    '''
    Searches the repository for given pkg name.
    The name can be full or partial FMRI. All matches are printed. Globs are also supported.

    CLI Example::

        salt '*' pkg.search bash
    '''

    ret = {}
    cmd = '/bin/pkg list -aHv {0}'.format(name)
    out = __salt__['cmd.run_all'](cmd)
    if out['retcode'] != 0:
        # error = nothing found
        return {}
    # no error, processing pkg listing
    # column 1 is full FMRI name in form pkg://publisher/pkg/name@version
    for line in out['stdout'].splitlines():
        name = _ips_get_pkgname(line)
        version = _ips_get_pkgversion(line)
        __salt__['pkg_resource.add_pkg'](ret, name, version)

    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def install(name=None, refresh=False, pkgs=None, version=None, test=False, **kwargs):
    '''
    Install the named package using the IPS pkg command.
    Accepts full or partial FMRI.

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}


    Multiple Package Installation Options:

    pkgs
        A list of packages to install. Must be passed as a python list.


    CLI Example::

        salt '*' pkg.install vim
        salt '*' pkg.install pkg://solaris/editor/vim
        salt '*' pkg.install pkg://solaris/editor/vim refresh=True
        salt '*' pkg.install pkgs='["foo", "bar"]'
    '''
    if not pkgs:
        if is_installed(name):
            return 'Package already installed.'

    if refresh:
        refresh_db(full=True)

    pkg2inst = ''
    if pkgs:    # multiple packages specified
        for pkg in pkgs:
            if list(pkg.items())[0][1]:   # version specified
                pkg2inst += '{0}@{1} '.format(list(pkg.items())[0][0], list(pkg.items())[0][1])
            else:
                pkg2inst += '{0} '.format(list(pkg.items())[0][0])
        log.debug('Installing these packages instead of {0}: {1}'.format(name, pkg2inst))

    else:   # install single package
        if version:
            pkg2inst = "{0}@{1}".format(name, version)
        else:
            pkg2inst = "{0}".format(name)

    cmd = 'pkg install -v --accept '
    if test:
        cmd += '-n '

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = list_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd += '{0}'.format(pkg2inst)
    #ret = __salt__['cmd.retcode'](cmd)
    ret = __salt__['cmd.run_all'](cmd)

    # Get a list of the packages again, including newly installed ones.
    new = list_pkgs()

    changes = salt.utils.compare_dicts(old, new)

    if ret['retcode'] != 0:     # there's something worth looking at
        output = {}             # so we're adding some additional info
        output['changes'] = changes
        output['retcode'] = ips_pkg_return_values[ret['retcode']]   # translate error code
        output['message'] = ret['stderr'] + '\n'
        return output

    # No error occurred
    if test:
        return "Test succeeded."

    # Return a list of the new packages installed.
    return changes


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove specified package. Accepts full or partial FMRI.
    In case of multiple match, the command fails and won't modify the OS.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove tcsh
        salt '*' pkg.remove pkg://solaris/shell/tcsh
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''

    # Check to see if the package is installed before we proceed
    if not pkgs:
        if not is_installed(name):
            return ''

    pkg2rm = ''
    if pkgs:    # multiple packages specified
        for pkg in pkgs:
            pkg2rm += '{0} '.format(pkg)
        log.debug('Installing these packages instead of {0}: {1}'.format(name, pkg2rm))
    else:   # remove single package
        pkg2rm = "{0}".format(name)

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Remove the package(s)
    cmd = '/bin/pkg uninstall -v {0}'.format(pkg2rm)
    ret = __salt__['cmd.run_all'](cmd)

    # Get a list of the packages after the uninstall
    new = list_pkgs()

    # Compare the pre and post remove package objects and report the uninstalled pkgs.
    changes = salt.utils.compare_dicts(old, new)

    if ret['retcode'] != 0:     # there's something worth looking at
        output = {}             # so we're adding some additional info
        output['changes'] = changes
        output['retcode'] = ips_pkg_return_values[ret['retcode']]   # translate error code
        output['message'] = ret['stderr'] + '\n'
        return output

    # No error occurred
    return changes


def purge(name, **kwargs):
    '''
    Remove specified package. Accepts full or partial FMRI.

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(name, **kwargs)

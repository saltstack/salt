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
from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging


# Import salt libs
import salt.utils.data
import salt.utils.functools
import salt.utils.path
import salt.utils.pkg
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'pkg'
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is Solaris 11
    '''
    if __grains__['os_family'] == 'Solaris' \
            and float(__grains__['kernelrelease']) > 5.10 \
            and salt.utils.path.which('pkg'):
        return __virtualname__
    return (False,
            'The solarisips execution module failed to load: only available '
            'on Solaris >= 11.')


ips_pkg_return_values = {
    0: 'Command succeeded.',
    1: 'An error occurred.',
    2: 'Invalid command line options were specified.',
    3: 'Multiple operations were requested, but only some of them succeeded.',
    4: 'No changes were made - nothing to do.',
    5: 'The requested operation cannot be performed on a  live image.',
    6: 'The requested operation cannot be completed because the licenses for '
       'the packages being installed or updated have not been accepted.',
    7: 'The image is currently in use by another process and cannot be '
       'modified.'
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
    Updates the remote repos database.

    full : False

        Set to ``True`` to force a refresh of the pkg DB from all publishers,
        regardless of the last refresh time.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
        salt '*' pkg.refresh_db full=True
    '''
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    if full:
        return __salt__['cmd.retcode']('/bin/pkg refresh --full') == 0
    else:
        return __salt__['cmd.retcode']('/bin/pkg refresh') == 0


def upgrade_available(name):
    '''
    Check if there is an upgrade available for a certain package
    Accepts full or partial FMRI. Returns all matches found.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available apache-22
    '''
    version = None
    cmd = ['pkg', 'list', '-Huv', name]
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    if not lines:
        return {}
    ret = {}
    for line in lines:
        ret[_ips_get_pkgname(line)] = _ips_get_pkgversion(line)
    return ret


def list_upgrades(refresh=True, **kwargs):  # pylint: disable=W0613
    '''
    Lists all packages available for update.

    When run in global zone, it reports only upgradable packages for the global
    zone.

    When run in non-global zone, it can report more upgradable packages than
    ``pkg update -vn``, because ``pkg update`` hides packages that require
    newer version of ``pkg://solaris/entire`` (which means that they can be
    upgraded only from the global zone). If ``pkg://solaris/entire`` is found
    in the list of upgrades, then the global zone should be updated to get all
    possible updates. Use ``refresh=True`` to refresh the package database.

    refresh : True
        Runs a full package database refresh before listing. Set to ``False`` to
        disable running the refresh.

        .. versionchanged:: 2017.7.0

        In previous versions of Salt, ``refresh`` defaulted to ``False``. This was
        changed to default to ``True`` in the 2017.7.0 release to make the behavior
        more consistent with the other package modules, which all default to ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
        salt '*' pkg.list_upgrades refresh=False
    '''
    if salt.utils.data.is_true(refresh):
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
    In non-global zones upgrade is limited by dependency constrains linked to
    the version of pkg://solaris/entire.

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    When there is a failure, an explanation is also included in the error
    message, based on the return code of the ``pkg update`` command.


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    if salt.utils.data.is_true(refresh):
        refresh_db()

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = list_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd = ['pkg', 'update', '-v', '--accept']
    result = __salt__['cmd.run_all'](cmd,
                                     output_loglevel='trace',
                                     python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result['retcode'] != 0:
        raise CommandExecutionError(
            'Problem encountered upgrading packages',
            info={'changes': ret,
                  'retcode': ips_pkg_return_values[result['retcode']],
                  'result': result}
        )

    return ret


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the currently installed packages as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    # not yet implemented or not applicable
    if any([salt.utils.data.is_true(kwargs.get(x))
        for x in ('removed', 'purge_desired')]):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    ret = {}
    cmd = '/bin/pkg list -Hv'
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    # column 1 is full FMRI name in form pkg://publisher/class/name@version
    for line in lines:
        name = _ips_get_pkgname(line)
        version = _ips_get_pkgversion(line)
        __salt__['pkg_resource.add_pkg'](ret, name, version)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def version(*names, **kwargs):
    '''
    Common interface for obtaining the version of installed packages.
    Accepts full or partial FMRI. If called using pkg_resource, full FMRI is required.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version vim
        salt '*' pkg.version foo bar baz
        salt '*' pkg_resource.version pkg://solaris/entire

    '''
    if names:
        cmd = ['/bin/pkg', 'list', '-Hv']
        cmd.extend(names)
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
    In case of multiple matches, it returns list of all matched packages.
    Accepts full or partial FMRI.
    Please use pkg.latest_version as pkg.available_version is being deprecated.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version pkg://solaris/entire
    '''
    cmd = ['/bin/pkg', 'list', '-Hnv', name]
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    ret = {}
    for line in lines:
        ret[_ips_get_pkgname(line)] = _ips_get_pkgversion(line)
    if ret:
        return ret
    return ''

# available_version is being deprecated
available_version = salt.utils.functools.alias_function(latest_version, 'available_version')


def get_fmri(name, **kwargs):
    '''
    Returns FMRI from partial name. Returns empty string ('') if not found.
    In case of multiple match, the function returns list of all matched packages.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_fmri bash
    '''
    if name.startswith('pkg://'):
        # already full fmri
        return name
    cmd = ['/bin/pkg', 'list', '-aHv', name]
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
    Internal function. Normalizes pkg name to full FMRI before running
    pkg.install. In case of multiple matches or no match, it returns the name
    without modifications.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.normalize_name vim
    '''
    if name.startswith('pkg://'):
        # already full fmri
        return name
    cmd = ['/bin/pkg', 'list', '-aHv', name]
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

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.is_installed bash
    '''

    cmd = ['/bin/pkg', 'list', '-Hv', name]
    return __salt__['cmd.retcode'](cmd) == 0


def search(name, versions_as_list=False, **kwargs):
    '''
    Searches the repository for given pkg name.
    The name can be full or partial FMRI. All matches are printed. Globs are
    also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.search bash
    '''

    ret = {}
    cmd = ['/bin/pkg', 'list', '-aHv', name]
    out = __salt__['cmd.run_all'](cmd, ignore_retcode=True)
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


    CLI Example:

    .. code-block:: bash

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
                pkg2inst += '{0}@{1} '.format(list(pkg.items())[0][0],
                                              list(pkg.items())[0][1])
            else:
                pkg2inst += '{0} '.format(list(pkg.items())[0][0])
        log.debug('Installing these packages instead of %s: %s',
                  name, pkg2inst)

    else:   # install single package
        if version:
            pkg2inst = "{0}@{1}".format(name, version)
        else:
            pkg2inst = "{0}".format(name)

    cmd = ['pkg', 'install', '-v', '--accept']
    if test:
        cmd.append('-n')

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = list_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd.append(pkg2inst)

    out = __salt__['cmd.run_all'](cmd, output_loglevel='trace')

    # Get a list of the packages again, including newly installed ones.
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if out['retcode'] != 0:
        raise CommandExecutionError(
            'Error occurred installing package(s)',
            info={
                'changes': ret,
                'retcode': ips_pkg_return_values[out['retcode']],
                'errors': [out['stderr']]
            }
        )

    # No error occurred
    if test:
        return 'Test succeeded.'

    return ret


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

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove tcsh
        salt '*' pkg.remove pkg://solaris/shell/tcsh
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    targets = salt.utils.args.split_input(pkgs) if pkgs else [name]
    if not targets:
        return {}

    if pkgs:
        log.debug('Removing these packages instead of %s: %s', name, targets)

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Remove the package(s)
    cmd = ['/bin/pkg', 'uninstall', '-v'] + targets
    out = __salt__['cmd.run_all'](cmd, output_loglevel='trace')

    # Get a list of the packages after the uninstall
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if out['retcode'] != 0:
        raise CommandExecutionError(
            'Error occurred removing package(s)',
            info={
                'changes': ret,
                'retcode': ips_pkg_return_values[out['retcode']],
                'errors': [out['stderr']]
            }
        )

    return ret


def purge(name, **kwargs):
    '''
    Remove specified package. Accepts full or partial FMRI.

    Returns a list containing the removed packages.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
    '''
    return remove(name, **kwargs)

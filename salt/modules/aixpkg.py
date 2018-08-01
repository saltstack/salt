# -*- coding: utf-8 -*-
'''
Package support for AIX

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging
import itertools


# Import salt libs
import salt.utils.data
import salt.utils.functools
import salt.utils.path
import salt.utils.pkg
from salt.exceptions import CommandExecutionError
from salt.ext import six
from salt.ext.six.moves import zip  # pylint: disable=redefined-builtin
from functools import reduce

import pudb

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is Solaris
    '''
    if __grains__['os_family'] == 'AIX':
        return __virtualname__
    return (False,
            'The aixpkg execution module failed to load.')

### TBD DGM need to go through and remove use of 'pkg://' and replace with AIX requivalent

aix_pkg_return_values = {
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


def _aix_get_pkgname(line):
    '''
    Extracts package name from "pkg list -v" output.
    Input: one line of the command output
    Output: pkg name (e.g.: "pkg://aix/x11/library/toolkit/libxt")
    Example use:
    line = "pkg://aix/x11/library/toolkit/libxt@1.1.3,5.11-0.175.1.0.0.24.1317:20120904T180030Z i--"
    name = _aix_get_pkgname(line)
    '''
    return line.split()[0].split('@')[0].strip()


def _aix_get_pkgversion(line):
    '''
    Extracts package version from "pkg list -v" output.
    Input: one line of the command output
    Output: package version (e.g.: "1.1.3,5.11-0.175.1.0.0.24.1317:20120904T180030Z")
    Example use:
    line = "pkg://aix/xlsmp.aix61.rte"
    name = _aix_get_pkgversion(line)
    '''
    return line.split()[0].split('@')[1].strip()


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the filesets or rpm packages currently installed as a dict:

    .. code-block:: python

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    ret = {}
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any([salt.utils.data.is_true(kwargs.get(x))
            for x in ('removed', 'purge_desired')]):
        return ret

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(
                __context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    # cmd returns information colon delimited in a single linei, format
    #   Package Name:Fileset:Level:State:PTF Id:Fix State:Type:Description:Destination Dir.:Uninstaller: \
    #       Message Catalog:Message Set:Message Number:Parent:Automatic:EFIX Locked:Install Path:Build Date
    # Example:
    #   xcursor:xcursor-1.1.7-3:1.1.7-3: : :C:R:X Cursor library: :/bin/rpm -e xcursor: : : : :0: :(none):Mon May  8 15:18:35 CDT 2017
    #   bos:bos.rte.libcur:7.1.5.0: : :C:F:libcurses Library: : : : : : :0:0:/:1731
    #
    # where Type codes: F -- Installp Fileset, P -- Product, C -- Component, T -- Feature, R -- RPM Package

    cmd = '/usr/bin/lslpp -Lc'
    lines = __salt__['cmd.run'](
            cmd,
            python_shell=False).splitlines()

    for line in lines:
        if line.startswith('#'):
            continue

        comps = line.split(':')
        if  len(comps) < 7:
            continue

        if 'R' in comps[6]:
            name = comps[0]
        else:
            name = comps[1]     # use fileset rather than package name

        version_num = comps[2]
        __salt__['pkg_resource.add_pkg'](
            ret,
            name,
            version_num)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)

    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)

    return ret


def version(*names, **kwargs):
    '''
    Common interface for obtaining the version of installed filesets or rpm packages.
    Accepts full or partial FMRI. If called using pkg_resource, full FMRI is required.
    Partial FMRI is returned if the fileset or rpm package is not installed.   TBD DGM check this statement

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version vim
        salt '*' pkg.version foo bar baz
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def is_installed(name, **kwargs):
    '''
    Returns True if the fileset or rpm package is installed. Otherwise returns False.
    Name can be full or partial FMRI.
    In case of multiple match from partial FMRI name, it returns True.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.is_installed bash
    '''
    cmd = ['/usr/bin/lslpp', '-Lc', name]
    return __salt__['cmd.retcode'](cmd) == 0


def install(name=None, refresh=False, pkgs=None, version=None, test=False, **kwargs):
    '''
    Install the named package using the installp command.
    Accepts full or partial FMRI.

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    ### TBD DGM need to allow for rpm or IBM's bff or rte filesets and
    need to distinguish between rpms and filesets when using commands
    since some commands only work for filesets, e.g. lslpp -l bash


    Multiple Package Installation Options:

    pkgs
        A list of packages to install. Must be passed as a python list.


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install vim
        salt '*' pkg.install /stage/middleware/AIX/bash-4.2-3.aix6.1.ppc.rpm
        salt '*' pkg.install /stage/middleware/AIX/bash-4.2-3.aix6.1.ppc.rpm refresh=True
        salt '*' pkg.install /stage/middleware/AIX/VIOS2211_update/tpc_4.1.1.85.bff
        salt '*' pkg.install /stage/middleware/AIX/Xlfv13.1/urt/xlC.rte
        salt '*' pkg.install pkgs='["foo", "bar"]'
    '''
    pu.db

### TBD DGM need to allow for rpm's - rpm -Uivh <name> if endswith('.rpm')

    if not pkgs:
        if is_installed(name):
            return {}

###    if refresh:
###        refresh_db(full=True)

    pkg2insts = ''
    if pkgs:    # multiple packages specified
        for pkg in pkgs:
            if list(pkg.items())[0][1]:   # version specified
###                pkg2inst += '{0}@{1} '.format(list(pkg.items())[0][0],
###                                              list(pkg.items())[0][1])
                pkg2insts += '{0} {1} '.format(os.path.dirname(list(pkg.items())[0][0])
                                            , os.path.basename(list(pkg.items())[0][0]))
                pkg2insts += os.linesep
            else:
###                pkg2inst += '{0} '.format(list(pkg.items())[0][0])
                pkg2insts += '{0} {1}'.format(os.path.dirname(list(pkg.items())[0][0])
                                            , os.path.basename(list(pkg.items())[0][0]))
                pkg2insts += os.linesep
        log.debug('Installing these packages instead of %s: %s',
                  name, pkg2insts)

    else:   # install single package
###        if version:
### TBD DGM what to do about versions            pkg2inst = "{0}@{1}".format(name, version)
###            pkg2inst = "{0}@{1}".format(name, version)
###        else:
###            pkg2inst = "{0}".format(name)
        pkg2insts = "{0} {1}".format(os.path.dirname(name), os.path.basename(name))

    cmd = ['/usr/bin/installp', '-avYXg -d', '']
###    if test:
###        cmd.append('-n')

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = list_pkgs()

    # Install or upgrade the package
    # If package is already installed
    for pkg2inst in pkg2insts:
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
                'retcode': aix_pkg_return_values[out['retcode']],
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
        salt '*' pkg.remove /stage/middleware/AIX/Xlfv13.1/urt/xlC.rte
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    pu.db

### TBD DGM need to allow for rpm's - rpm -Uivh <name> if endswith('.rpm')

    targets = salt.utils.args.split_input(pkgs) if pkgs else [name]
    if not targets:
        return {}

    if pkgs:
        log.debug('Removing these packages instead of %s: %s', name, targets)

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Remove the package(s)
    cmd = ['/usr/bin/installp', '-u'] + targets
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
                'retcode': aix_pkg_return_values[out['retcode']],
                'errors': [out['stderr']]
            }
        )

    return ret

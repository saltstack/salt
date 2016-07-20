# -*- coding: utf-8 -*-
'''
Package support for Solaris

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import

# Import python libs
import copy
import os
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, MinionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is Solaris
    '''
    if __grains__['os'] == 'Solaris' and float(__grains__['kernelrelease']) <= 5.10:
        return __virtualname__
    return False


def _write_adminfile(kwargs):
    '''
    Create a temporary adminfile based on the keyword arguments passed to
    pkg.install.
    '''
    # Set the adminfile default variables
    email = kwargs.get('email', '')
    instance = kwargs.get('instance', 'quit')
    partial = kwargs.get('partial', 'nocheck')
    runlevel = kwargs.get('runlevel', 'nocheck')
    idepend = kwargs.get('idepend', 'nocheck')
    rdepend = kwargs.get('rdepend', 'nocheck')
    space = kwargs.get('space', 'nocheck')
    setuid = kwargs.get('setuid', 'nocheck')
    conflict = kwargs.get('conflict', 'nocheck')
    action = kwargs.get('action', 'nocheck')
    basedir = kwargs.get('basedir', 'default')

    # Make tempfile to hold the adminfile contents.
    fd_, adminfile = salt.utils.mkstemp(prefix="salt-", close_fd=False)

    # Write to file then close it.
    os.write(fd_, 'email={0}\n'.format(email))
    os.write(fd_, 'instance={0}\n'.format(instance))
    os.write(fd_, 'partial={0}\n'.format(partial))
    os.write(fd_, 'runlevel={0}\n'.format(runlevel))
    os.write(fd_, 'idepend={0}\n'.format(idepend))
    os.write(fd_, 'rdepend={0}\n'.format(rdepend))
    os.write(fd_, 'space={0}\n'.format(space))
    os.write(fd_, 'setuid={0}\n'.format(setuid))
    os.write(fd_, 'conflict={0}\n'.format(conflict))
    os.write(fd_, 'action={0}\n'.format(action))
    os.write(fd_, 'basedir={0}\n'.format(basedir))
    os.close(fd_)

    return adminfile


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any([salt.utils.is_true(kwargs.get(x))
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
    cmd = '/usr/bin/pkginfo -x'

    # Package information returned two lines per package. On even-offset
    # lines, the package name is in the first column. On odd-offset lines, the
    # package version is in the second column.
    lines = __salt__['cmd.run'](
            cmd,
            output_loglevel='trace',
            python_shell=False).splitlines()
    for index, line in enumerate(lines):
        if index % 2 == 0:
            name = line.split()[0].strip()
        if index % 2 == 1:
            version_num = line.split()[1].strip()
            __salt__['pkg_resource.add_pkg'](ret, name, version_num)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...

    NOTE: As package repositories are not presently supported for Solaris
    pkgadd, this function will always return an empty string for a given
    package.
    '''
    kwargs.pop('refresh', True)

    ret = {}
    if not names:
        return ''
    for name in names:
        ret[name] = ''

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def install(name=None, sources=None, saltenv='base', **kwargs):
    '''
    Install the passed package. Can install packages from the following
    sources::

        * Locally (package already exists on the minion
        * HTTP/HTTPS server
        * FTP server
        * Salt master

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example, installing a data stream pkg that already exists on the
    minion::

        salt '*' pkg.install sources='[{"<pkg name>": "/dir/on/minion/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    CLI Example, installing a data stream pkg that exists on the salt master::

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "salt://pkgs/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    CLI Example, installing a data stream pkg that exists on a HTTP server::

        salt '*' pkg.install sources='[{"<pkg name>": "http://packages.server.com/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "http://packages.server.com/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    If working with solaris zones and you want to install a package only in the
    global zone you can pass 'current_zone_only=True' to salt to have the
    package only installed in the global zone. (Behind the scenes this is
    passing '-G' to the pkgadd command.) Solaris default when installing a
    package in the global zone is to install it in all zones. This overrides
    that and installs the package only in the global.

    CLI Example, installing a data stream package only in the global zone::

        salt 'global_zone' pkg.install sources='[{"SMClgcc346": "/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg"}]' current_zone_only=True

    By default salt automatically provides an adminfile, to automate package
    installation, with these options set::

        email=
        instance=quit
        partial=nocheck
        runlevel=nocheck
        idepend=nocheck
        rdepend=nocheck
        space=nocheck
        setuid=nocheck
        conflict=nocheck
        action=nocheck
        basedir=default

    You can override any of these options in two ways. First you can optionally
    pass any of the options as a kwarg to the module/state to override the
    default value or you can optionally pass the 'admin_source' option
    providing your own adminfile to the minions.

    Note: You can find all of the possible options to provide to the adminfile
    by reading the admin man page::

        man -s 4 admin

    CLI Example - Overriding the 'instance' adminfile option when calling the
    module directly::

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]' instance="overwrite"

    CLI Example - Overriding the 'instance' adminfile option when used in a
    state::

        SMClgcc346:
          pkg.installed:
            - sources:
              - SMClgcc346: salt://srv/salt/pkgs/gcc-3.4.6-sol10-sparc-local.pkg
            - instance: overwrite

    Note: the ID declaration is ignored, as the package name is read from the
    "sources" parameter.

    CLI Example - Providing your own adminfile when calling the module
    directly::

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]' admin_source='salt://pkgs/<adminfile filename>'

    CLI Example - Providing your own adminfile when using states::

        <pkg name>:
          pkg.installed:
            - sources:
              - <pkg name>: salt://pkgs/<pkg filename>
            - admin_source: salt://pkgs/<adminfile filename>

    Note: the ID declaration is ignored, as the package name is read from the
    "sources" parameter.
    '''
    if salt.utils.is_true(kwargs.get('refresh')):
        log.warning('\'refresh\' argument not implemented for solarispkg '
                    'module')

    # pkgs is not supported, but must be passed here for API compatibility
    pkgs = kwargs.pop('pkgs', None)
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    if not sources:
        log.error('"sources" param required for solaris pkg_add installs')
        return {}

    if 'admin_source' in kwargs:
        adminfile = __salt__['cp.cache_file'](kwargs['admin_source'], saltenv)
    else:
        adminfile = _write_adminfile(kwargs)

    old = list_pkgs()
    cmd = '/usr/sbin/pkgadd -n -a {0} '.format(adminfile)

    # Only makes sense in a global zone but works fine in non-globals.
    if kwargs.get('current_zone_only') == 'True':
        cmd += '-G '

    for pkg in pkg_params:
        temp_cmd = cmd + '-d {0} "all"'.format(pkg)
        # Install the package{s}
        __salt__['cmd.run'](
                temp_cmd,
                python_shell=False,
                output_loglevel='trace')

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()

    # Remove the temp adminfile
    if 'admin_source' not in kwargs:
        os.unlink(adminfile)

    return salt.utils.compare_dicts(old, new)


def remove(name=None, pkgs=None, saltenv='base', **kwargs):
    '''
    Remove packages with pkgrm

    name
        The name of the package to be deleted

    By default salt automatically provides an adminfile, to automate package
    removal, with these options set::

        email=
        instance=quit
        partial=nocheck
        runlevel=nocheck
        idepend=nocheck
        rdepend=nocheck
        space=nocheck
        setuid=nocheck
        conflict=nocheck
        action=nocheck
        basedir=default

    You can override any of these options in two ways. First you can optionally
    pass any of the options as a kwarg to the module/state to override the
    default value or you can optionally pass the 'admin_source' option
    providing your own adminfile to the minions.

    Note: You can find all of the possible options to provide to the adminfile
    by reading the admin man page:

    .. code-block:: bash

        man -s 4 admin


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove SUNWgit
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    if 'admin_source' in kwargs:
        adminfile = __salt__['cp.cache_file'](kwargs['admin_source'], saltenv)
    else:
        # Set the adminfile default variables
        email = kwargs.get('email', '')
        instance = kwargs.get('instance', 'quit')
        partial = kwargs.get('partial', 'nocheck')
        runlevel = kwargs.get('runlevel', 'nocheck')
        idepend = kwargs.get('idepend', 'nocheck')
        rdepend = kwargs.get('rdepend', 'nocheck')
        space = kwargs.get('space', 'nocheck')
        setuid = kwargs.get('setuid', 'nocheck')
        conflict = kwargs.get('conflict', 'nocheck')
        action = kwargs.get('action', 'nocheck')
        basedir = kwargs.get('basedir', 'default')

        # Make tempfile to hold the adminfile contents.
        fd_, adminfile = salt.utils.mkstemp(prefix="salt-", close_fd=False)

        # Write to file then close it.
        os.write(fd_, 'email={0}\n'.format(email))
        os.write(fd_, 'instance={0}\n'.format(instance))
        os.write(fd_, 'partial={0}\n'.format(partial))
        os.write(fd_, 'runlevel={0}\n'.format(runlevel))
        os.write(fd_, 'idepend={0}\n'.format(idepend))
        os.write(fd_, 'rdepend={0}\n'.format(rdepend))
        os.write(fd_, 'space={0}\n'.format(space))
        os.write(fd_, 'setuid={0}\n'.format(setuid))
        os.write(fd_, 'conflict={0}\n'.format(conflict))
        os.write(fd_, 'action={0}\n'.format(action))
        os.write(fd_, 'basedir={0}\n'.format(basedir))
        os.close(fd_)

    # Remove the package
    cmd = '/usr/sbin/pkgrm -n -a {0} {1}'.format(adminfile,
                                                 ' '.join(targets))
    __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='trace')
    # Remove the temp adminfile
    if 'admin_source' not in kwargs:
        os.unlink(adminfile)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported, this function is identical to
    ``remove()``.

    name
        The name of the package to be deleted


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs, **kwargs)

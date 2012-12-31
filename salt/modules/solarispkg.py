'''
Package support for Solaris
'''

# Import python libs
import os
import logging

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is Solaris
    '''
    if __grains__['os'] == 'Solaris':
        return 'pkg'
    return False


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


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


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    pkg = {}
    cmd = '/usr/bin/pkginfo -x'

    line_count = 0
    for line in __salt__['cmd.run'](cmd).splitlines():
        if line_count % 2 == 0:
            namever = line.split()[0].strip()
        if line_count % 2 == 1:
            pkg[namever] = line.split()[1].strip()
        line_count = line_count + 1
    return pkg


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    cmd = '/usr/bin/pkgparam {0} VERSION 2> /dev/null'.format(name)
    namever = __salt__['cmd.run'](cmd)
    if namever:
        return namever
    return ''


def available_version(name):
    '''
    The available version of the package in the repository On Solaris with the
    pkg module this always returns the version that is installed since pkgadd
    does not have the concept of a repository.

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    return version(name)


def install(name=None, refresh=False, sources=None, **kwargs):
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

    CLI Example, installing a datastream pkg that already exists on the
    minion::

        salt '*' pkg.install sources='[{"<pkg name>": "/dir/on/minion/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    CLI Example, installing a datastream pkg that exists on the salt master::

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "salt://pkgs/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    CLI Example, installing a datastream pkg that exists on a HTTP server::

        salt '*' pkg.install sources='[{"<pkg name>": "http://packages.server.com/<pkg filename>"}]'
        salt '*' pkg.install sources='[{"SMClgcc346": "http://packages.server.com/gcc-3.4.6-sol10-sparc-local.pkg"}]'

    If working with solaris zones and you want to install a package only in the
    global zone you can pass 'current_zone_only=True' to salt to have the
    package only installed in the global zone. (Behind the scenes this is
    passing '-G' to the pkgadd command.) Solaris default when installing a
    package in the global zone is to install it in all zones. This overrides
    that and installs the package only in the global.

    CLI Example, installing a datastream package only in the global zone::

        salt 'global_zone' pkg.install sources='[{"SMClgcc346": "/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg"}]' current_zone_only=True

    By default salt automatically provides an adminfile, to automate package
    installation, with these options set:

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

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, kwargs.get('pkgs'), sources)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    if 'admin_source' in kwargs:
        adminfile = __salt__['cp.cache_file'](kwargs['admin_source'])
    else:
        adminfile = _write_adminfile(kwargs)

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = list_pkgs()

    cmd = '/usr/sbin/pkgadd -n -a {0} '.format(adminfile)

    # Only makes sense in a global zone but works fine in non-globals.
    if kwargs.get('current_zone_only') == 'True':
        cmd += '-G '

    for pkg in pkg_params:
        temp_cmd = cmd + '-d {0} "all"'.format(pkg)
        # Install the package{s}
        stderr = __salt__['cmd.run_all'](temp_cmd).get('stderr', '')
        if stderr:
            log.error(stderr)

    # Get a list of the packages again, including newly installed ones.
    new = list_pkgs()

    # Remove the temp adminfile
    if not 'admin_source' in kwargs:
        os.unlink(adminfile)

    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name, **kwargs):
    '''
    Remove a single package with pkgrm

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
    by reading the admin man page::

        man -s 4 admin

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove SUNWgit
    '''

    # Check to see if the package is installed before we proceed
    if version(name) == '':
        return ''

    if 'admin_source' in kwargs:
        adminfile = __salt__['cp.cache_file'](kwargs['admin_source'])
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

    # Get a list of the currently installed pkgs.
    old = list_pkgs()

    # Remove the package
    cmd = '/usr/sbin/pkgrm -n -a {0} {1}'.format(adminfile, name)
    __salt__['cmd.retcode'](cmd)

    # Remove the temp adminfile
    if not 'admin_source' in kwargs:
        os.unlink(adminfile)

    # Get a list of the packages after the uninstall
    new = list_pkgs()

    # Compare the pre and post remove package objects and report the
    # uninstalled pkgs.
    return _list_removed(old, new)


def purge(name, **kwargs):
    '''
    Remove a single package with pkgrm

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(name, **kwargs)

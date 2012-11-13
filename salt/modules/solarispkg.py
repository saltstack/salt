'''
Package support for Solaris
'''

# Import python libs
import os

# Import salt libs
import salt.utils


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


def _compare_versions(old, new):
    '''
    Returns a dict that that displays old and new versions for a package after
    install/upgrade of package.
    '''
    pkgs = {}
    for npkg in new:
        if npkg in old:
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    return pkgs


def _get_pkgs():
    '''
    Get a full list of the package installed on the machine
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


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    return _get_pkgs()


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


def install(name, refresh=False, **kwargs):
    '''
    Install the passed package. Can install packages from the following
    sources::

        * Locally (package already exists on the minion
        * HTTP/HTTPS server
        * FTP server
        * Salt master

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example, installing a datastream pkg that already exists on the
    minion::

        salt '*' pkg.install <package name once installed> source=/dir/on/minion/<package filename>
        salt '*' pkg.install SMClgcc346 source=/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg

    CLI Example, installing a datastream pkg that exists on the salt master::

        salt '*' pkg.install <package name once installed> source='salt://srv/salt/pkgs/<package filename>'
        salt '*' pkg.install SMClgcc346 source='salt://srv/salt/pkgs/gcc-3.4.6-sol10-sparc-local.pkg'

    CLI Example, installing a datastream pkg that exists on a HTTP server::

        salt '*' pkg.install <package name once installed> source='http://packages.server.com/<package filename>'
        salt '*' pkg.install SMClgcc346 source='http://packages.server.com/gcc-3.4.6-sol10-sparc-local.pkg'

    If working with solaris zones and you want to install a package only in the
    global zone you can pass 'current_zone_only=True' to salt to have the
    package only installed in the global zone. (Behind the scenes this is
    passing '-G' to the pkgadd command.) Solaris default when installing a
    package in the global zone is to install it in all zones. This overrides
    that and installs the package only in the global.

    CLI Example, installing a datastream package only in the global zone::

        salt 'global_zone' pkg.install SMClgcc346 source=/var/spool/pkg/gcc-3.4.6-sol10-sparc-local.pkg current_zone_only=True

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

        salt '*' pkg.install <package name once installed> source='salt://srv/salt/pkgs/<package filename>' instance="overwrite"

    CLI Example - Overriding the 'instance' adminfile option when used in a
    state::

        SMClgcc346:
          pkg.installed:
            - source: salt://srv/salt/pkgs/gcc-3.4.6-sol10-sparc-local.pkg
            - instance: overwrite

    CLI Example - Providing your own adminfile when calling the module
    directly::

        salt '*' pkg.install <package name once installed> source='salt://srv/salt/pkgs/<package filename>' admin_source='salt://srv/salt/pkgs/<adminfile filename>'

    CLI Example - Providing your own adminfile when using states::

        <package name once installed>:
          pkg.installed:
            - source: salt://srv/salt/pkgs/<package filename>
            - admin_source: salt://srv/salt/pkgs/<adminfile filename>
    '''

    if not 'source' in kwargs:
        return 'source option required with solaris pkg installs'
    else:
        if (kwargs['source']).startswith('salt://') \
                or (kwargs['source']).startswith('http://') \
                or (kwargs['source']).startswith('https://') \
                or (kwargs['source']).startswith('ftp://'):
            pkgname = __salt__['cp.cache_file'](kwargs['source'])
        else:
            pkgname = (kwargs['source'])

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
        fd, adminfile = salt.utils.mkstemp(prefix="salt-", close_fd=False)

        # Write to file then close it.
        os.write(fd, 'email={0}\n'.format(email))
        os.write(fd, 'email={instance={0}\n'.format(instance))
        os.write(fd, 'email={partial={0}\n'.format(partial))
        os.write(fd, 'email={runlevel={0}\n'.format(runlevel))
        os.write(fd, 'email={idepend={0}\n'.format(idepend))
        os.write(fd, 'email={rdepend={0}\n'.format(rdepend))
        os.write(fd, 'email={space={0}\n'.format(space))
        os.write(fd, 'email={setuid={0}\n'.format(setuid))
        os.write(fd, 'email={conflict={0}\n'.format(conflict))
        os.write(fd, 'email={action={0}\n'.format(action))
        os.write(fd, 'email={basedir={0}\n'.format(basedir))
        os.close(fd)

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = _get_pkgs()

    cmd = '/usr/sbin/pkgadd -n -a {0} '.format(adminfile)

    # Global only?
    if kwargs.get('current_zone_only') == 'True':
        cmd += '-G '

    cmd += '-d {0} \'all\''.format(pkgname)

    # Install the package
    __salt__['cmd.retcode'](cmd)

    # Get a list of the packages again, including newly installed ones.
    new = _get_pkgs()

    # Remove the temp adminfile
    if not 'admin_source' in kwargs:
        os.unlink(adminfile)

    # Return a list of the new package installed.
    return _compare_versions(old, new)


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
        fd, adminfile = salt.utils.mkstemp(prefix="salt-")

        # Write to file then close it.
        os.write(fd, 'email={0}\n'.format(email))
        os.write(fd, 'instance={0}\n'.format(instance))
        os.write(fd, 'partial={0}\n'.format(partial))
        os.write(fd, 'runlevel={0}\n'.format(runlevel))
        os.write(fd, 'idepend={0}\n'.format(idepend))
        os.write(fd, 'rdepend={0}\n'.format(rdepend))
        os.write(fd, 'space={0}\n'.format(space))
        os.write(fd, 'setuid={0}\n'.format(setuid))
        os.write(fd, 'conflict={0}\n'.format(conflict))
        os.write(fd, 'action={0}\n'.format(action))
        os.write(fd, 'basedir={0}\n'.format(basedir))
        os.close(fd)

    # Get a list of the currently installed pkgs.
    old = _get_pkgs()

    # Remove the package
    cmd = '/usr/sbin/pkgrm -n -a {0} {1}'.format(adminfile, name)
    __salt__['cmd.retcode'](cmd)

    # Remove the temp adminfile
    if not 'admin_source' in kwargs:
        os.unlink(adminfile)

    # Get a list of the packages after the uninstall
    new = _get_pkgs()

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

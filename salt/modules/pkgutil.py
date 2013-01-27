'''
Pkgutil support for Solaris
'''


def __virtual__():
    '''
    Set the virtual pkg module if the os is Solaris
    '''
    if __grains__['os'] == 'Solaris':
        return 'pkgutil'
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


def refresh_db():
    '''
    Updates the pkgutil repo database (pkgutil -U)

    CLI Example::

        salt '*' pkgutil.refresh_db
    '''
    return __salt__['cmd.retcode']('/opt/csw/bin/pkgutil -U > /dev/null 2>&1') == 0


def upgrade_available(name):
    '''
    Check if there is an upgrade available for a certain package

    CLI Example::

        salt '*' pkgutil.upgrade_available CSWpython
    '''
    version = None
    cmd = '/opt/csw/bin/pkgutil -c --parse --single {0} 2>/dev/null'.format(
        name)
    out = __salt__['cmd.run_stdout'](cmd)
    if out:
        version = out.split()[2].strip()
    if version:
        if version == "SAME":
            return ''
        else:
            return version
    return ''


def list_upgrades(refresh=True):
    '''
    List all available package upgrades on this system

    CLI Example::

        salt '*' pkgutil.list_upgrades
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()
    upgrades = {}
    lines = __salt__['cmd.run_stdout'](
        '/opt/csw/bin/pkgutil -A --parse').splitlines()
    for line in lines:
        comps = line.split('\t')
        if comps[2] == "SAME":
            continue
        if comps[2] == "not installed":
            continue
        upgrades[comps[0]] = comps[1]
    return upgrades


def upgrade(refresh=True, **kwargs):
    '''
    Upgrade all of the packages to the latest available version.

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkgutil.upgrade
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = _get_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd = '/opt/csw/bin/pkgutil -yu'
    __salt__['cmd.run'](cmd)

    # Get a list of the packages again, including newly installed ones.
    new = _get_pkgs()

    # Return a list of the new package installed.
    return __salt__['pkg_resource.find_changes'](old, new)


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkgutil.list_pkgs
    '''
    return _get_pkgs()


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkgutil.version CSWpython
    '''
    cmd = '/usr/bin/pkgparam {0} VERSION 2> /dev/null'.format(name)
    namever = __salt__['cmd.run'](cmd)
    if namever:
        return namever
    return ''


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkgutil.available_version CSWpython
    '''
    cmd = '/opt/csw/bin/pkgutil -a --parse {0}'.format(name)
    namever = __salt__['cmd.run_stdout'](cmd).split()[2].strip()
    if namever:
        return namever
    return ''


def install(name, refresh=False, version=None, **kwargs):
    '''
    Install the named package using the pkgutil tool.

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkgutil.install <package_name>
        salt '*' pkgutil.install SMClgcc346
    '''

    if refresh:
        refresh_db()

    if version:
        pkg = "{0}-{1}".format(name, version)
    else:
        pkg = "{0}".format(name)

    cmd = '/opt/csw/bin/pkgutil -yu '

    # Get a list of the packages before install so we can diff after to see
    # what got installed.
    old = _get_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd += '{0}'.format(pkg)
    __salt__['cmd.run'](cmd)

    # Get a list of the packages again, including newly installed ones.
    new = _get_pkgs()

    # Return a list of the new package installed.
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name, **kwargs):
    '''
    Remove a package and all its dependencies which are not in use by other
    packages.

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkgutil.remove <package name>
        salt '*' pkgutil.remove SMCliconv
    '''

    # Check to see if the package is installed before we proceed
    if version(name) == '':
        return ''

    # Get a list of the currently installed pkgs.
    old = _get_pkgs()

    # Remove the package
    cmd = '/opt/csw/bin/pkgutil -yr {0}'.format(name)
    __salt__['cmd.run'](cmd)

    # Get a list of the packages after the uninstall
    new = _get_pkgs()

    # Compare the pre and post remove package objects and report the uninstalled pkgs.
    return _list_removed(old, new)


def purge(name, **kwargs):
    '''
    Remove a package and all its dependencies which are not in use by other
    packages.

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkgutil.purge <package name>
    '''
    return remove(name, **kwargs)


def perform_cmp(pkg1='', pkg2=''):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example::

        salt '*' pkg.perform_cmp '0.2.4-0' '0.2.4.1-0'
        salt '*' pkg.perform_cmp pkg1='0.2.4-0' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.perform_cmp'](pkg1=pkg1, pkg2=pkg2)


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Compare two version strings.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '<' '0.2.4.1-0'
        salt '*' pkg.compare pkg1='0.2.4-0' oper='<' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](pkg1=pkg1, oper=oper, pkg2=pkg2)

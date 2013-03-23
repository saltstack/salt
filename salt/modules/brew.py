'''
Homebrew for Mac OS X
'''

# Import salt libs
import salt


def __virtual__():
    '''
    Confine this module to Mac OS with Homebrew.
    '''

    if salt.utils.which('brew') and __grains__['os'] == 'MacOS':
        return 'pkg'
    return False


def list_pkgs(versions_as_list=False):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = __salt__['config.is_true'](versions_as_list)
    ret = {}
    cmd = 'brew list --versions {0}'.format(' '.join(args))
    for line in __salt__['cmd.run'](cmd).splitlines():
        try:
            name, version = line.split(' ')[0:2]
        except ValueError:
            continue
        __salt__['pkg_resource.add_pkg'](ret, name, version)

    __salt__['pkg_resource.sort_pkglist'](ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3>
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation

    Note that this currently not fully implemented but needs to return
    something to avoid a traceback when calling pkg.latest.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3>
    '''
    if len(names) <= 1:
        return ''
    else:
        ret = {}
        for name in names:
            ret[name] = ''
        return ret

# available_version is being deprecated
available_version = latest_version


def remove(pkgs, **kwargs):
    '''
    Removes packages with ``brew uninstall``

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package,package,package>
    '''
    formulas = ' '.join(pkgs.split(','))
    cmd = 'brew uninstall {0}'.format(formulas)

    return __salt__['cmd.run'](cmd)


def install(name=None, pkgs=None, **kwargs):
    '''
    Install the passed package(s) with ``brew install``

    name
        The name of the formula to be installed. Note that this parameter is
        ignored if "pkgs" is passed.

        CLI Example::
            salt '*' pkg.install <package name>


    Multiple Package Installation Options:

    pkgs
        A list of formulas to install. Must be passed as a python list.

        CLI Example::
            salt '*' pkg.install pkgs='["foo","bar"]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.install 'package package package'
    '''
    pkg_params, pkg_type = \
        __salt__['pkg_resource.parse_targets'](name,
                                               pkgs,
                                               kwargs.get('sources', {}))
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    formulas = ' '.join(pkg_params)
    old = list_pkgs()
    homebrew_binary = __salt__['cmd.run']('brew --prefix') + "/bin/brew"
    user = __salt__['file.get_user'](homebrew_binary)
    cmd = 'brew install {0}'.format(formulas)
    if user != __opts__['user']:
        __salt__['cmd.run'](cmd, runas=user)
    else:
        __salt__['cmd.run'](cmd)

    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def list_upgrades():
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    cmd = 'brew outdated'

    return __salt__['cmd.run'](cmd).splitlines()


def upgrade_available(pkg):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return pkg in list_upgrades()


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

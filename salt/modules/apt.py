'''
Support for APT (Advanced Packaging Tool)
'''

# Import python libs
import os
import re
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__outputter__ = {
    'upgrade_available': 'txt',
    'available_version': 'txt',
    'list_upgrades': 'txt',
    'install': 'yaml',
}


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    return 'pkg' if __grains__['os_family'] == 'Debian' else False


def __init__(opts):
    '''
    For Debian and derivative systems, set up
    a few env variables to keep apt happy and
    non-interactive.
    '''
    if __virtual__():
        env_vars = {
            'APT_LISTBUGS_FRONTEND': 'none',
            'APT_LISTCHANGES_FRONTEND': 'none',
            'DEBIAN_FRONTEND': 'noninteractive',
        }
        # Export these puppies so they persist
        os.environ.update(env_vars)


def available_version(name):
    '''
    Return the latest version of the named package available for upgrade or
    installation via the available apt repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    version = ''
    cmd = 'apt-cache -q policy {0} | grep Candidate'.format(name)

    out = __salt__['cmd.run_stdout'](cmd)

    version_list = out.split()

    if len(version_list) >= 2:
        version = version_list[-1]

    return version


def version(name):
    '''
    Returns a string representing the package version or an empty string if not
    installed

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    pkgs = list_pkgs(name)
    # check for ':arch' appended to pkg name (i.e. 32 bit installed on 64 bit
    # machine is ':i386')
    if name.find(':') >= 0:
        name = name.split(':')[0]
    if name in pkgs:
        return pkgs[name]
    else:
        return ''


def refresh_db():
    '''
    Updates the APT database to latest packages based upon repositories

    Returns a dict::

        {'<database name>': Bool}

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    cmd = 'apt-get -q update'

    out = __salt__['cmd.run_stdout'](cmd)

    servers = {}
    for line in out:
        cols = line.split()
        if not len(cols):
            continue
        ident = ' '.join(cols[1:4])
        if 'Get' in cols[0]:
            servers[ident] = True
        else:
            servers[ident] = False

    return servers


def install(name=None, refresh=False, fromrepo=None, skip_verify=False,
            debconf=None, pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package, add refresh=True to update the dpkg database.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        CLI Example::
            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    fromrepo
        Specify a package repository to install from
        (e.g., ``apt-get -t unstable install somepackage``)

    skip_verify
        Skip the GPG verification check (e.g., ``--allow-unauthenticated``, or
        ``--force-bad-verify`` for install from package file).

    debconf
        Provide the path to a debconf answers file, processed before
        installation.

    version
        Install a specific version of the package, e.g. 1.0.9~ubuntu. Ignored
        if "pkgs" or "sources" is passed.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example::
            salt '*' pkg.install pkgs='["foo","bar"]'

    sources
        A list of DEB packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::
            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    # Note that this function will daemonize the subprocess
    # preventing a restart resulting from a salt-minion upgrade
    # from killing the apt and hence hosing the dpkg database
    salt.utils.daemonize_if(__opts__, **kwargs)

    if refresh:
        refresh_db()

    if debconf:
        __salt__['debconf.set_file'](debconf)

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources)

    # Support old "repo" argument
    repo = kwargs.get('repo','')
    if not fromrepo and repo:
        fromrepo = repo

    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        cmd = 'dpkg -i {verify} {pkg}'.format(
            verify='--force-bad-verify' if skip_verify else '',
            pkg=' '.join(pkg_params),
        )
    elif pkg_type == 'repository':
        fname = ' '.join(pkg_params)
        if len(pkg_params) == 1:
            for vkey, vsign in (('eq', '='), ('version', '=')):
                if kwargs.get(vkey) is not None:
                    fname = '"{0}{1}{2}"'.format(fname, vsign, kwargs[vkey])
                    break
        if fromrepo:
            log.info('Targeting repo "{0}"'.format(fromrepo))
        cmd = 'apt-get -q -y {confold} {confdef} {verify} {target} install ' \
              '{pkg}'.format(
            confold='-o DPkg::Options::=--force-confold',
            confdef='-o DPkg::Options::=--force-confdef',
            verify='--allow-unauthenticated' if skip_verify else '',
            target='-t {0}'.format(fromrepo) if fromrepo else '',
            pkg=fname,
        )

    old = list_pkgs()
    __salt__['cmd.run_all'](cmd).get('stderr', '')
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(pkg):
    '''
    Remove a single package via ``apt-get remove``

    Returns a list containing the names of the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    cmd = 'apt-get -q -y remove {0}'.format(pkg)
    __salt__['cmd.run'](cmd)
    new_pkgs = list_pkgs()
    for pkg in old_pkgs:
        if pkg not in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def purge(pkg):
    '''
    Remove a package via ``apt-get purge`` along with all configuration
    files and unused dependencies.

    Returns a list containing the names of the removed packages

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    # Remove inital package
    purge_cmd = 'apt-get -q -y purge {0}'.format(pkg)
    __salt__['cmd.run'](purge_cmd)

    new_pkgs = list_pkgs()

    for pkg in old_pkgs:
        if pkg not in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def upgrade(refresh=True, **kwargs):
    '''
    Upgrades all packages via ``apt-get dist-upgrade``

    Returns a list of dicts containing the package names, and the new and old
    versions::

        [
            {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>']
            }',
            ...
        ]

    CLI Example::

        salt '*' pkg.upgrade
    '''
    salt.utils.daemonize_if(__opts__, **kwargs)
    if refresh:
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'apt-get -q -y -o DPkg::Options::=--force-confold -o DPkg::Options::=--force-confdef dist-upgrade'
    __salt__['cmd.run'](cmd)
    new_pkgs = list_pkgs()

    for pkg in new_pkgs:
        if pkg in old_pkgs:
            if old_pkgs[pkg] == new_pkgs[pkg]:
                continue
            else:
                ret_pkgs[pkg] = {'old': old_pkgs[pkg],
                             'new': new_pkgs[pkg]}
        else:
            ret_pkgs[pkg] = {'old': '',
                         'new': new_pkgs[pkg]}

    return ret_pkgs


def list_pkgs(regex_string=''):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    External dependencies::

        Virtual package resolution requires aptitude.
        Without aptitude virtual packages will be reported as not installed.

    CLI Example::

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs httpd
    '''
    ret = {}
    cmd = (
        'dpkg-query --showformat=\'${{Status}} ${{Package}} ${{Version}}\n\' '
        '-W {0}'.format(
            regex_string
        )
    )

    out = __salt__['cmd.run_stdout'](cmd)

    # Typical line of output:
    # install ok installed zsh 4.3.17-1ubuntu1
    for line in out.splitlines():
        cols = line.split()
        if len(cols) and ('install' in cols[0] or 'hold' in cols[0]) and \
                                                        'installed' in cols[2]:
            __salt__['pkg_resource.add_pkg'](ret, cols[3], cols[4])

    # Check for virtual packages. We need aptitude for this.
    if __salt__['cmd.has_exec']('aptitude'):
        if not ret:
            search_string = regex_string
        else:
            search_string = '.+'
        cmd = 'aptitude search "?name(^{0}$) ?virtual ' \
              '?reverse-provides(?installed)"'.format(search_string)

        out = __salt__['cmd.run_stdout'](cmd)
        for line in out.splitlines():
            # Setting all matching 'installed' virtual package versions to 1
            try:
                name = line.split()[1]
            except IndexError:
                continue
            __salt__['pkg_resource.add_pkg'](ret, name, '1')

    __salt__['pkg_resource.sort_pkglist'](ret)
    return ret


def _get_upgradable():
    '''
    Utility function to get upgradable packages

    Sample return data:
    { 'pkgname': '1.2.3-45', ... }
    '''

    cmd = 'apt-get --just-print dist-upgrade'
    out = __salt__['cmd.run_stdout'](cmd)

    # rexp parses lines that look like the following:
    ## Conf libxfont1 (1:1.4.5-1 Debian:testing [i386])
    rexp = re.compile('(?m)^Conf '
                      '([^ ]+) '                # Package name
                      '\(([^ ]+) '              # Version
                      '([^ ]+)'                 # Release
                      '(?: \[([^\]]+)\])?\)$')  # Arch
    keys = ['name', 'version', 'release', 'arch']
    _get = lambda l, k: l[keys.index(k)]

    upgrades = rexp.findall(out)

    ret = {}
    for line in upgrades:
        name = _get(line, 'name')
        version = _get(line, 'version')
        ret[name] = version

    return ret


def list_upgrades():
    '''
    List all available package upgrades.

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    return _get_upgradable()


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return name in _get_upgradable()

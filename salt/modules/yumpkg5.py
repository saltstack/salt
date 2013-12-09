# -*- coding: utf-8 -*-
'''
Support for YUM
'''

# Import python libs
import collections
import copy
import logging
import os
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# This is imported in salt.modules.pkg_resource._parse_pkg_meta. Don't change
# it without considering its impact there.
__QUERYFORMAT = '%{NAME}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}'

# From rpmUtils.arch.getArchList() (not necessarily available on RHEL/CentOS 5)
__ALL_ARCHES = ('ia32e', 'x86_64', 'athlon', 'i686', 'i586', 'i486', 'i386',
                'noarch')
__SUFFIX_NOT_NEEDED = ('x86_64', 'noarch')

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    # Work only on RHEL/Fedora based distros with python 2.5 and below
    try:
        os_grain = __grains__['os'].lower()
        os_family = __grains__['os_family'].lower()
        os_major_version = int(__grains__['osrelease'].split('.')[0])
    except Exception:
        return False

    enabled = ('amazon', 'xcp', 'xenserver')

    if os_family == 'redhat' or os_grain in enabled:
        return __virtualname__
    return False


# This is imported in salt.modules.pkg_resource._parse_pkg_meta. Don't change
# it without considering its impact there.
def _parse_pkginfo(line):
    '''
    A small helper to parse package information; returns a namedtuple
    '''
    # Need to reimport `collections` as this function is re-namespaced into
    # other modules
    import collections

    pkginfo = collections.namedtuple('PkgInfo', ('name', 'shortname',
                                                 'version', 'arch'))

    try:
        name, pkgver, rel, arch = line.split('_|-')
    # Handle unpack errors (should never happen with the queryformat we are
    # using, but can't hurt to be careful).
    except ValueError:
        return None

    shortname = name
    # Support 32-bit packages on x86_64 systems
    if __grains__.get('cpuarch') in __SUFFIX_NOT_NEEDED \
            and arch not in __SUFFIX_NOT_NEEDED:
        name += '.{0}'.format(arch)
    if rel:
        pkgver += '-{0}'.format(rel)

    return pkginfo(name, shortname, pkgver, arch)


def _repoquery(repoquery_args):
    '''
    Runs a repoquery command and returns a list of namedtuples
    '''
    ret = []
    cmd = 'repoquery {0}'.format(repoquery_args)
    output = __salt__['cmd.run_all'](cmd).get('stdout', '').splitlines()
    for line in output:
        pkginfo = _parse_pkginfo(line)
        if pkginfo is not None:
            ret.append(pkginfo)
    return ret


def _get_repo_options(**kwargs):
    '''
    Returns a string of '--enablerepo' and '--disablerepo' options to be used
    in the yum command, based on the kwargs.
    '''
    # Get repo options from the kwargs
    fromrepo = kwargs.get('fromrepo', '')
    repo = kwargs.get('repo', '')
    disablerepo = kwargs.get('disablerepo', '')
    enablerepo = kwargs.get('enablerepo', '')

    # Support old 'repo' argument
    if repo and not fromrepo:
        fromrepo = repo

    repo_arg = ''
    if fromrepo:
        log.info('Restricting to repo {0!r}'.format(fromrepo))
        repo_arg = ('--disablerepo={0!r} --enablerepo={1!r}'
                    .format('*', fromrepo))
    else:
        repo_arg = ''
        if disablerepo:
            log.info('Disabling repo {0!r}'.format(disablerepo))
            repo_arg += '--disablerepo={0!r} '.format(disablerepo)
        if enablerepo:
            log.info('Enabling repo {0!r}'.format(enablerepo))
            repo_arg += '--enablerepo={0!r} '.format(enablerepo)
    return repo_arg


def _pkg_arch(name):
    '''
    Returns a 2-tuple of the name and arch parts of the passed string. Note
    that packages that are for the system architecture should not have the
    architecture specified in the passed string.
    '''
    # TODO: Fix __grains__ availability in provider overrides
    if not any(name.endswith('.{0}'.format(x)) for x in __ALL_ARCHES):
        return name, __grains__['cpuarch']
    try:
        pkgname, pkgarch = name.rsplit('.', 1)
    except ValueError:
        return name, __grains__['cpuarch']
    else:
        return pkgname, pkgarch


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=epel-testing
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', True))
    # FIXME: do stricter argument checking that somehow takes
    # _get_repo_options() into account

    if len(names) == 0:
        return ''
    ret = {}
    namearch_map = {}
    # Initialize the return dict with empty strings, and populate the namearch
    # dict
    for name in names:
        ret[name] = ''
        pkgname, pkgarch = _pkg_arch(name)
        namearch_map.setdefault(name, {})['name'] = pkgname
        namearch_map[name]['arch'] = pkgarch

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    # Get updates for specified package(s)
    repo_arg = _get_repo_options(**kwargs)
    updates = _repoquery(
        '{0} --pkgnarrow=available --queryformat {1!r} '
        '{2}'.format(
            repo_arg,
            __QUERYFORMAT,
            ' '.join([namearch_map[x]['name'] for x in names])
        )
    )

    for name in names:
        for pkg in (x for x in updates
                    if x.shortname == namearch_map[name]['name']):
            if (all(x in __SUFFIX_NOT_NEEDED
                    for x in (namearch_map[name]['arch'], pkg.arch))
                    or namearch_map[name]['arch'] == pkg.arch):
                ret[name] = pkg.version

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


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


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # 'removed' not yet implemented or not applicable
    if salt.utils.is_true(kwargs.get('removed')):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    ret = {}
    cmd = 'rpm -qa --queryformat "{0}\n"'.format(__QUERYFORMAT)
    for line in __salt__['cmd.run'](cmd).splitlines():
        pkginfo = _parse_pkginfo(line)
        if pkginfo is None:
            continue
        __salt__['pkg_resource.add_pkg'](ret, pkginfo.name, pkginfo.version)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def list_upgrades(refresh=True, **kwargs):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    repo_arg = _get_repo_options(**kwargs)
    updates = _repoquery('{0} --all --pkgnarrow=updates --queryformat '
                         '"{1}"'.format(repo_arg, __QUERYFORMAT))
    return dict([(x.name, x.version) for x in updates])


def check_db(*names, **kwargs):
    '''
    .. versionadded:: 0.17.0

    Returns a dict containing the following information for each specified
    package:

    1. A key ``found``, which will be a boolean value denoting if a match was
       found in the package database.
    2. If ``found`` is ``False``, then a second key called ``suggestions`` will
       be present, which will contain a list of possible matches.

    The ``fromrepo``, ``enablerepo``, and ``disablerepo`` arguments are
    supported, as used in pkg states.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.check_db <package1> <package2> <package3>
        salt '*' pkg.check_db <package1> <package2> <package3> fromrepo=epel-testing
    '''
    repo_arg = _get_repo_options(**kwargs)
    deplist_base = 'yum {0} deplist --quiet'.format(repo_arg) + ' {0!r}'
    repoquery_base = ('{0} -a --quiet --whatprovides --queryformat '
                      '{1!r}'.format(repo_arg, __QUERYFORMAT))

    ret = {}
    for name in names:
        ret.setdefault(name, {})['found'] = bool(
            __salt__['cmd.run'](deplist_base.format(name))
        )
        if ret[name]['found'] is False:
            repoquery_cmd = repoquery_base + ' {0!r}'.format(name)
            provides = set([x.name for x in _repoquery(repoquery_cmd)])
            if provides:
                for pkg in provides:
                    ret[name]['suggestions'] = list(provides)
            else:
                ret[name]['suggestions'] = []
    return ret


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    cmd = 'yum -q clean dbcache'
    __salt__['cmd.retcode'](cmd)
    return True


def install(name=None,
            refresh=False,
            fromrepo=None,
            skip_verify=False,
            pkgs=None,
            sources=None,
            **kwargs):
    '''
    Install the passed package(s), add refresh=True to clean the yum database
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``.i686``, ``.i586``, etc.) to the end of the
        package name.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to update the yum database before executing.

    skip_verify
        Skip the GPG verification check (e.g., ``--nogpgcheck``)

    version
        Install a specific version of the package, e.g. 1.2.3-4.el5. Ignored
        if "pkgs" or "sources" is passed.


    Repository Options:

    fromrepo
        Specify a package repository (or repositories) from which to install.
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4.el5"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources,
                                                                  **kwargs)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    version_num = kwargs.get('version')
    if version_num:
        if pkgs is None and sources is None:
            # Allow "version" to work for single package target
            pkg_params = {name: version_num}
        else:
            log.warning('"version" parameter will be ignored for multiple '
                        'package targets')

    repo_arg = _get_repo_options(fromrepo=fromrepo, **kwargs)

    old = list_pkgs()
    downgrade = []
    if pkg_type == 'repository':
        targets = []
        for pkgname, version_num in pkg_params.iteritems():
            if version_num is None:
                targets.append(pkgname)
            else:
                cver = old.get(pkgname, '')
                if __grains__.get('cpuarch', '') == 'x86_64':
                    try:
                        arch = re.search(r'(\.i\d86)$', pkgname).group(1)
                    except AttributeError:
                        arch = ''
                    else:
                        # Remove arch from pkgname
                        pkgname = pkgname[:-len(arch)]
                else:
                    arch = ''
                pkgstr = '"{0}-{1}{2}"'.format(pkgname, version_num, arch)
                if not cver or salt.utils.compare_versions(ver1=version_num,
                                                           oper='>=',
                                                           ver2=cver):
                    targets.append(pkgstr)
                else:
                    downgrade.append(pkgstr)
    else:
        targets = pkg_params

    if targets:
        cmd = 'yum -y {repo} {gpgcheck} install {pkg}'.format(
            repo=repo_arg,
            gpgcheck='--nogpgcheck' if skip_verify else '',
            pkg=' '.join(targets),
        )
        __salt__['cmd.run_all'](cmd)

    if downgrade:
        cmd = 'yum -y {repo} {gpgcheck} downgrade {pkg}'.format(
            repo=repo_arg,
            gpgcheck='--nogpgcheck' if skip_verify else '',
            pkg=' '.join(downgrade),
        )
        __salt__['cmd.run_all'](cmd)

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def upgrade(refresh=True):
    '''
    Run a full system upgrade, a yum upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    old = list_pkgs()
    cmd = 'yum -q -y upgrade'
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove packages with ``yum -q -y remove``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = 'yum -q -y remove "{0}"'.format('" "'.join(targets))
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported by yum, this function is identical to
    ``remove()``.

    name
        The name of the package to be deleted.


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
    return remove(name=name, pkgs=pkgs)


def list_repos(basedir='/etc/yum.repos.d'):
    '''
    Lists all repos in <basedir> (default: /etc/yum.repos.d/).

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_repos
    '''
    repos = {}
    for repofile in os.listdir(basedir):
        repopath = '{0}/{1}'.format(basedir, repofile)
        if not repofile.endswith('.repo'):
            continue
        header, filerepos = _parse_repo_file(repopath)
        for reponame in filerepos.keys():
            repo = filerepos[reponame]
            repo['file'] = repopath
            repos[reponame] = repo
    return repos


def get_repo(repo, basedir='/etc/yum.repos.d', **kwargs):
    '''
    Display a repo from <basedir> (default basedir: /etc/yum.repos.d).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo myrepo
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir
    '''
    repos = list_repos(basedir)

    # Find out what file the repo lives in
    repofile = ''
    for arepo in repos.keys():
        if arepo == repo:
            repofile = repos[arepo]['file']
    if not repofile:
        raise Exception('repo {0} was not found in {1}'.format(repo, basedir))

    # Return just one repo
    header, filerepos = _parse_repo_file(repofile)
    return filerepos[repo]


def del_repo(repo, basedir='/etc/yum.repos.d', **kwargs):
    '''
    Delete a repo from <basedir> (default basedir: /etc/yum.repos.d).

    If the .repo file that the repo exists in does not contain any other repo
    configuration, the file itself will be deleted.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo myrepo
        salt '*' pkg.del_repo myrepo basedir=/path/to/dir
    '''
    repos = list_repos(basedir)

    if repo not in repos:
        return 'Error: the {0} repo does not exist in {1}'.format(
            repo, basedir)

    # Find out what file the repo lives in
    repofile = ''
    for arepo in repos:
        if arepo == repo:
            repofile = repos[arepo]['file']

    # See if the repo is the only one in the file
    onlyrepo = True
    for arepo in repos.keys():
        if arepo == repo:
            continue
        if repos[arepo]['file'] == repofile:
            onlyrepo = False

    # If this is the only repo in the file, delete the file itself
    if onlyrepo:
        os.remove(repofile)
        return 'File {0} containing repo {1} has been removed'.format(
            repofile, repo)

    # There must be other repos in this file, write the file with them
    header, filerepos = _parse_repo_file(repofile)
    content = header
    for stanza in filerepos.keys():
        if stanza == repo:
            continue
        comments = ''
        if 'comments' in filerepos[stanza]:
            comments = '\n'.join(filerepos[stanza]['comments'])
            del filerepos[stanza]['comments']
        content += '\n[{0}]'.format(stanza)
        for line in filerepos[stanza]:
            content += '\n{0}={1}'.format(line, filerepos[stanza][line])
        content += '\n{0}\n'.format(comments)

    with salt.utils.fopen(repofile, 'w') as fileout:
        fileout.write(content)

    return 'Repo {0} has been removed from {1}'.format(repo, repofile)


def mod_repo(repo, basedir=None, **kwargs):
    '''
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified:

    repo
        name by which the yum refers to the repo
    name
        a human-readable name for the repo
    baseurl
        the URL for yum to reference
    mirrorlist
        the URL for yum to reference

    Key/Value pairs may also be removed from a repo's configuration by setting
    a key to a blank value. Bear in mind that a name cannot be deleted, and a
    baseurl can only be deleted if a mirrorlist is specified (or vice versa).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo reponame enabled=1 gpgcheck=1
        salt '*' pkg.mod_repo reponame basedir=/path/to/dir enabled=1
        salt '*' pkg.mod_repo reponame baseurl= mirrorlist=http://host.com/
    '''
    # Filter out '__pub' arguments
    repo_opts = dict((x, kwargs[x]) for x in kwargs if not x.startswith('__'))

    # Build a list of keys to be deleted
    todelete = []
    for key in repo_opts:
        if repo_opts[key] != 0 and not repo_opts[key]:
            del repo_opts[key]
            todelete.append(key)

    # Fail if the user tried to delete the name
    if 'name' in todelete:
        return 'Error: The repo name cannot be deleted'

    # Give the user the ability to change the basedir
    repos = {}
    if basedir:
        repos = list_repos(basedir)
    else:
        repos = list_repos()
        basedir = '/etc/yum.repos.d'

    repofile = ''
    header = ''
    filerepos = {}
    if repo not in repos:
        # If the repo doesn't exist, create it in a new file
        repofile = '{0}/{1}.repo'.format(basedir, repo)

        if 'name' not in repo_opts:
            return ('Error: The repo does not exist and needs to be created, '
                    'but a name was not given')

        if 'baseurl' not in repo_opts and 'mirrorlist' not in repo_opts:
            return ('Error: The repo does not exist and needs to be created, '
                    'but either a baseurl or a mirrorlist needs to be given')
        filerepos[repo] = {}
    else:
        # The repo does exist, open its file
        repofile = repos[repo]['file']
        header, filerepos = _parse_repo_file(repofile)

    # Error out if they tried to delete baseurl or mirrorlist improperly
    if 'baseurl' in todelete:
        if 'mirrorlist' not in repo_opts and 'mirrorlist' \
                not in filerepos[repo].keys():
            return 'Error: Cannot delete baseurl without specifying mirrorlist'
    if 'mirrorlist' in todelete:
        if 'baseurl' not in repo_opts and 'baseurl' \
                not in filerepos[repo].keys():
            return 'Error: Cannot delete mirrorlist without specifying baseurl'

    # Delete anything in the todelete list
    for key in todelete:
        if key in filerepos[repo].keys():
            del filerepos[repo][key]

    # Old file or new, write out the repos(s)
    filerepos[repo].update(repo_opts)
    content = header
    for stanza in filerepos.keys():
        comments = ''
        if 'comments' in filerepos[stanza].keys():
            comments = '\n'.join(filerepos[stanza]['comments'])
            del filerepos[stanza]['comments']
        content += '\n[{0}]'.format(stanza)
        for line in filerepos[stanza].keys():
            content += '\n{0}={1}'.format(line, filerepos[stanza][line])
        content += '\n{0}\n'.format(comments)

    with salt.utils.fopen(repofile, 'w') as fileout:
        fileout.write(content)

    return {repofile: filerepos}


def _parse_repo_file(filename):
    '''
    Turn a single repo file into a dict
    '''
    repos = {}
    header = ''
    repo = ''
    with salt.utils.fopen(filename, 'r') as rfile:
        for line in rfile:
            if line.startswith('['):
                repo = line.strip().replace('[', '').replace(']', '')
                repos[repo] = {}

            # Even though these are essentially uselss, I want to allow the
            # user to maintain their own comments, etc
            if not line:
                if not repo:
                    header += line
            if line.startswith('#'):
                if not repo:
                    header += line
                else:
                    if 'comments' not in repos[repo]:
                        repos[repo]['comments'] = []
                    repos[repo]['comments'].append(line.strip())
                continue

            # These are the actual configuration lines that matter
            if '=' in line:
                comps = line.strip().split('=')
                repos[repo][comps[0].strip()] = '='.join(comps[1:])

    return (header, repos)


def expand_repo_def(repokwargs):
    '''
    Take a repository definition and expand it to the full pkg repository dict
    that can be used for comparison. This is a helper function to make
    certain repo managers sane for comparison in the pkgrepo states.

    There is no use to calling this function via the CLI.
    '''
    # YUM doesn't need the data massaged.
    return repokwargs

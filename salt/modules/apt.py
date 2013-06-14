'''
Support for APT (Advanced Packaging Tool)
'''

# Import python libs
import copy
import os
import re
import logging
import urllib2
import json

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)


try:
    from aptsources import sourceslist
    apt_support = True
except ImportError as e:
    apt_support = False

try:
    import softwareproperties.ppa
    ppa_format_support = True
except ImportError as e:
    ppa_format_support = False

# Source format for urllib fallback on PPA handling
LP_SRC_FORMAT = 'deb http://ppa.launchpad.net/{0}/{1}/ubuntu {2} main'
LP_PVT_SRC_FORMAT = 'deb https://{0}private-ppa.launchpad.net/{1}/{2}/ubuntu' \
                    ' {3} main'

_MODIFY_OK = frozenset(['uri', 'comps', 'architectures', 'disabled',
                        'file', 'dist'])


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    if __grains__['os_family'] != 'Debian':
        return False
    return 'pkg'


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
            'UCF_FORCE_CONFFOLD': '1',
        }
        # Export these puppies so they persist
        os.environ.update(env_vars)


def _get_ppa_info_from_launchpad(owner_name, ppa_name):
    '''
    Idea from softwareproperties.ppa.
    Uses urllib2 which sacrifices server cert verification.

    This is used as fall-back code or for secure PPAs

    :param owner_name:
    :param ppa_name:
    :return:
    '''

    lp_url = 'https://launchpad.net/api/1.0/~{0}/+archive/{1}'.format(
        owner_name, ppa_name)
    request = urllib2.Request(lp_url, headers={'Accept': 'application/json'})
    lp_page = urllib2.urlopen(request)
    return json.load(lp_page)


def _reconstruct_ppa_name(owner_name, ppa_name):
    return 'ppa:{0}/{1}'.format(owner_name, ppa_name)


def _pkgname_without_arch(name):
    '''
    Check for ':arch' appended to pkg name (i.e. 32 bit installed on 64 bit
    machine is ':i386')
    '''
    if name.find(':') >= 0:
        return name.split(':')[0]
    return name


def _get_repo(**kwargs):
    '''
    Check the kwargs for either 'fromrepo' or 'repo' and return the value.
    'fromrepo' takes precedence over 'repo'.
    '''
    for key in ('fromrepo', 'repo'):
        try:
            return kwargs[key]
        except KeyError:
            pass
    return ''


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=unstable
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
    pkgs = list_pkgs(versions_as_list=True)
    fromrepo = _get_repo(**kwargs)
    repo = ' -o APT::Default-Release="{0}"'.format(fromrepo) \
        if fromrepo else ''
    for name in names:
        cmd = 'apt-cache -q policy {0}{1} | grep Candidate'.format(name, repo)
        out = __salt__['cmd.run_all'](cmd)
        candidate = out['stdout'].split()
        if len(candidate) >= 2:
            candidate = candidate[-1]
            if candidate.lower() == '(none)':
                candidate = ''
        else:
            candidate = ''

        installed = pkgs.get(name, [])
        if not installed:
            ret[name] = candidate
        else:
            # If there are no installed versions that are greater than or equal
            # to the install candidate, then the candidate is an upgrade, so
            # add it to the return dict
            if not any([compare(pkg1=x, oper='>=', pkg2=candidate)
                        for x in installed]):
                ret[name] = candidate

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def refresh_db():
    '''
    Updates the APT database to latest packages based upon repositories

    Returns a dict, with the keys being package databases and the values being
    the result of the update attempt. Values can be one of the following:

        ``True``: Database updated successfully
        ``False``: Problem updating database
        ``None``: Database already up-to-date

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    ret = {}
    cmd = 'apt-get -q update'
    out = __salt__['cmd.run_all'](cmd).get('stdout', '')

    lines = out.splitlines()
    for line in lines:
        cols = line.split()
        if not cols:
            continue
        ident = ' '.join(cols[1:])
        if 'Get' in cols[0]:
            # Strip filesize from end of line
            ident = re.sub(r' \[.+B\]$', '', ident)
            ret[ident] = True
        elif cols[0] == 'Ign':
            ret[ident] = False
        elif cols[0] == 'Hit':
            ret[ident] = None
    return ret


def install(name=None,
            refresh=False,
            fromrepo=None,
            skip_verify=False,
            debconf=None,
            pkgs=None,
            sources=None,
            **kwargs):
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
        Install a specific version of the package, e.g. 1.2.3~0ubuntu0. Ignored
        if "pkgs" or "sources" is passed.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example::
            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-0ubuntu0"}]'

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
    if salt.utils.is_true(refresh):
        refresh_db()

    if debconf:
        __salt__['debconf.set_file'](debconf)

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources,
                                                                  **kwargs)

    # Support old "repo" argument
    repo = kwargs.get('repo', '')
    if not fromrepo and repo:
        fromrepo = repo

    if kwargs.get('env'):
        try:
            os.environ.update(kwargs.get('env'))
        except Exception as e:
            log.exception(e)

    old = list_pkgs()

    downgrade = False
    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        cmd = 'dpkg -i {confold} {verify} {pkg}'.format(
            confold='--force-confold',
            verify='--force-bad-verify' if skip_verify else '',
            pkg=' '.join(pkg_params),
        )
    elif pkg_type == 'repository':
        if pkgs is None and kwargs.get('version') and len(pkg_params) == 1:
            # Only use the 'version' param if 'name' was not specified as a
            # comma-separated list
            pkg_params = {name: kwargs.get('version')}
        targets = []
        for param, version_num in pkg_params.iteritems():
            if version_num is None:
                targets.append(param)
            else:
                cver = old.get(param)
                if cver is not None \
                        and __salt__['pkg.compare'](pkg1=version_num,
                                                    oper='<', pkg2=cver):
                    downgrade = True
                targets.append('"{0}={1}"'.format(param, version_num))
        if fromrepo:
            log.info('Targeting repo "{0}"'.format(fromrepo))
        cmd = 'apt-get -q -y {force_yes} {confold} {confdef} {verify} ' \
              '{target} install {pkg}'.format(
                  force_yes='--force-yes' if downgrade else '',
                  confold='-o DPkg::Options::=--force-confold',
                  confdef='-o DPkg::Options::=--force-confdef',
                  verify='--allow-unauthenticated' if skip_verify else '',
                  target='-t {0}'.format(fromrepo) if fromrepo else '',
                  pkg=' '.join(targets),
              )

    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def _uninstall(action='remove', name=None, pkgs=None, **kwargs):
    '''
    remove and purge do identical things but with different apt-get commands,
    this function performs the common logic.
    '''
    if kwargs.get('env'):
        try:
            os.environ.update(kwargs.get('env'))
        except Exception as e:
            log.exception(e)

    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    old = list_pkgs()
    old_removed = list_pkgs(removed=True)
    targets = [x for x in pkg_params if x in old]
    if action == 'purge':
        targets.extend([x for x in pkg_params if x in old_removed])
    if not targets:
        return {}
    cmd = 'apt-get -q -y {0} {1}'.format(action, ' '.join(targets))
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    new_removed = list_pkgs(removed=True)

    ret = {'installed': __salt__['pkg_resource.find_changes'](old, new)}
    if action == 'purge':
        ret['removed'] = __salt__['pkg_resource.find_changes'](old_removed,
                                                               new_removed)
        return ret
    else:
        return ret['installed']


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove packages using ``apt-get remove``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='remove', name=name, pkgs=pkgs, **kwargs)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Remove packages via ``apt-get purge`` along with all configuration files
    and unused dependencies.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='purge', name=name, pkgs=pkgs, **kwargs)


def upgrade(refresh=True, **kwargs):
    '''
    Upgrades all packages via ``apt-get dist-upgrade``

    Returns a dict containing the changes.

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    old = list_pkgs()
    cmd = ('apt-get -q -y -o DPkg::Options::=--force-confold '
           '-o DPkg::Options::=--force-confdef dist-upgrade')
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def _clean_pkglist(pkgs):
    '''
    Go through package list and, if any packages have a mix of actual versions
    and virtual package markers, remove the virtual package markers.
    '''
    for key in pkgs.keys():
        if '1' in pkgs[key] and len(pkgs[key]) > 1:
            while True:
                try:
                    pkgs[key].remove('1')
                except ValueError:
                    break


def list_pkgs(versions_as_list=False, removed=False):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    If removed is ``True``, then only packages which have been removed (but not
    purged) will be returned.

    External dependencies::

        Virtual package resolution requires dctrl-tools.
        Without dctrl-tools virtual packages will be reported as not installed.

    CLI Example::

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    removed = salt.utils.is_true(removed)

    if 'pkg.list_pkgs' in __context__:
        if removed:
            ret = copy.deepcopy(__context__['pkg.list_pkgs']['removed'])
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs']['installed'])
        if not versions_as_list:
            __salt__['pkg_resource.stringify'](ret)
        return ret

    ret = {'installed': {}, 'removed': {}}
    cmd = 'dpkg-query --showformat=\'${Status} ${Package} ' \
          '${Version}\n\' -W'

    out = __salt__['cmd.run_all'](cmd).get('stdout', '')
    # Typical lines of output:
    # install ok installed zsh 4.3.17-1ubuntu1
    # deinstall ok config-files mc 3:4.8.1-2ubuntu1
    for line in out.splitlines():
        cols = line.split()
        try:
            linetype, status, name, version_num = \
                [cols[x] for x in (0, 2, 3, 4)]
        except ValueError:
            continue
        name = _pkgname_without_arch(name)
        if len(cols):
            if ('install' in linetype or 'hold' in linetype) and \
                    'installed' in status:
                __salt__['pkg_resource.add_pkg'](ret['installed'],
                                                 name,
                                                 version_num)
            elif 'deinstall' in linetype:
                __salt__['pkg_resource.add_pkg'](ret['removed'],
                                                 name,
                                                 version_num)

    # Check for virtual packages. We need dctrl-tools for this.
    if __salt__['cmd.has_exec']('grep-available'):
        cmd = 'grep-available -F Provides -s Package,Provides -e "^.+$"'
        out = __salt__['cmd.run_stdout'](cmd)

        virtpkg_re = re.compile('Package: (\\S+)\nProvides: ([\\S, ]+)')
        virtpkgs = set()
        for realpkg, provides in virtpkg_re.findall(out):
            # grep-available returns info on all virtual packages. Ignore any
            # virtual packages that do not have the real package installed.
            if realpkg in ret:
                virtpkgs.update(provides.split(', '))
        for virtname in virtpkgs:
            # Set virtual package versions to '1'
            __salt__['pkg_resource.add_pkg'](ret, virtname, '1')

    for pkglist_type in ('installed', 'removed'):
        __salt__['pkg_resource.sort_pkglist'](ret[pkglist_type])
        _clean_pkglist(ret[pkglist_type])

    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)

    if removed:
        ret = ret['removed']
    else:
        ret = ret['installed']
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def _get_upgradable():
    '''
    Utility function to get upgradable packages

    Sample return data:
    { 'pkgname': '1.2.3-45', ... }
    '''

    cmd = 'apt-get --just-print dist-upgrade'
    out = __salt__['cmd.run_all'](cmd).get('stdout', '')

    # rexp parses lines that look like the following:
    # Conf libxfont1 (1:1.4.5-1 Debian:testing [i386])
    rexp = re.compile('(?m)^Conf '
                      '([^ ]+) '          # Package name
                      r'\(([^ ]+)')        # Version
    keys = ['name', 'version']
    _get = lambda l, k: l[keys.index(k)]

    upgrades = rexp.findall(out)

    ret = {}
    for line in upgrades:
        name = _get(line, 'name')
        version_num = _get(line, 'version')
        ret[name] = version_num

    return ret


def list_upgrades(refresh=True):
    '''
    List all available package upgrades.

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    return _get_upgradable()


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def perform_cmp(pkg1='', pkg2=''):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example::

        salt '*' pkg.perform_cmp '0.2.4-0ubuntu1' '0.2.4.1-0ubuntu1'
        salt '*' pkg.perform_cmp pkg1='0.2.4-0ubuntu1' pkg2='0.2.4.1-0ubuntu1'
    '''
    try:
        for oper, ret in (('lt', -1), ('eq', 0), ('gt', 1)):
            cmd = 'dpkg --compare-versions "{0}" {1} ' \
                  '"{2}"'.format(pkg1, oper, pkg2)
            if __salt__['cmd.retcode'](cmd) == 0:
                return ret
    except Exception as e:
        log.error(e)
    return None


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Compare two version strings.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '<' '0.2.4.1-0'
        salt '*' pkg.compare pkg1='0.2.4-0' oper='<' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](pkg1=pkg1, oper=oper, pkg2=pkg2)


def _split_repo_str(repo):
    split = sourceslist.SourceEntry(repo)
    return split.type, split.uri, split.dist, split.comps


def _consolidate_repo_sources(sources):
    if not isinstance(sources, sourceslist.SourcesList):
        raise TypeError('"{0}" not a "{1}"'.format(type(sources),
                                                   sourceslist.SourcesList))

    consolidated = {}
    delete_files = set()
    base_file = sourceslist.SourceEntry('').file

    repos = filter(lambda s: not s.invalid, sources.list)

    for r in repos:
        key = str((getattr(r, 'architectures', []),
                   r.disabled, r.type, r.uri))
        if key in consolidated:
            combined = consolidated[key]
            combined_comps = set(r.comps).union(set(combined.comps))
            consolidated[key].comps = list(combined_comps)
        else:
            consolidated[key] = sourceslist.SourceEntry(r.line)

        if r.file != base_file:
            delete_files.add(r.file)

    sources.list = consolidated.values()
    sources.save()
    for f in delete_files:
        try:
            os.remove(f)
        except Exception:
            pass
    return sources


def list_repos():
    '''
    Lists all repos in the sources.list (and sources.lists.d) files

    CLI Example::

       salt '*' pkg.list_repos
       salt '*' pkg.list_repos disabled=True
    '''
    if not apt_support:
        msg = 'Error: aptsources.sourceslist python module not found'
        log.error(msg)
        return msg

    repos = {}
    sources = sourceslist.SourcesList()
    for source in sources.list:
        if source.invalid:
            continue
        repo = {}
        repo['file'] = source.file
        repo['comps'] = getattr(source, 'comps', [])
        repo['disabled'] = source.disabled
        repo['dist'] = source.dist
        repo['type'] = source.type
        repo['uri'] = source.uri
        repo['line'] = source.line.strip()
        repo['architectures'] = getattr(source, 'architectures', [])
        repos.setdefault(source.uri, []).append(repo)
    return repos


def get_repo(repo, **kwargs):
    '''
    Display a repo from the sources.list / sources.list.d

    The repo passwd in needs to be a complete repo entry.

    CLI Examples::

        salt '*' pkg.get_repo "myrepo definition"
    '''
    if not apt_support:
        msg = 'Error: aptsources.sourceslist python module not found'
        raise Exception(msg)

    ppa_auth = kwargs.get('ppa_auth', None)
    # we have to be clever about this since the repo definition formats
    # are a bit more "loose" than in some other distributions
    if repo.startswith('ppa:') and __grains__['os'] == 'Ubuntu':
        # This is a PPA definition meaning special handling is needed
        # to derive the name.
        dist = __grains__['lsb_codename']
        owner_name, ppa_name = repo[4:].split('/')
        if ppa_auth:
            auth_info = '{0}@'.format(ppa_auth)
            repo = LP_PVT_SRC_FORMAT.format(auth_info, owner_name,
                                            ppa_name, dist)
        else:
            if ppa_format_support:
                repo = softwareproperties.ppa.expand_ppa_line(
                    repo,
                    __grains__['lsb_codename'])[0]
            else:
                repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)

    repos = list_repos()

    if repos:
        try:
            repo_type, repo_uri, repo_dist, repo_comps = _split_repo_str(repo)
            if ppa_auth:
                uri_match = re.search('(http[s]?://)(.+)', repo_uri)
                if uri_match:
                    if not uri_match.group(2).startswith(ppa_auth):
                        repo_uri = '{0}{1}@{2}'.format(uri_match.group(1),
                                                       ppa_auth,
                                                       uri_match.group(2))
        except SyntaxError:
            error_str = 'Error: repo "{0}" is not a well formatted definition'
            raise Exception(error_str.format(repo))

        for source in repos.values():
            for sub in source:
                if (sub['type'] == repo_type and
                    sub['uri'] == repo_uri and
                        sub['dist'] == repo_dist):
                    if not repo_comps:
                        return sub
                    for comp in repo_comps:
                        if comp in sub.get('comps', []):
                            return sub

    raise Exception('repo "{0}" was not found'.format(repo))


def del_repo(repo, refresh=False, **kwargs):
    '''
    Delete a repo from the sources.list / sources.list.d

    If the .list file is in the sources.list.d directory
    and the file that the repo exists in does not contain any other
    repo configuration, the file itself will be deleted.

    The repo passed in must be a fully formed repository definition
    string.

    CLI Examples::

        salt '*' pkg.del_repo "myrepo definition"
        salt '*' pkg.del_repo "myrepo definition" refresh=True
    '''
    if not apt_support:
        return 'Error: aptsources.sourceslist python module not found'

    is_ppa = False
    if repo.startswith('ppa:') and __grains__['os'] == 'Ubuntu':
        # This is a PPA definition meaning special handling is needed
        # to derive the name.
        is_ppa = True
        dist = __grains__['lsb_codename']
        if not ppa_format_support:
            warning_str = 'Unable to use functions from ' \
                          '"python-software-properties" package, making ' \
                          'best guess at ppa format: {0}'
            log.warning(warning_str.format(repo))
            owner_name, ppa_name = repo[4:].split('/')
            if 'ppa_auth' in kwargs:
                auth_info = '{0}@'.format(kwargs['ppa_auth'])
                repo = LP_PVT_SRC_FORMAT.format(auth_info, dist, owner_name,
                                                ppa_name)
            else:
                repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)
        else:
            repo = softwareproperties.ppa.expand_ppa_line(repo, dist)[0]

    sources = sourceslist.SourcesList()
    repos = filter(lambda s: not s.invalid, sources.list)
    if repos:
        deleted_from = dict()
        try:
            repo_type, repo_uri, repo_dist, repo_comps = _split_repo_str(repo)
        except SyntaxError:
            error_str = 'Error: repo "{0}" not a well formatted definition'
            return error_str.format(repo)

        for source in repos:
            if (source.type == repo_type and source.uri == repo_uri and
                    source.dist == repo_dist):

                s_comps = set(source.comps)
                r_comps = set(repo_comps)
                if s_comps.intersection(r_comps):
                    deleted_from[source.file] = 0
                    source.comps = list(s_comps.difference(r_comps))
                    if not source.comps:
                        try:
                            sources.remove(source)
                        except ValueError:
                            pass
            # PPAs are special and can add deb-src where expand_ppa_line doesn't
            # always reflect this.  Lets just cleanup here for good measure
            if (is_ppa and repo_type == 'deb' and source.type == 'deb-src' and
                    source.uri == repo_uri and source.dist == repo_dist):

                s_comps = set(source.comps)
                r_comps = set(repo_comps)
                if s_comps.intersection(r_comps):
                    deleted_from[source.file] = 0
                    source.comps = list(s_comps.difference(r_comps))
                    if not source.comps:
                        try:
                            sources.remove(source)
                        except ValueError:
                            pass
            sources.save()
        if deleted_from:
            ret = ''
            for source in sources:
                if source.file in deleted_from:
                    deleted_from[source.file] += 1
            for repo_file, c in deleted_from.iteritems():
                msg = 'Repo "{0}" has been removed from {1}.\n'
                if c == 0 and 'sources.list.d/' in repo_file:
                    if os.path.isfile(repo_file):
                        msg = ('File {1} containing repo "{0}" has been '
                               'removed.\n')
                        try:
                            os.remove(repo_file)
                        except OSError:
                            pass
                ret += msg.format(repo, repo_file)
            # explicit refresh after a repo is deleted
            refresh_db()
            return ret

    return "Repo {0} doesn't exist in the sources.list(s)".format(repo)


def mod_repo(repo, **kwargs):
    '''
    Modify one or more values for a repo.  If the repo does not exist, it will
    be created, so long as the definition is well formed.  For Ubuntu the
    "ppa:<project>/repo" format is acceptable. "ppa:" format can only be
    used to create a new repository.

    The following options are available to modify a repo definition::

        comps (a comma separated list of components for the repo, e.g. "main")
        file (a file name to be used)
        keyserver (keyserver to get gpg key from)
        keyid (key id to load with the keyserver argument)
        key_url (URL to a gpg key to add to the apt gpg keyring)
        consolidate (if true, will attempt to de-dup and consolidate sources)

        * Note: Due to the way keys are stored for apt, there is a known issue
                where the key wont be updated unless another change is made
                at the same time.  Keys should be properly added on initial
                configuration.

    CLI Examples::

        salt '*' pkg.mod_repo 'myrepo definition' uri=http://new/uri
        salt '*' pkg.mod_repo 'myrepo definition' comps=main,universe
    '''
    if not apt_support:
        raise ImportError('Error: aptsources.sourceslist module not found')

    # to ensure no one sets some key values that _shouldn't_ be changed on the
    # object itself, this is just a white-list of "ok" to set properties
    if repo.startswith('ppa:'):
        if __grains__['os'] == 'Ubuntu':
            # secure PPAs cannot be supported as of the time of this code
            # implementation via apt-add-repository.  The code path for
            # secure PPAs should be the same as urllib method
            if ppa_format_support and 'ppa_auth' not in kwargs:
                cmd = 'apt-add-repository -y {0}'.format(repo)
                out = __salt__['cmd.run_stdout'](cmd, **kwargs)
                # explicit refresh when a repo is modified.
                refresh_db()
                return {repo: out}
            else:
                if not ppa_format_support:
                    warning_str = 'Unable to use functions from ' \
                                  '"python-software-properties" package, ' \
                                  'making best guess at ppa format: {0}'
                    log.warning(warning_str.format(repo))
                else:
                    log.info('falling back to urllib method for private PPA ')
                #fall back to urllib style
                try:
                    owner_name, ppa_name = repo[4:].split('/', 1)
                except ValueError:
                    err_str = 'Unable to get PPA info from argument. ' \
                              'Expected format "<PPA_OWNER>/<PPA_NAME>" ' \
                              '(e.g. saltstack/salt) not found.  Received ' \
                              '"{0}" instead.'
                    raise Exception(err_str.format(repo[4:]))
                dist = __grains__['lsb_codename']
                # ppa has a lot of implicit arguments. Make them explicit.
                # These will defer to any user-defined variants
                kwargs['dist'] = dist
                ppa_auth = ''
                if file not in kwargs:
                    filename = '/etc/apt/sources.list.d/{0}-{1}-{2}.list'
                    kwargs['file'] = filename.format(owner_name, ppa_name,
                                                     dist)
                try:
                    launchpad_ppa_info = _get_ppa_info_from_launchpad(
                        owner_name, ppa_name)
                    if 'ppa_auth' not in kwargs:
                        kwargs['keyid'] = launchpad_ppa_info[
                            'signing_key_fingerprint']
                    else:
                        if 'keyid' not in kwargs:
                            error_str = 'Private PPAs require a ' \
                                        'keyid to be specified: {0}/{1}'
                            raise Exception(error_str.format(owner_name,
                                                             ppa_name))
                except urllib2.HTTPError as exc:
                    error_str = 'Launchpad does not know about {0}/{1}: {2}'
                    raise Exception(error_str.format(owner_name, ppa_name,
                                                     exc))
                except IndexError as e:
                    error_str = 'Launchpad knows about {0}/{1} but did not ' \
                                'return a fingerprint. Please set keyid ' \
                                'manually: {2}'
                    raise Exception(error_str.format(owner_name, ppa_name, e))

                if 'keyserver' not in kwargs:
                    kwargs['keyserver'] = 'keyserver.ubuntu.com'
                if 'ppa_auth' in kwargs:
                    if not launchpad_ppa_info['private']:
                        error_str = 'PPA is not private but auth ' \
                                    'credentials passed: {0}'
                        raise Exception(error_str.format(repo))
                # assign the new repo format to the "repo" variable
                # so we can fall through to the "normal" mechanism
                # here.
                if 'ppa_auth' in kwargs:
                    ppa_auth = '{0}@'.format(kwargs['ppa_auth'])
                    repo = LP_PVT_SRC_FORMAT.format(ppa_auth, owner_name,
                                                    ppa_name, dist)
                else:
                    repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)
        else:
            error_str = 'cannot parse "ppa:" style repo definitions: {0}'
            raise Exception(error_str.format(repo))

    sources = sourceslist.SourcesList()
    if kwargs.get('consolidate', False):
        # attempt to de-dup and consolidate all sources
        # down to entries in sources.list
        # this option makes it easier to keep the sources
        # list in a "sane" state.
        #
        # this should remove duplicates, consolidate comps
        # for a given source down to one line
        # and eliminate "invalid" and comment lines
        #
        # the second side effect is removal of files
        # that are not the main sources.list file
        sources = _consolidate_repo_sources(sources)

    repos = filter(lambda s: not s.invalid, sources)
    mod_source = None
    try:
        repo_type, repo_uri, repo_dist, repo_comps = _split_repo_str(
            repo)
    except SyntaxError:
        error_str = 'Error: repo "{0}" not a well formatted definition'
        raise SyntaxError(error_str.format(repo))

    full_comp_list = set(repo_comps)

    if 'keyid' in kwargs:
        keyid = kwargs.pop('keyid', None)
        ks = kwargs.pop('keyserver', None)
        if not keyid or not ks:
            error_str = 'both keyserver and keyid options required.'
            raise NameError(error_str)
        cmd = 'apt-key export {0}'.format(keyid)
        output = __salt__['cmd.run_stdout'](cmd, **kwargs)
        imported = output.startswith('-----BEGIN PGP')
        if ks:
            if not imported:
                cmd = ('apt-key adv --keyserver {0} --logger-fd 1 '
                       '--recv-keys {1}')
                out = __salt__['cmd.run_stdout'](cmd.format(ks, keyid),
                                                 **kwargs)
                if not (out.find('imported') or out.find('not changed')):
                    error_str = 'Error: key retrieval failed: {0}'
                    raise Exception(
                        error_str.format(
                            cmd.format(
                                ks,
                                keyid
                            )
                        )
                    )
    elif 'key_url' in kwargs:
        key_url = kwargs['key_url']
        fn_ = __salt__['cp.cache_file'](key_url)
        cmd = 'apt-key add {0}'.format(fn_)
        out = __salt__['cmd.run_stdout'](cmd, **kwargs)
        if not out.upper().startswith('OK'):
            error_str = 'Error: key retrieval failed: {0}'
            raise Exception(error_str.format(cmd.format(key_url)))

    if 'comps' in kwargs:
        kwargs['comps'] = kwargs['comps'].split(',')
        full_comp_list.union(set(kwargs['comps']))
    else:
        kwargs['comps'] = list(full_comp_list)

    if 'architectures' in kwargs:
        kwargs['architectures'] = kwargs['architectures'].split(',')

    if 'disabled' in kwargs:
        kw_disabled = kwargs['disabled']
        if kw_disabled is True or str(kw_disabled).lower() == 'true':
            kwargs['disabled'] = True
        else:
            kwargs['disabled'] = False

    kw_type = kwargs.get('type')
    kw_dist = kwargs.get('dist')

    for source in repos:
        # This series of checks will identify the starting source line
        # and the resulting source line.  The idea here is to ensure
        # we are not retuning bogus data because the source line
        # has already been modified on a previous run.
        if ((source.type == repo_type and source.uri == repo_uri
             and source.dist == repo_dist) or
            (source.dist == kw_dist and source.type == kw_type
             and source.type == kw_type)):

            for comp in full_comp_list:
                if comp in getattr(source, 'comps', []):
                    mod_source = source
            if not source.comps:
                mod_source = source
            if mod_source:
                break

    if not mod_source:
        mod_source = sourceslist.SourceEntry(repo)
        sources.list.append(mod_source)

    # if all comps aren't part of the disable
    # match, it is important we keep the comps
    # not destined to be disabled/enabled in
    # the original state
    if ('disabled' in kwargs and
            mod_source.disabled != kwargs['disabled']):

        s_comps = set(mod_source.comps)
        r_comps = set(repo_comps)
        if s_comps.symmetric_difference(r_comps):
            new_source = sourceslist.SourceEntry(source.line)
            new_source.file = source.file
            new_source.comps = list(r_comps.difference(s_comps))
            source.comps = list(s_comps.difference(r_comps))
            sources.insert(sources.index(source), new_source)
            sources.save()

    for key in kwargs:
        if key in _MODIFY_OK and hasattr(mod_source, key):
            setattr(mod_source, key, kwargs[key])
    sources.save()
    # on changes, explicitly refresh
    refresh_db()
    return {
        repo: {
            'architectures': getattr(mod_source, 'architectures', []),
            'comps': mod_source.comps,
            'disabled': mod_source.disabled,
            'file': mod_source.file,
            'type': mod_source.type,
            'uri': mod_source.uri,
            'line': mod_source.line
        }
    }


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's package database (not
    generally recommended).

    CLI Examples::

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_list'](*packages)


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples::

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_dict'](*packages)


def expand_repo_def(repokwargs):
    '''
    Take a repository definition and expand it to the full pkg repository dict
    that can be used for comparison.  This is a helper function to make
    the Debian/Ubuntu apt sources sane for comparison in the pkgrepo states.

    There is no use to calling this function via the CLI.
    '''
    sanitized = {}

    if not apt_support:
        msg = 'Error: aptsources.sourceslist python module not found'
        raise Exception(msg)

    repo = repokwargs['repo']

    if repo.startswith('ppa:') and __grains__['os'] == 'Ubuntu':
        dist = __grains__['lsb_codename']
        owner_name, ppa_name = repo[4:].split('/', 1)
        if 'ppa_auth' in repokwargs:
            auth_info = '{0}@'.format(repokwargs['ppa_auth'])
            repo = LP_PVT_SRC_FORMAT.format(auth_info, owner_name, ppa_name,
                                            dist)
        else:
            if ppa_format_support:
                repo = softwareproperties.ppa.expand_ppa_line(
                    repo, dist)[0]
            else:
                repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)

        if file not in repokwargs:
            filename = '/etc/apt/sources.list.d/{0}-{1}-{2}.list'
            repokwargs['file'] = filename.format(owner_name, ppa_name,
                                                 dist)

    source_entry = sourceslist.SourceEntry(repo)
    for kwarg in _MODIFY_OK:
        if kwarg in repokwargs:
            setattr(source_entry, kwarg, repokwargs[kwarg])

    sanitized['file'] = source_entry.file
    sanitized['comps'] = getattr(source_entry, 'comps', [])
    sanitized['disabled'] = source_entry.disabled
    sanitized['dist'] = source_entry.dist
    sanitized['type'] = source_entry.type
    sanitized['uri'] = source_entry.uri
    sanitized['line'] = source_entry.line.strip()
    sanitized['architectures'] = getattr(source_entry, 'architectures', [])

    return sanitized

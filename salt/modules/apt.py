'''
Support for APT (Advanced Packaging Tool)
'''

# Import python libs
import os
import re
import logging

#import aptsources.sourceslist
try:
    from aptsources import sourceslist
    apt_support = True
except ImportError:
    apt_support = False

try:
    from softwareproperties.ppa import expand_ppa_line
    ppa_format_support = True
except ImportError:
    ppa_format_support = False

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


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
            'UCF_FORCE_CONFFOLD': '1',
        }
        # Export these puppies so they persist
        os.environ.update(env_vars)


def _pkgname_without_arch(name):
    '''
    Check for ':arch' appended to pkg name (i.e. 32 bit installed on 64 bit
    machine is ':i386')
    '''
    if name.find(':') >= 0:
        return name.split(':')[0]
    return name


def available_version(*names):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.available_version <package name>
        salt '*' pkg.available_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
    pkgs = list_pkgs()
    for name in names:
        cmd = 'apt-cache -q policy {0} | grep Candidate'.format(name)
        candidate = __salt__['cmd.run_stdout'](cmd).split()
        if len(candidate) >= 2:
            candidate = candidate[-1]
            if candidate.lower() == '(none)':
                candidate = ''
        else:
            candidate = ''

        installed = pkgs.get(name, '')
        if candidate:
            if not installed or compare(pkg1=installed, oper='<',
                                        pkg2=candidate):
                ret[name] = candidate

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


def version(*names):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    pkgs = list_pkgs()
    if len(names) == 0:
        return ''
    elif len(names) == 1:
        return pkgs.get(_pkgname_without_arch(names[0]), '')
    else:
        ret = {}
        for name in names:
            ret[name] = pkgs.get(_pkgname_without_arch(name), '')
        return ret


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
    lines = __salt__['cmd.run_stdout'](cmd).splitlines()
    for line in lines:
        cols = line.split()
        if not cols:
            continue
        ident = ' '.join(cols[1:])
        if 'Get' in cols[0]:
            # Strip filesize from end of line
            ident = re.sub(' \[.+B\]$', '', ident)
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
    # Note that this function will daemonize the subprocess
    # preventing a restart resulting from a salt-minion upgrade
    # from killing the apt and hence hosing the dpkg database
    salt.utils.daemonize_if(__opts__, **kwargs)

    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()

    if debconf:
        __salt__['debconf.set_file'](debconf)

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources)

    # Support old "repo" argument
    repo = kwargs.get('repo', '')
    if not fromrepo and repo:
        fromrepo = repo

    if kwargs.get('env'):
        try:
            os.environ.update(kwargs.get('env'))
        except Exception as e:
            log.exception(e)

    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        cmd = 'dpkg -i {verify} {pkg}'.format(
            verify='--force-bad-verify' if skip_verify else '',
            pkg=' '.join(pkg_params),
        )
    elif pkg_type == 'repository':
        if pkgs is None and kwargs.get('version'):
            pkg_params = {name: kwargs.get('version')}
        targets = []
        for param, version in pkg_params.iteritems():
            if version is None:
                targets.append(param)
            else:
                targets.append('"{0}={1}"'.format(param, version))
        if fromrepo:
            log.info('Targeting repo "{0}"'.format(fromrepo))
        cmd = 'apt-get -q -y {confold} {confdef} {verify} {target} install ' \
              '{pkg}'.format(
                  confold='-o DPkg::Options::=--force-confold',
                  confdef='-o DPkg::Options::=--force-confdef',
                  verify='--allow-unauthenticated' if skip_verify else '',
                  target='-t {0}'.format(fromrepo) if fromrepo else '',
                  pkg=' '.join(targets),
              )

    old = list_pkgs()
    __salt__['cmd.run_all'](cmd)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(pkg, **kwargs):
    '''
    Remove a single package via ``apt-get remove``

    Returns a list containing the names of the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    if kwargs.get('env'):
        try:
            os.environ.update(kwargs.get('env'))
        except Exception as e:
            log.exception(e)

    cmd = 'apt-get -q -y remove {0}'.format(pkg)
    __salt__['cmd.run'](cmd)
    new_pkgs = list_pkgs()
    for pkg in old_pkgs:
        if pkg not in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def purge(pkg, **kwargs):
    '''
    Remove a package via ``apt-get purge`` along with all configuration
    files and unused dependencies.

    Returns a list containing the names of the removed packages

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    if kwargs.get('env'):
        try:
            os.environ.update(kwargs.get('env'))
        except Exception as e:
            log.exception(e)

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
                            'new': '<new-version>'}
            }',
            ...
        ]

    CLI Example::

        salt '*' pkg.upgrade
    '''
    salt.utils.daemonize_if(__opts__, **kwargs)

    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
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


def list_upgrades(refresh=True):
    '''
    List all available package upgrades.

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()
    return _get_upgradable()


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return available_version(name) != ''


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
        key = str((r.architectures, r.disabled, r.type, r.uri))
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
        except:
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
        return 'Error: aptsources.sourceslist python module not found'

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
        repo['line'] = source.line
        repo['architectures'] = source.architectures
        repos.setdefault(source.uri, []).append(repo)
    return repos


def get_repo(repo):
    '''
    Display a repo from the sources.list / sources.list.d

    The repo passwd in needs to be a complete repo entry.

    CLI Examples::

        salt '*' pkg.get_repo "myrepo definition"
    '''
    if not apt_support:
        msg = 'Error: aptsources.sourceslist python module not found'
        raise Exception(msg)

    # we have to be clever about this since the repo definition formats
    # are a bit more "loose" than in some other distributions
    if repo.startswith('ppa:') and __grains__['os'] == 'Ubuntu':
        # This is a PPA definition meaning special handling is needed
        # to derive the name.
        if not ppa_format_support:
            error_str = 'cannot parse "ppa:" style repos definitions: {0}'
            raise Exception(error_str.format(repo))
        repo = expand_ppa_line(repo, __grains__['lsb_codename'])[0]

    repos = list_repos()

    if repos:
        try:
            repo_type, repo_uri, repo_dist, repo_comps = _split_repo_str(repo)
        except SyntaxError, e:
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


def del_repo(repo, refresh=False):
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
        if not ppa_format_support:
            error_str = 'Error: cannot parse "ppa:" style repo definition: {0}'
            return error_str.format(repo)
        repo = expand_ppa_line(repo, __grains__['lsb_codename'])[0]

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
                        msg = 'File {1} containing repo "{0}" has been removed.\n'
                        try:
                            os.remove(repo_file)
                        except OSError, e:
                            pass
                ret += msg.format(repo, repo_file)
            if refresh or str(refresh).lower() == 'true':
                refresh_db()
            return ret

    return "Repo {0} doesn't exist in the sources.list(s)".format(repo)


def mod_repo(repo, refresh=False, **kwargs):
    '''
    Modify one or more values for a repo.  If the repo does not exist, it will
    be created, so long as the definition is well formed.  For Ubuntu the
    "ppa:<project>/repo" format is acceptable. "ppa:" format can only be
    used to create a new repository.

    The following options are available to modify a repo definition::

        comps (a comma separated list of components for the repo, e.g. "main")
        file (a file name to be used)
        refresh (refresh the apt sources db when the mod is done)
        keyserver (keyserver to get gpg key from)
        keyid (key id to load with the keyserver argument)
        key_url (URl to a gpg key to add to the apt gpg keyring)
        consolidate (if true, will attempt to de-dup and consolidate sources)

    CLI Examples::

        salt '*' pkg.mod_repo 'myrepo definition' uri=http://new/uri
        salt '*' pkg.mod_repo 'myrepo definition' comps=main,universe
    '''
    if not apt_support:
        raise ImportError('Error: aptsources.sourceslist module not found')

    # to ensure no one sets some key values that _shouldn't_ be changed on the
    # object itself, this is just a white-list of "ok" to set properties
    _MODIFY_OK = set(
        ['uri', 'comps', 'architectures', 'disabled', 'file', 'dist'])
    if repo.startswith('ppa:') and __grains__['os'] == 'Ubuntu':
        if not ppa_format_support:
            error_str = 'cannot parse "ppa:" style repo definitions: {0}'
            raise Exception(error_str.format(repo))
        ppa = expand_ppa_line(repo, __grains__['lsb_codename'])[0]
        cmd = 'apt-add-repository -y {0}'.format(repo)
        out = __salt__['cmd.run_stdout'](cmd)
        if refresh is True or str(refresh).lower() == 'true':
            refresh_db()
        return {repo: out}
    else:
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
        if repos:
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
                output = __salt__['cmd.run_stdout'](cmd)
                imported = output.startswith('-----BEGIN PGP')
                if ks:
                    cmd = 'apt-key export {0}'.format(keyid)
                    output = __salt__['cmd.run_stdout'](cmd)
                    if not imported:
                        cmd = 'apt-key adv --keyserver {0} --logger-fd 1 --recv-keys {1}'
                        out = __salt__['cmd.run_stdout'](cmd.format(keyid, fp))
                        if not out.find('imported') or out.find('not changed'):
                            error_str = 'Error: key retrieval failed: {0}'
                            raise Exception(error_str.format(cmd.format(ks,
                                                                        keyid)))
            elif 'key_url' in kwargs:
                key_url = kwargs.pop('key_url', None)
                cmd = 'wget -q -O- {0} | apt-key add -'.format(key_url)
                out = __salt__['cmd.run_stdout'](cmd)
                if not out.upper().startswith('OK'):
                    error_str = 'Error: key retrieval failed: {0}'
                    raise Exception(error_str.format(cmd.format(key_url)))

            if 'comps' in kwargs:
                kwargs['comps'] = kwargs['comps'].split(',')
                full_comp_list.union(set(kwargs['comps']))
            else:
                kwargs['comps'] = list(full_comp_list)

            if 'architecturess' in kwargs:
                kwargs['architectures'] = kwargs['architectures'].split(',')

            if 'disabled' in kwargs:
                kw_disabled = kwargs['disabled']
                if kw_disabled is True or str(kw_disabled).lower() == 'true':
                    kwargs['disabled'] = True
                else:
                    kwargs['disabled'] = False

            kw_type = kwargs.get('type')
            kw_uri = kwargs.get('uri')
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
                    if type(getattr(mod_source, key)) == type(kwargs[key]):
                        setattr(mod_source, key, kwargs[key])
            sources.save()
            if refresh is True or str(refresh).lower() == 'true':
                refresh_db()
            return {repo: {
                    'architectures': mod_source.architectures,
                    'comps': mod_source.comps,
                    'disabled': mod_source.disabled,
                    'file': mod_source.file,
                    'type': mod_source.type,
                    'uri': mod_source.uri,
                    'line': mod_source.line,
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

'''
Resources needed by pkg providers
'''

# Import python libs
import os
import re
import yaml
import pprint
import logging
import distutils.version

log = logging.getLogger(__name__)


def _parse_pkg_meta(path):
    '''
    Parse metadata from a binary package and return the package's name and
    version number.
    '''
    def parse_rpm(path):
        name = ''
        version = ''
        rel = ''
        result = __salt__['cmd.run_all']('rpm -qpi "{0}"'.format(path))
        if result['retcode'] == 0:
            for line in result['stdout'].splitlines():
                if not name:
                    match = re.match('^Name\s*:\s*(\S+)', line)
                    if match:
                        name = match.group(1)
                        continue
                if not version:
                    match = re.match('^Version\s*:\s*(\S+)', line)
                    if match:
                        version = match.group(1)
                        continue
                if not rel:
                    match = re.match('^Release\s*:\s*(\S+)', line)
                    if match:
                        rel = match.group(1)
                        continue
        if rel:
            version += '-{0}'.format(rel)
        return name, version

    def parse_pacman(path):
        name = ''
        version = ''
        result = __salt__['cmd.run_all']('pacman -Qpi "{0}"'.format(path))
        if result['retcode'] == 0:
            for line in result['stdout'].splitlines():
                if not name:
                    match = re.match('^Name\s*:\s*(\S+)', line)
                    if match:
                        name = match.group(1)
                        continue
                if not version:
                    match = re.match('^Version\s*:\s*(\S+)', line)
                    if match:
                        version = match.group(1)
                        continue
        return name, version

    def parse_deb(path):
        name = ''
        version = ''
        result = __salt__['cmd.run_all']('dpkg-deb -I "{0}"'.format(path))
        if result['retcode'] == 0:
            for line in result['stdout'].splitlines():
                if not name:
                    match = re.match('^\s*Package\s*:\s*(\S+)', line)
                    if match:
                        name = match.group(1)
                        continue
                if not version:
                    match = re.match('^\s*Version\s*:\s*(\S+)', line)
                    if match:
                        version = match.group(1)
                        continue
        return name, version

    if __grains__['os_family'] in ('Suse', 'RedHat', 'Mandriva'):
        metaparser = parse_rpm
    elif __grains__['os_family'] in ('Arch',):
        metaparser = parse_pacman
    elif __grains__['os_family'] in ('Debian',):
        metaparser = parse_deb
    else:
        log.error('No metadata parser found for {0}'.format(path))
        return '', ''

    return metaparser(path)


def pack_pkgs(pkgs):
    '''
    Accepts a list of packages or package/version pairs (or a string
    representing said list) and returns a dict of name/version pairs. For a
    given package, if no version was specified (i.e. the value is a string and
    not a dict, then the dict returned will use None as the value for that
    package.

    Example: '["foo", {"bar": 1.2}, "baz"]' would become
             {'foo': None, 'bar': 1.2, 'baz': None}

    CLI Example::

        salt '*' pkg_resource.pack_pkgs '["foo", {"bar": 1.2}, "baz"]'
    '''
    if isinstance(pkgs, basestring):
        try:
            pkgs = yaml.safe_load(pkgs)
        except yaml.parser.ParserError as err:
            log.error(err)
            return {}
    if not isinstance(pkgs, list) \
            or [x for x in pkgs if not isinstance(x, (basestring, int,
                                                      float, dict))]:
        log.error('Invalid input: {0}'.format(pprint.pformat(pkgs)))
        log.error('Input must be a list of strings/dicts')
        return {}
    ret = {}
    for pkg in pkgs:
        if isinstance(pkg, (basestring, int, float)):
            ret[pkg] = None
        else:
            if len(pkg) != 1:
                log.error('Invalid input: package name/version pairs must '
                          'contain only one element (data passed: '
                          '{0}).'.format(pkg))
                return {}
            ret.update(pkg)
    return dict([(str(x), str(y) if y is not None else y)
                 for x, y in ret.iteritems()])


def pack_sources(sources):
    '''
    Accepts list of dicts (or a string representing a list of dicts) and packs
    the key/value pairs into a single dict.

    Example: '[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]' would
    become {"foo": "salt://foo.rpm", "bar": "salt://bar.rpm"}

    CLI Example::

        salt '*' pkg_resource.pack_sources '[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]'
    '''
    if isinstance(sources, basestring):
        try:
            sources = yaml.safe_load(sources)
        except yaml.parser.ParserError as err:
            log.error(err)
            return {}
    ret = {}
    for source in sources:
        if (not isinstance(source, dict)) or len(source) != 1:
            log.error('Invalid input: {0}'.format(pprint.pformat(sources)))
            log.error('Input must be a list of 1-element dicts')
            return {}
        else:
            ret.update(source)
    return ret


def _verify_binary_pkg(srcinfo):
    '''
    Compares package files (s) against the metadata to confirm that they match
    what is expected.
    '''
    problems = []
    for pkg_name, pkg_uri, pkg_path, pkg_type in srcinfo:
        pkgmeta_name, pkgmeta_version = _parse_pkg_meta(pkg_path)
        if not pkgmeta_name:
            if pkg_type == 'remote':
                problems.append('Failed to cache {0}. Are you sure this '
                                'path is correct?'.format(pkg_uri))
            elif pkg_type == 'local':
                if not os.path.isfile(pkg_path):
                    problems.append('Package file {0} not found. Are '
                                    'you sure this path is '
                                    'correct?'.format(pkg_path))
                else:
                    problems.append('Unable to parse package metadata for '
                                    '{0}.'.format(pkg_path))
        elif pkg_name != pkgmeta_name:
            problems.append('Package file {0} (Name: {1}) does not '
                            'match the specified package name '
                            '({2}).'.format(pkg_uri, pkgmeta_name, pkg_name))
    return problems


def check_desired(desired=None):
    '''
    Examines desired package names to make sure they were formatted properly.
    Returns a list of problems encountered.

    CLI Examples::

        salt '*' pkg_resource.check_desired
    '''
    problems = []

    # If minion is Gentoo-based, ensure packages are properly submitted as
    # category/pkgname. For any package that does not follow this format, offer
    # matches from the portage tree.
    if __grains__['os_family'] == 'Gentoo':
        for pkg in (desired or []):
            if '/' not in pkg:
                matches = __salt__['pkg.porttree_matches'](pkg)
                if matches:
                    msg = 'Package category missing for "{0}" (possible ' \
                          'matches: {1}).'.format(pkg, ', '.join(matches))
                else:
                    msg = 'Package category missing for "{0}" and no match ' \
                          'found in portage tree.'.format(pkg)
                log.error(msg)
                problems.append(msg)

    return problems


def parse_targets(name=None, pkgs=None, sources=None):
    '''
    Parses the input to pkg.install and returns back the package(s) to be
    installed. Returns a list of packages, as well as a string noting whether
    the packages are to come from a repository or a binary package.

    CLI Example::

        salt '*' pkg_resource.parse_targets
    '''

    # For Solaris, there is no repository, and only the "sources" param can be
    # used. Warn if "name" or "pkgs" is provided, and require that "sources" is
    # present.
    if __grains__['os_family'] == 'Solaris':
        if name:
            log.warning('Parameter "name" ignored on Solaris hosts.')
        if pkgs:
            log.warning('Parameter "pkgs" ignored on Solaris hosts.')
        if not sources:
            log.error('"sources" option required with Solaris pkg installs')
            return None, None
    elif __grains__['os'] == 'MacOS' and sources:
        log.warning('Parameter "sources" ignored on MacOS hosts.')

    # "pkgs" is always ignored on Solaris.
    if pkgs and sources and __grains__['os_family'] != 'Solaris':
        log.error('Only one of "pkgs" and "sources" can be used.')
        return None, None

    elif pkgs and __grains__['os_family'] != 'Solaris':
        if name:
            log.warning('"name" parameter will be ignored in favor of "pkgs"')
        pkgs = pack_pkgs(pkgs)
        if not pkgs:
            return None, None
        else:
            return pkgs, 'repository'

    elif sources and __grains__['os'] != 'MacOS':
        # No need to warn for Solaris, warning taken care of above.
        if name and __grains__['os_family'] != 'Solaris':
            log.warning('"name" parameter will be ignored in favor of '
                        '"sources".')
        sources = pack_sources(sources)
        if not sources:
            return None, None

        srcinfo = []
        for pkg_name, pkg_src in sources.iteritems():
            if __salt__['config.valid_fileproto'](pkg_src):
                # Cache package from remote source (salt master, http, ftp)
                srcinfo.append((pkg_name,
                                pkg_src,
                               __salt__['cp.cache_file'](pkg_src),
                               'remote'))
            else:
                # Package file local to the minion
                srcinfo.append((pkg_name, pkg_src, pkg_src, 'local'))

        # Check metadata to make sure the name passed matches the source
        if __grains__['os_family'] not in ('Solaris',) \
                and __grains__['os'] not in ('Gentoo', 'OpenBSD', 'FreeBSD'):
            problems = _verify_binary_pkg(srcinfo)
            # If any problems are found in the caching or metadata parsing done
            # in the above for loop, log each problem and return None,None,
            # which will keep package installation from proceeding.
            if problems:
                for problem in problems:
                    log.error(problem)
                return None, None

        # srcinfo is a 4-tuple (pkg_name,pkg_uri,pkg_path,pkg_type), so grab
        # the package path (3rd element of tuple).
        return [x[2] for x in srcinfo], 'file'

    elif name and __grains__['os_family'] != 'Solaris':
        return {name: None}, 'repository'

    else:
        log.error('No package sources passed to pkg.install.')
        return None, None


def version(*names, **kwargs):
    '''
    Common interface for obtaining the version of installed packages

    CLI Example::

        salt '*' pkg_resource.version vim
    '''
    ret = {}
    versions_as_list = \
        __salt__['config.is_true'](kwargs.get('versions_as_list'))
    if len(names) != 0:
        pkgs = __salt__['pkg.list_pkgs'](versions_as_list=True)
        for name in names:
            ret[name] = pkgs.get(name, [])
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    # Return a single value if only one package name was passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


def add_pkg(pkgs, name, version):
    '''
    Add a package to a dict of installed packages.

    CLI Example::

        salt '*' pkg_resource.add_pkg '{}' bind 9
    '''
    try:
        pkgs.setdefault(name, []).append(version)
    except AttributeError as e:
        log.exception(e)


def sort_pkglist(pkgs):
    '''
    Accepts a dict obtained from pkg.list_pkgs() and sorts in place the list of
    versions for any packages that have multiple versions installed, so that
    two package lists can be compared to one another.

    CLI Example::

        salt '*' pkg_resource.sort_pkglist '["3.45", "2.13"]'
    '''
    # It doesn't matter that ['4.9','4.10'] would be sorted to ['4.10','4.9'],
    # so long as the sorting is consistent.
    try:
        for key in pkgs.keys():
            pkgs[key].sort()
    except AttributeError as e:
        log.exception(e)


def stringify(pkgs):
    '''
    Takes a dict of package name/version information and joins each list of
    installed versions into a string.

    CLI Example::

        salt '*' pkg_resource.stringify 'vim: 7.127'
    '''
    try:
        for key in pkgs.keys():
            pkgs[key] = ','.join(pkgs[key])
    except AttributeError as e:
        log.exception(e)


def find_changes(old=None, new=None):
    '''
    Compare before and after results from pkg.list_pkgs() to determine what
    changes were made to the packages installed on the minion.

    CLI Example::

        salt '*' pkg_resource.find_changes
    '''
    pkgs = {}
    for npkg in set((new or {}).keys()).union((old or {}).keys()):
        if npkg not in old:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
        elif npkg not in new:
            # the package is removed
            pkgs[npkg] = {'new': '',
                          'old': old[npkg]}
        elif new[npkg] != old[npkg]:
            # the package was here before and the version has changed
            pkgs[npkg] = {'old': old[npkg],
                          'new': new[npkg]}
    return pkgs


def perform_cmp(pkg1='', pkg2=''):
    '''
    Compares two version strings using distutils.version.LooseVersion. This is
    a fallback for providers which don't have a version comparison utility
    built into them.  Return -1 if version1 < version2, 0 if version1 ==
    version2, and 1 if version1 > version2. Return None if there was a problem
    making the comparison.

    CLI Example::

        salt '*' pkg_resource.perform_cmp
    '''
    try:
        if distutils.version.LooseVersion(pkg1) < \
                distutils.version.LooseVersion(pkg2):
            return -1
        elif distutils.version.LooseVersion(pkg1) == \
                distutils.version.LooseVersion(pkg2):
            return 0
        elif distutils.version.LooseVersion(pkg1) > \
                distutils.version.LooseVersion(pkg2):
            return 1
    except Exception as e:
        log.exception(e)
    return None


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Package version comparison function.

    CLI Example::

        salt '*' pkg_resource.compare
    '''
    cmp_map = {'<': (-1,), '<=': (-1, 0), '==': (0,),
               '>=': (0, 1), '>': (1,)}
    if oper not in ['!='] + cmp_map.keys():
        log.error('Invalid operator "{0}" for package '
                  'comparison'.format(oper))
        return False

    cmp_result = __salt__['pkg.perform_cmp'](pkg1, pkg2)
    if cmp_result is None:
        return False

    if oper == '!=':
        return cmp_result not in cmp_map['==']
    else:
        return cmp_result in cmp_map[oper]

'''
Resources needed by pkg providers
'''

import logging
import os
import re
from pprint import pformat
from types import StringTypes

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
                    m = re.match('^Name\s*:\s*(\S+)', line)
                    if m:
                        name = m.group(1)
                        continue
                if not version:
                    m = re.match('^Version\s*:\s*(\S+)', line)
                    if m:
                        version = m.group(1)
                        continue
                if not rel:
                    m = re.match('^Release\s*:\s*(\S+)', line)
                    if m:
                        version = m.group(1)
                        continue
        if rel:
            version += '-{0}'.format(rel)
        return name,version

    def parse_pacman(path):
        name = ''
        version = ''
        result = __salt__['cmd.run_all']('pacman -Qpi "{0}"'.format(path))
        if result['retcode'] == 0:
            for line in result['stdout'].splitlines():
                if not name:
                    m = re.match('^Name\s*:\s*(\S+)',line)
                    if m:
                        name = m.group(1)
                        continue
                if not version:
                    m = re.match('^Version\s*:\s*(\S+)',line)
                    if m:
                        version = m.group(1)
                        continue
        return name,version

    def parse_deb(path):
        # Need to add support for this once apt gets some multi-source love
        pass

    if __grains__['os_family'] in ('Suse','RedHat','Mandriva'):
        metaparser = parse_rpm
    elif __grains__['os_family'] in ('Arch'):
        metaparser = parse_pacman
    elif __grains__['os_family'] in ('Debian'):
        metaparser = parse_deb
    else:
        log.error('No metadata parser found for {0}'.format(path))
        return '',''

    return metaparser(path)


def _pack_pkgs(sources):
    '''
    Accepts list (or a string representing a list) and returns back either the
    list passed, or the list represenation of the string passed.

    Example: '["foo","bar","baz"]' would become ["foo","bar","baz"]
    '''
    if type(sources) in StringTypes:
        try:
            # Safely eval the string data into a list
            sources = eval(sources,{'__builtins__': None},{})
        except Exception as e:
            log.error(e)
            return []
    if not isinstance(sources,list) \
    or [x for x in sources if type(x) not in StringTypes]:
        log.error('Invalid input: {0}'.format(pformat(source)))
        return []
    return sources


def _pack_sources(sources):
    '''
    Accepts list of dicts (or a string representing a list of dicts) and packs
    the key/value pairs into a single dict.

    Example: '[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]' would
    become {"foo": "salt://foo.rpm", "bar": "salt://bar.rpm"}
    '''
    if type(sources) in StringTypes:
        try:
            # Safely eval the string data into a list of dicts
            sources = eval(sources,{'__builtins__': None},{})
        except Exception as e:
            log.error(e)
            return {}
    ret = {}
    for source in sources:
        if (not isinstance(source,dict)) or len(source) != 1:
            log.error('Invalid input: {0}'.format(pformat(sources)))
            return {}
        else:
            ret.update(source)
    return ret


def parse_targets(name=None, pkgs=None, sources=None):
    '''
    Parses the input to pkg.install and returns back the package(s) to be
    installed. Returns a list of packages, as well as a string noting whether
    the packages are to come from a repository or a binary package.
    '''
    if pkgs and sources:
        log.error('Only one of "pkgs" and "sources" can be used.')
        return None,None
    elif pkgs:
        if name:
            log.warning('"name" parameter will be ignored in favor of "pkgs"')
        pkgs = _pack_pkgs(pkgs)
        if not pkgs:
            return None,None
        else:
            return pkgs,'repository'
    elif sources:
        if name:
            log.warning('"name" parameter will be ignored in favor of '
                        '"sources".')
        sources = _pack_sources(sources)
        if not sources:
            return None,None

        srcinfo = []
        for pkg_name,pkg_src in sources.iteritems():
            if __salt__['config.valid_fileproto'](pkg_src):
                # Cached RPM from master
                srcinfo.append((pkg_name,
                                pkg_src,
                               __salt__['cp.cache_file'](pkg_src),
                               'remote'))
            else:
                # RPM file local to the minion
                srcinfo.append((pkg_name,pkg_src,pkg_src,'local'))

        # Check metadata to make sure the name passed matches the source
        problems = []
        for pkg_name,pkg_uri,pkg_path,pkg_type in srcinfo:
            pkgmeta_name,pkgmeta_version = _parse_pkg_meta(pkg_path)
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
                                '({2}).'.format(pkg_uri,pkgmeta_name,pkg_name))

        # If any problems are found in the caching or metadata parsing done in
        # the above for loop, log each problem and then return an empty dict.
        # Do not proceed to attempt package installation.
        if problems:
            for problem in problems: log.error(problem)
            return None,None

        # srcinfo is a 4-tuple (pkg_name,pkg_uri,pkg_path,pkg_type), so grab
        # the path (3rd element of tuple).
        return [x[2] for x in srcinfo],'file'

    elif name:
        return [name],'repository'
    else:
        log.error('No package sources passed to pkg.install.')
        return None,None


def find_changes(old={}, new={}):
    '''
    Compare before and after results from pkg.list_pkgs() to determine what
    changes were made to the packages installed on the minion.
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

# -*- coding: utf-8 -*-
'''
Resources needed by pkg providers
'''

# Import python libs
import fnmatch
import logging
import os
import pprint
import re
import sys
import yaml

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def _parse_pkg_meta(path):
    '''
    Parse metadata from a binary package and return the package's name and
    version number.
    '''
    def parse_rpm(path):
        try:
            import collections  # needed by _parse_pkginfo, DO NOT REMOVE
            from salt.modules.yumpkg5 import __QUERYFORMAT, _parse_pkginfo
            from salt.utils import namespaced_function as _namespaced_function
            _parse_pkginfo = _namespaced_function(_parse_pkginfo, globals())
        except ImportError:
            log.critical('Error importing helper functions. This is almost '
                         'certainly a bug.')
            return '', ''
        pkginfo = __salt__['cmd.run_all'](
            'rpm -qp --queryformat {0!r} {1!r}'.format(__QUERYFORMAT, path)
        ).get('stdout', '').strip()
        pkginfo = _parse_pkginfo(pkginfo)
        if pkginfo is None:
            return '', ''
        else:
            return pkginfo.name, pkginfo.version

    def parse_pacman(path):
        name = ''
        version = ''
        result = __salt__['cmd.run_all']('pacman -Qpi "{0}"'.format(path))
        if result['retcode'] == 0:
            for line in result['stdout'].splitlines():
                if not name:
                    match = re.match(r'^Name\s*:\s*(\S+)', line)
                    if match:
                        name = match.group(1)
                        continue
                if not version:
                    match = re.match(r'^Version\s*:\s*(\S+)', line)
                    if match:
                        version = match.group(1)
                        continue
        return name, version

    def parse_deb(path):
        name = ''
        version = ''
        arch = ''
        # This is ugly, will have to try to find a better way of accessing the
        # __grains__ global.
        cpuarch = sys.modules[
            __salt__['test.ping'].__module__
        ].__grains__.get('cpuarch', '')
        osarch = sys.modules[
            __salt__['test.ping'].__module__
        ].__grains__.get('osarch', '')

        result = __salt__['cmd.run_all']('dpkg-deb -I "{0}"'.format(path))
        if result['retcode'] == 0:
            for line in result['stdout'].splitlines():
                if not name:
                    try:
                        name = re.match(
                            r'^\s*Package\s*:\s*(\S+)',
                            line
                        ).group(1)
                    except AttributeError:
                        continue
                if not version:
                    try:
                        version = re.match(
                            r'^\s*Version\s*:\s*(\S+)',
                            line
                        ).group(1)
                    except AttributeError:
                        continue
                if cpuarch == 'x86_64' and not arch:
                    try:
                        arch = re.match(
                            r'^\s*Architecture\s*:\s*(\S+)',
                            line
                        ).group(1)
                    except AttributeError:
                        continue
        if arch and cpuarch == 'x86_64':
            if arch != 'all' and osarch == 'amd64' and osarch != arch:
                name += ':{0}'.format(arch)
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


def _repack_pkgs(pkgs):
    '''
    Repack packages specified using "pkgs" argument to pkg states into a single
    dictionary
    '''
    return dict(
        [
            (str(x), str(y) if y is not None else y)
            for x, y in salt.utils.repack_dictlist(pkgs).iteritems()
        ]
    )


def pack_sources(sources):
    '''
    Accepts list of dicts (or a string representing a list of dicts) and packs
    the key/value pairs into a single dict.

    ``'[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]'`` would become
    ``{"foo": "salt://foo.rpm", "bar": "salt://bar.rpm"}``

    CLI Example:

    .. code-block:: bash

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


def parse_targets(name=None, pkgs=None, sources=None, **kwargs):
    '''
    Parses the input to pkg.install and returns back the package(s) to be
    installed. Returns a list of packages, as well as a string noting whether
    the packages are to come from a repository or a binary package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg_resource.parse_targets
    '''
    if __grains__['os'] == 'MacOS' and sources:
        log.warning('Parameter "sources" ignored on MacOS hosts.')

    if pkgs and sources:
        log.error('Only one of "pkgs" and "sources" can be used.')
        return None, None

    elif pkgs:
        pkgs = _repack_pkgs(pkgs)
        if not pkgs:
            return None, None
        else:
            return pkgs, 'repository'

    elif sources and __grains__['os'] != 'MacOS':
        sources = pack_sources(sources)
        if not sources:
            return None, None

        srcinfo = []
        for pkg_name, pkg_src in sources.iteritems():
            if __salt__['config.valid_fileproto'](pkg_src):
                # Cache package from remote source (salt master, HTTP, FTP)
                srcinfo.append((pkg_name,
                                pkg_src,
                               __salt__['cp.cache_file'](pkg_src,
                                                         kwargs.get('__env__',
                                                                    'base')),
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

    elif name:
        return dict([(x, None) for x in name.split(',')]), 'repository'

    else:
        log.error('No package sources passed to pkg.install.')
        return None, None


def version(*names, **kwargs):
    '''
    Common interface for obtaining the version of installed packages.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg_resource.version vim
        salt '*' pkg_resource.version foo bar baz
        salt '*' pkg_resource.version 'python*'
    '''
    ret = {}
    versions_as_list = \
        salt.utils.is_true(kwargs.get('versions_as_list'))
    pkg_glob = False
    if len(names) != 0:
        pkgs = __salt__['pkg.list_pkgs'](versions_as_list=True)
        for name in names:
            if '*' in name:
                pkg_glob = True
                for match in fnmatch.filter(pkgs.keys(), name):
                    ret[match] = pkgs.get(match, [])
            else:
                ret[name] = pkgs.get(name, [])
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    # Return a string if no globbing is used, and there is one item in the
    # return dict
    if len(ret) == 1 and not pkg_glob:
        try:
            return ret.values()[0]
        except IndexError:
            return ''
    return ret


def add_pkg(pkgs, name, version):
    '''
    Add a package to a dict of installed packages.

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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


def version_clean(version):
    '''
    Clean the version string removing extra data.
    This function will simply try to call ``pkg.version_clean``.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg_resource.version_clean <version_string>
    '''
    if version and 'pkg.version_clean' in __salt__:
        return __salt__['pkg.version_clean'](version)

    return version


def check_extra_requirements(pkgname, pkgver):
    '''
    Check if the installed package already has the given requirements.
    This function will simply try to call "pkg.check_extra_requirements".

    CLI Example:

    .. code-block:: bash

        salt '*' pkg_resource.check_extra_requirements <pkgname> <extra_requirements>
    '''
    if pkgver and 'pkg.check_extra_requirements' in __salt__:
        return __salt__['pkg.check_extra_requirements'](pkgname, pkgver)

    return True

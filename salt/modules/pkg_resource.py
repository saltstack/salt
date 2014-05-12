# -*- coding: utf-8 -*-
'''
Resources needed by pkg providers
'''

# Import python libs
import fnmatch
import logging
import pprint

# Import third party libs
import yaml

# Import salt libs
import salt.utils
from salt._compat import string_types

log = logging.getLogger(__name__)
__SUFFIX_NOT_NEEDED = ('x86_64', 'noarch')


def _repack_pkgs(pkgs):
    '''
    Repack packages specified using "pkgs" argument to pkg states into a single
    dictionary
    '''
    _normalize_name = __salt__.get('pkg.normalize_name', lambda pkgname: pkgname)
    return dict(
        [
            (_normalize_name(str(x)), str(y) if y is not None else y)
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
    _normalize_name = __salt__.get('pkg.normalize_name', lambda pkgname: pkgname)
    if isinstance(sources, string_types):
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
            key = next(iter(source))
            ret[_normalize_name(key)] = source[key]
    return ret


def parse_targets(name=None,
                  pkgs=None,
                  sources=None,
                  saltenv='base',
                  **kwargs):
    '''
    Parses the input to pkg.install and returns back the package(s) to be
    installed. Returns a list of packages, as well as a string noting whether
    the packages are to come from a repository or a binary package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg_resource.parse_targets
    '''
    if '__env__' in kwargs:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'__env__\'. This functionality will be removed in Salt '
            'Boron.'
        )
        # Backwards compatibility
        saltenv = kwargs['__env__']

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
                               __salt__['cp.cache_file'](pkg_src, saltenv),
                               'remote'))
            else:
                # Package file local to the minion
                srcinfo.append((pkg_name, pkg_src, pkg_src, 'local'))

        # srcinfo is a 4-tuple (pkg_name,pkg_uri,pkg_path,pkg_type), so grab
        # the package path (3rd element of tuple).
        return [x[2] for x in srcinfo], 'file'

    elif name:
        _normalize_name = \
            __salt__.get('pkg.normalize_name', lambda pkgname: pkgname)
        packed = dict([(_normalize_name(x), None) for x in name.split(',')])
        return packed, 'repository'

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
        salt.utils.is_true(kwargs.pop('versions_as_list', False))
    pkg_glob = False
    if len(names) != 0:
        pkgs = __salt__['pkg.list_pkgs'](versions_as_list=True, **kwargs)
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
            # Passing the pkglist to set() also removes duplicate version
            # numbers (if present).
            pkgs[key] = sorted(set(pkgs[key]))
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

# -*- coding: utf-8 -*-
'''
Support for MacPorts under MacOSX
'''

# Import python libs
import copy
import logging
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

LIST_ACTIVE_ONLY = True

__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confine this module to Mac OS with MacPorts.
    '''

    if salt.utils.which('port') and __grains__['os'] == 'MacOS':
        return __virtualname__
    return False


def _list(query=''):
    ret = {}
    cmd = 'port list {0}'.format(query)
    out = __salt__['cmd.run'](cmd, output_loglevel='trace')
    for line in out.splitlines():
        try:
            name, version_num, category = re.split(r'\s+', line.lstrip())[0:3]
            version_num = version_num[1:]
        except ValueError:
            continue
        ret[name] = version_num

    return ret


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
    cmd = 'port installed'
    out = __salt__['cmd.run'](cmd, output_loglevel='trace')
    for line in out.splitlines():
        try:
            name, version_num, active = re.split(r'\s+', line.lstrip())[0:3]
            version_num = version_num[1:]
        except ValueError:
            continue
        if not LIST_ACTIVE_ONLY or active == '(active)':
            __salt__['pkg_resource.add_pkg'](ret, name, version_num)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3>
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation

    Options:

    refresh
        Update ports with ``port selfupdate``

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3>
    '''

    if salt.utils.is_true(kwargs.get('refresh', True)):
        refresh_db()

    available = _list(' '.join(names)) or {}
    installed = __salt__['pkg.list_pkgs']() or {}

    ret = {}

    for k, v in available.items():
        if k not in installed or salt.utils.compare_versions(ver1=installed[k], oper='<', ver2=v):
            ret[k] = v
        else:
            ret[k] = ''

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]

    return ret

# available_version is being deprecated
available_version = latest_version


def remove(name=None, pkgs=None, **kwargs):
    '''
    Removes packages with ``port uninstall``.

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
    pkg_params = __salt__['pkg_resource.parse_targets'](name,
                                                        pkgs,
                                                        **kwargs)[0]
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = 'port uninstall {0}'.format(' '.join(targets))
    __salt__['cmd.run_all'](cmd, output_loglevel='trace')
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def install(name=None, refresh=False, pkgs=None, **kwargs):
    '''
    Install the passed package(s) with ``port install``

    name
        The name of the formula to be installed. Note that this parameter is
        ignored if "pkgs" is passed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    version
        Specify a version to pkg to install. Ignored if pkgs is specified.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>
            salt '*' pkg.install git-core version='1.8.5.5'

    variant
        Specify a variant to pkg to install. Ignored if pkgs is specified.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>
            salt '*' pkg.install git-core version='1.8.5.5' variant='+credential_osxkeychain+doc+pcre'

    Multiple Package Installation Options:

    pkgs
        A list of formulas to install. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo","bar"]'
            salt '*' pkg.install pkgs='["foo@1.2","bar"]'
            salt '*' pkg.install pkgs='["foo@1.2+ssl","bar@2.3"]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install 'package package package'
    '''
    pkg_params, pkg_type = \
        __salt__['pkg_resource.parse_targets'](name,
                                               pkgs,
                                               {})

    if salt.utils.is_true(refresh):
        refresh_db()

    # Handle version kwarg for a single package target
    if pkgs is None:
        version_num = kwargs.get('version')
        variant_spec = kwargs.get('variant')
        spec = None

        if version_num:
            spec = (spec or '') + '@' + version_num

        if variant_spec:
            spec = (spec or '') + variant_spec

        pkg_params = {name: spec}

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    formulas_array = []
    for pname, pparams in pkg_params.items():
        formulas_array.append(pname + (pparams or ''))

    formulas = ' '.join(formulas_array)

    old = list_pkgs()
    cmd = 'port install {0}'.format(formulas)

    __salt__['cmd.run'](cmd, output_loglevel='trace')
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def list_upgrades(refresh=True):
    '''
    Check whether or not an upgrade is available for all packages

    Options:

    refresh
        Update ports with ``port selfupdate``

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''

    if refresh:
        refresh_db()
    return _list('outdated')


def upgrade_available(pkg, refresh=True):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return pkg in list_upgrades(refresh=refresh)


def refresh_db():
    '''
    Update ports with ``port selfupdate``
    '''
    __salt__['cmd.run_all']('port selfupdate', output_loglevel='trace')


def upgrade(refresh=True):
    '''
    Run a full upgrade

    Options:

    refresh
        Update ports with ``port selfupdate``

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''

    old = list_pkgs()

    for pkg in list_upgrades(refresh=refresh):
        __salt__['pkg.install'](pkg)

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)

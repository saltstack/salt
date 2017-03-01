# -*- coding: utf-8 -*-
'''
Support for Opkg

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

.. versionadded: 2016.3.0

.. note::

    For version comparison support on opkg < 0.3.4, the ``opkg-utils`` package
    must be installed.

'''
from __future__ import absolute_import

# Import python libs
import copy
import os
import re
import logging
import distutils.version
from salt.ext import six
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils
import salt.utils.itertools

from salt.exceptions import (
    CommandExecutionError, MinionError, SaltInvocationError
)

REPO_REGEXP = r'^#?\s*(src|src/gz)\s+([^\s<>]+|"[^<>]+")\s+[^\s<>]+'
OPKG_CONFDIR = '/etc/opkg'
ATTR_MAP = {
    'Architecture': 'arch',
    'Homepage': 'url',
    'Installed-Time': 'install_date_time_t',
    'Maintainer': 'packager',
    'Package': 'name',
    'Section': 'group'
}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confirm this module is on a nilrt based system
    '''
    if __grains__.get('os_family', False) == 'NILinuxRT':
        return __virtualname__
    return (False, "Module opkg only works on nilrt based systems")


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', True))

    if len(names) == 0:
        return ''

    ret = {}
    for name in names:
        ret[name] = ''

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    cmd = ['opkg', 'list-upgradable']
    out = __salt__['cmd.run_stdout'](cmd,
                                     output_loglevel='trace',
                                     python_shell=False)
    for line in salt.utils.itertools.split(out, '\n'):
        try:
            name, _oldversion, newversion = line.split(' - ')
            if name in names:
                ret[name] = newversion
        except ValueError:
            pass

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

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def refresh_db():
    '''
    Updates the opkg database to latest packages based upon repositories

    Returns a dict, with the keys being package databases and the values being
    the result of the update attempt. Values can be one of the following:

    - ``True``: Database updated successfully
    - ``False``: Problem updating database

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    ret = {}
    cmd = ['opkg', 'update']
    call = __salt__['cmd.run_all'](cmd,
                                   output_loglevel='trace',
                                   python_shell=False)
    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += call['stderr']

        raise CommandExecutionError(
            '{0}'.format(comment)
        )
    else:
        out = call['stdout']

    for line in salt.utils.itertools.split(out, '\n'):
        if 'Inflating' in line:
            key = line.strip().split()[1].split('.')[0]
            ret[key] = True
        elif 'Failed to download' in line:
            key = line.strip().split()[5].split(',')[0]
            ret[key] = False
    return ret


def install(name=None,
            refresh=False,
            pkgs=None,
            sources=None,
            reinstall=False,
            **kwargs):
    '''
    Install the passed package, add refresh=True to update the opkg database.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    version
        Install a specific version of the package, e.g. 1.2.3~0ubuntu0. Ignored
        if "pkgs" or "sources" is passed.

        .. versionadded:: Nitrogen

    reinstall : False
        Specifying reinstall=True will use ``opkg install --force-reinstall``
        rather than simply ``opkg install`` for requested packages that are
        already installed.

        If a version is specified with the requested package, then ``opkg
        install --force-reinstall`` will only be used if the installed version
        matches the requested version.

        .. versionadded:: Nitrogen


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-0ubuntu0"}]'

    sources
        A list of IPK packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.  Dependencies are automatically resolved
        and marked as auto-installed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    install_recommends
        Whether to install the packages marked as recommended. Default is True.

    only_upgrade
        Only upgrade the packages (disallow downgrades), if they are already
        installed. Default is False.

        .. versionadded:: Nitrogen

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    refreshdb = salt.utils.is_true(refresh)

    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    cmd_prefix = ['opkg', 'install']
    to_install = []
    to_reinstall = []
    to_downgrade = []

    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        if reinstall:
            cmd_prefix.append('--force-reinstall')
        if not kwargs.get('only_upgrade', False):
            cmd_prefix.append('--force-downgrade')
        to_install.extend(pkg_params)
    elif pkg_type == 'repository':
        if not kwargs.get('install_recommends', True):
            cmd_prefix.append('--no-install-recommends')
        for pkgname, pkgversion in six.iteritems(pkg_params):
            if (name and pkgs is None and kwargs.get('version') and
                    len(pkg_params) == 1):
                # Only use the 'version' param if 'name' was not specified as a
                # comma-separated list
                version_num = kwargs['version']
            else:
                version_num = pkgversion

            if version_num is None:
                # Don't allow downgrades if the version
                # number is not specified.
                if reinstall and pkgname in old:
                    to_reinstall.append(pkgname)
                else:
                    to_install.append(pkgname)
            else:
                pkgstr = '{0}={1}'.format(pkgname, version_num)
                cver = old.get(pkgname, '')
                if reinstall and cver and salt.utils.compare_versions(
                        ver1=version_num,
                        oper='==',
                        ver2=cver,
                        cmp_func=version_cmp):
                    to_reinstall.append(pkgstr)
                elif not cver or salt.utils.compare_versions(
                        ver1=version_num,
                        oper='>=',
                        ver2=cver,
                        cmp_func=version_cmp):
                    to_install.append(pkgstr)
                else:
                    if not kwargs.get('only_upgrade', False):
                        to_downgrade.append(pkgstr)
                    else:
                        # This should cause the command to fail.
                        to_install.append(pkgstr)

    cmds = []

    if to_install:
        cmd = copy.deepcopy(cmd_prefix)
        cmd.extend(to_install)
        cmds.append(cmd)

    if to_downgrade:
        cmd = copy.deepcopy(cmd_prefix)
        cmd.append('--force-downgrade')
        cmd.extend(to_downgrade)
        cmds.append(cmd)

    if to_reinstall:
        cmd = copy.deepcopy(cmd_prefix)
        cmd.append('--force-reinstall')
        cmd.extend(to_reinstall)
        cmds.append(cmd)

    if not cmds:
        return {}

    if refreshdb:
        refresh_db()

    errors = []
    for cmd in cmds:
        out = __salt__['cmd.run_all'](
            cmd,
            output_loglevel='trace',
            python_shell=False
        )
        if out['retcode'] != 0 and out['stderr']:
            errors.append(out['stderr'])

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered installing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def remove(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
    '''
    Remove packages using ``opkg remove``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = ['opkg', 'remove']
    cmd.extend(targets)

    out = __salt__['cmd.run_all'](
        cmd,
        output_loglevel='trace',
        python_shell=False
    )
    if out['retcode'] != 0 and out['stderr']:
        errors = [out['stderr']]
    else:
        errors = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered removing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def purge(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
    '''
    Package purges are not supported by opkg, this function is identical to
    :mod:`pkg.remove <salt.modules.opkg.remove>`.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs)


def upgrade(refresh=True):
    '''
    Upgrades all packages via ``opkg upgrade``

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    ret = {'changes': {},
           'result': True,
           'comment': '',
           }

    if salt.utils.is_true(refresh):
        refresh_db()

    old = list_pkgs()

    cmd = ['opkg', 'upgrade']
    result = __salt__['cmd.run_all'](cmd,
                                     output_loglevel='trace',
                                     python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if result['retcode'] != 0:
        raise CommandExecutionError(
            'Problem encountered upgrading packages',
            info={'changes': ret, 'result': result}
        )

    return ret


def hold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    '''
    Set package in 'hold' state, meaning it will not be upgraded.

    name
        The name of the package, e.g., 'tmux'

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.hold <package name>

    pkgs
        A list of packages to hold. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.hold pkgs='["foo", "bar"]'
    '''
    if not name and not pkgs and not sources:
        raise SaltInvocationError(
            'One of name, pkgs, or sources must be specified.'
        )
    if pkgs and sources:
        raise SaltInvocationError(
            'Only one of pkgs or sources can be specified.'
        )

    targets = []
    if pkgs:
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {'name': target,
                       'changes': {},
                       'result': False,
                       'comment': ''}

        state = _get_state(target)
        if not state:
            ret[target]['comment'] = ('Package {0} not currently held.'
                                      .format(target))
        elif state != 'hold':
            if 'test' in __opts__ and __opts__['test']:
                ret[target].update(result=None)
                ret[target]['comment'] = ('Package {0} is set to be held.'
                                          .format(target))
            else:
                result = _set_state(target, 'hold')
                ret[target].update(changes=result[target], result=True)
                ret[target]['comment'] = ('Package {0} is now being held.'
                                          .format(target))
        else:
            ret[target].update(result=True)
            ret[target]['comment'] = ('Package {0} is already set to be held.'
                                      .format(target))
    return ret


def unhold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    '''
    Set package current in 'hold' state to install state,
    meaning it will be upgraded.

    name
        The name of the package, e.g., 'tmux'

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unhold <package name>

    pkgs
        A list of packages to hold. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unhold pkgs='["foo", "bar"]'
    '''
    if not name and not pkgs and not sources:
        raise SaltInvocationError(
            'One of name, pkgs, or sources must be specified.'
        )
    if pkgs and sources:
        raise SaltInvocationError(
            'Only one of pkgs or sources can be specified.'
        )

    targets = []
    if pkgs:
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {'name': target,
                       'changes': {},
                       'result': False,
                       'comment': ''}

        state = _get_state(target)
        if not state:
            ret[target]['comment'] = ('Package {0} does not have a state.'
                                      .format(target))
        elif state == 'hold':
            if 'test' in __opts__ and __opts__['test']:
                ret[target].update(result=None)
                ret['comment'] = ('Package {0} is set not to be held.'
                                  .format(target))
            else:
                result = _set_state(target, 'ok')
                ret[target].update(changes=result[target], result=True)
                ret[target]['comment'] = ('Package {0} is no longer being '
                                          'held.'.format(target))
        else:
            ret[target].update(result=True)
            ret[target]['comment'] = ('Package {0} is already set not to be '
                                      'held.'.format(target))
    return ret


def _get_state(pkg):
    '''
    View package state from the opkg database

    Return the state of pkg
    '''
    cmd = ['opkg', 'status']
    cmd.append(pkg)
    out = __salt__['cmd.run'](cmd, python_shell=False)
    state_flag = ''
    for line in salt.utils.itertools.split(out, '\n'):
        if line.startswith('Status'):
            _status, _state_want, state_flag, _state_status = line.split()

    return state_flag


def _set_state(pkg, state):
    '''
    Change package state on the opkg database

    The state can be any of:

     - hold
     - noprune
     - user
     - ok
     - installed
     - unpacked

    This command is commonly used to mark a specific package to be held from
    being upgraded, that is, to be kept at a certain version.

    Returns a dict containing the package name, and the new and old
    versions.
    '''
    ret = {}
    valid_states = ('hold', 'noprune', 'user', 'ok', 'installed', 'unpacked')
    if state not in valid_states:
        raise SaltInvocationError(
            'Invalid state: {0}'.format(state)
        )
    oldstate = _get_state(pkg)
    cmd = ['opkg', 'flag']
    cmd.append(state)
    cmd.append(pkg)
    _out = __salt__['cmd.run'](cmd, python_shell=False)

    # Missing return value check due to opkg issue 160
    ret[pkg] = {'old': oldstate,
                'new': state}
    return ret


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any([salt.utils.is_true(kwargs.get(x))
            for x in ('removed', 'purge_desired')]):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    cmd = ['opkg', 'list-installed']
    ret = {}
    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)
    for line in salt.utils.itertools.split(out, '\n'):
        pkg_name, pkg_version = line.split(' - ')
        __salt__['pkg_resource.add_pkg'](ret, pkg_name, pkg_version)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def list_upgrades(refresh=True):
    '''
    List all available package upgrades.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    ret = {}
    if salt.utils.is_true(refresh):
        refresh_db()

    cmd = ['opkg', 'list-upgradable']
    call = __salt__['cmd.run_all'](cmd,
                                   output_loglevel='trace',
                                   python_shell=False)

    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += call['stderr']
        if 'stdout' in call:
            comment += call['stdout']
        raise CommandExecutionError(
                '{0}'.format(comment)
        )
    else:
        out = call['stdout']

    for line in out.splitlines():
        name, _oldversion, newversion = line.split(' - ')
        ret[name] = newversion

    return ret


def _convert_to_standard_attr(attr):
    '''
    Helper function for _process_info_installed_output()

    Converts an opkg attribute name to a standard attribute
    name which is used across 'pkg' modules.
    '''
    ret_attr = ATTR_MAP.get(attr, None)
    if ret_attr is None:
        # All others convert to lowercase
        return attr.lower()
    return ret_attr


def _process_info_installed_output(out, filter_attrs):
    '''
    Helper function for info_installed()

    Processes stdout output from a single invocation of
    'opkg status'.
    '''
    ret = {}
    name = None
    attrs = {}
    attr = None

    for line in salt.utils.itertools.split(out, '\n'):
        if line and line[0] == ' ':
            # This is a continuation of the last attr
            if filter_attrs is None or attr in filter_attrs:
                line = line.strip()
                if len(attrs[attr]):
                    # If attr is empty, don't add leading newline
                    attrs[attr] += '\n'
                attrs[attr] += line
            continue
        line = line.strip()
        if not line:
            # Separator between different packages
            if name:
                ret[name] = attrs
            name = None
            attrs = {}
            attr = None
            continue
        key, value = line.split(':', 1)
        value = value.lstrip()
        attr = _convert_to_standard_attr(key)
        if attr == 'name':
            name = value
        elif filter_attrs is None or attr in filter_attrs:
            attrs[attr] = value

    if name:
        ret[name] = attrs
    return ret


def info_installed(*names, **kwargs):
    '''
    Return the information of the named package(s), installed on the system.

    .. versionadded:: Nitrogen

    :param names:
        Names of the packages to get information about. If none are specified,
        will return information for all installed packages.

    :param attr:
        Comma-separated package attributes. If no 'attr' is specified, all available attributes returned.

        Valid attributes are:
            arch, conffiles, conflicts, depends, description, filename, group,
            install_date_time_t, md5sum, packager, provides, recommends,
            replaces, size, source, suggests, url, version

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed
        salt '*' pkg.info_installed attr=version,packager
        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> attr=version,packager
        salt '*' pkg.info_installed <package1> <package2> <package3> ... attr=version,packager
    '''
    attr = kwargs.pop('attr', None)
    if attr is None:
        filter_attrs = None
    elif isinstance(attr, str):
        filter_attrs = set(attr.split(','))
    else:
        filter_attrs = set(attr)

    ret = {}
    if names:
        # Specific list of names of installed packages
        for name in names:
            cmd = ['opkg', 'status', name]
            call = __salt__['cmd.run_all'](cmd,
                                           output_loglevel='trace',
                                           python_shell=False)
            if call['retcode'] != 0:
                comment = ''
                if 'stderr' in call:
                    comment += call['stderr']

                raise CommandExecutionError(
                    '{0}'.format(comment)
                )
            ret.update(_process_info_installed_output(call['stdout'], filter_attrs))
    else:
        # All installed packages
        cmd = ['opkg', 'status']
        call = __salt__['cmd.run_all'](cmd,
                                       output_loglevel='trace',
                                       python_shell=False)
        if call['retcode'] != 0:
            comment = ''
            if 'stderr' in call:
                comment += call['stderr']

            raise CommandExecutionError(
                '{0}'.format(comment)
            )
        ret.update(_process_info_installed_output(call['stdout'], filter_attrs))

    return ret


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def version_cmp(pkg1, pkg2, ignore_epoch=False):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2016.3.4

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2.4-0' '0.2.4.1-0'
    '''
    normalize = lambda x: str(x).split(':', 1)[-1] if ignore_epoch else str(x)
    pkg1 = normalize(pkg1)
    pkg2 = normalize(pkg2)

    output = __salt__['cmd.run_stdout'](['opkg', '--version'],
                                        output_loglevel='trace',
                                        python_shell=False)
    opkg_version = output.split(' ')[2].strip()
    if distutils.version.LooseVersion(opkg_version) >= distutils.version.LooseVersion('0.3.4'):
        cmd_compare = ['opkg', 'compare-versions']
    elif salt.utils.which('opkg-compare-versions'):
        cmd_compare = ['opkg-compare-versions']
    else:
        log.warning('Unable to find a compare-versions utility installed. Either upgrade opkg to '
                    'version > 0.3.4 (preferred) or install the older opkg-compare-versions script.')
        return None

    for oper, ret in (("<<", -1), ("=", 0), (">>", 1)):
        cmd = cmd_compare[:]
        cmd.append(_cmd_quote(pkg1))
        cmd.append(oper)
        cmd.append(_cmd_quote(pkg2))
        retcode = __salt__['cmd.retcode'](cmd,
                                          output_loglevel='trace',
                                          ignore_retcode=True,
                                          python_shell=False)
        if retcode == 0:
            return ret
    return None


def list_repos():
    '''
    Lists all repos on /etc/opkg/*.conf

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
    '''
    repos = {}
    regex = re.compile(REPO_REGEXP)
    for filename in os.listdir(OPKG_CONFDIR):
        if filename.endswith(".conf"):
            with open(os.path.join(OPKG_CONFDIR, filename)) as conf_file:
                for line in conf_file:
                    if regex.search(line):
                        repo = {}
                        if line.startswith('#'):
                            repo['enabled'] = False
                            line = line[1:]
                        else:
                            repo['enabled'] = True
                        cols = salt.utils.shlex_split(line.strip())
                        if cols[0] in 'src':
                            repo['compressed'] = False
                        else:
                            repo['compressed'] = True
                        repo['name'] = cols[1]
                        repo['uri'] = cols[2]
                        repo['file'] = os.path.join(OPKG_CONFDIR, filename)
                        # do not store duplicated uri's
                        if repo['uri'] not in repos:
                            repos[repo['uri']] = [repo]
    return repos


def get_repo(alias):
    '''
    Display a repo from the /etc/opkg/*.conf

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo alias
    '''
    repos = list_repos()

    if repos:
        for source in six.itervalues(repos):
            for sub in source:
                if sub['name'] == alias:
                    return sub
    return {}


def _del_repo_from_file(alias, filepath):
    '''
    Remove a repo from filepath
    '''
    with open(filepath) as fhandle:
        output = []
        regex = re.compile(REPO_REGEXP)
        for line in fhandle:
            if regex.search(line):
                if line.startswith('#'):
                    line = line[1:]
                cols = salt.utils.shlex_split(line.strip())
                if alias != cols[1]:
                    output.append(line)
    with open(filepath, 'w') as fhandle:
        fhandle.writelines(output)


def _add_new_repo(alias, uri, compressed, enabled=True):
    '''
    Add a new repo entry
    '''
    repostr = '# ' if not enabled else ''
    repostr += 'src/gz ' if compressed else 'src '
    if ' ' in alias:
        repostr += '"' + alias + '" '
    else:
        repostr += alias + ' '
    repostr += uri + '\n'
    conffile = os.path.join(OPKG_CONFDIR, alias + '.conf')

    with open(conffile, 'a') as fhandle:
        fhandle.write(repostr)


def _mod_repo_in_file(alias, repostr, filepath):
    '''
    Replace a repo entry in filepath with repostr
    '''
    with open(filepath) as fhandle:
        output = []
        for line in fhandle:
            cols = salt.utils.shlex_split(line.strip())
            if alias not in cols:
                output.append(line)
            else:
                output.append(repostr + '\n')
    with open(filepath, 'w') as fhandle:
        fhandle.writelines(output)


def del_repo(alias):
    '''
    Delete a repo from /etc/opkg/*.conf

    If the file does not contain any other repo configuration, the file itself
    will be deleted.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo alias
    '''
    repos = list_repos()
    if repos:
        deleted_from = dict()
        for repo in repos:
            source = repos[repo][0]
            if source['name'] == alias:
                deleted_from[source['file']] = 0
                _del_repo_from_file(alias, source['file'])

        if deleted_from:
            ret = ''
            for repo in repos:
                source = repos[repo][0]
                if source['file'] in deleted_from:
                    deleted_from[source['file']] += 1
            for repo_file, count in six.iteritems(deleted_from):
                msg = 'Repo \'{0}\' has been removed from {1}.\n'
                if count == 1 and os.path.isfile(repo_file):
                    msg = ('File {1} containing repo \'{0}\' has been '
                           'removed.\n')
                    try:
                        os.remove(repo_file)
                    except OSError:
                        pass
                ret += msg.format(alias, repo_file)
            # explicit refresh after a repo is deleted
            refresh_db()
            return ret

    return "Repo {0} doesn't exist in the opkg repo lists".format(alias)


def mod_repo(alias, **kwargs):
    '''
    Modify one or more values for a repo.  If the repo does not exist, it will
    be created, so long as uri is defined.

    The following options are available to modify a repo definition:

    alias
        alias by which opkg refers to the repo.
    uri
        the URI to the repo.
    compressed
        defines (True or False) if the index file is compressed
    enabled
        enable or disable (True or False) repository
        but do not remove if disabled.
    refresh
        enable or disable (True or False) auto-refresh of the repositories

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo alias uri=http://new/uri
        salt '*' pkg.mod_repo alias enabled=False
    '''
    repos = list_repos()
    found = False
    uri = ''
    if 'uri' in kwargs:
        uri = kwargs['uri']

    for repo in repos:
        source = repos[repo][0]
        if source['name'] == alias:
            found = True
            repostr = ''
            if 'enabled' in kwargs and not kwargs['enabled']:
                repostr += '# '
            if 'compressed' in kwargs:
                repostr += 'src/gz ' if kwargs['compressed'] else 'src'
            else:
                repostr += 'src/gz' if source['compressed'] else 'src'
            repo_alias = kwargs['alias'] if 'alias' in kwargs else alias
            if ' ' in repo_alias:
                repostr += ' "{0}"'.format(repo_alias)
            else:
                repostr += ' {0}'.format(repo_alias)
            repostr += ' {0}'.format(kwargs['uri'] if 'uri' in kwargs else source['uri'])
            _mod_repo_in_file(alias, repostr, source['file'])
        elif uri and source['uri'] == uri:
            raise CommandExecutionError(
                'Repository \'{0}\' already exists as \'{1}\'.'.format(uri, source['name']))

    if not found:
        # Need to add a new repo
        if 'uri' not in kwargs:
            raise CommandExecutionError(
                'Repository \'{0}\' not found and no URI passed to create one.'.format(alias))
        # If compressed is not defined, assume True
        compressed = kwargs['compressed'] if 'compressed' in kwargs else True
        # If enabled is not defined, assume True
        enabled = kwargs['enabled'] if 'enabled' in kwargs else True
        _add_new_repo(alias, kwargs['uri'], compressed, enabled)

    if 'refresh' in kwargs:
        refresh_db()


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's package database (not
    generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    output = file_dict(*packages)
    files = []
    for package in list(output['packages'].values()):
        files.extend(package)
    return {'errors': output['errors'], 'files': files}


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    errors = []
    ret = {}
    cmd_files = ['opkg', 'files']

    if not packages:
        packages = list(list_pkgs().keys())

    for package in packages:
        files = []
        cmd = cmd_files[:]
        cmd.append(package)
        out = __salt__['cmd.run_all'](cmd,
                                      output_loglevel='trace',
                                      python_shell=False)
        for line in out['stdout'].splitlines():
            if line.startswith('/'):
                files.append(line)
            elif line.startswith(' * '):
                errors.append(line[3:])
                break
            else:
                continue
        if files:
            ret[package] = files

    return {'errors': errors, 'packages': ret}


def owner(*paths):
    '''
    Return the name of the package that owns the file. Multiple file paths can
    be passed. Like :mod:`pkg.version <salt.modules.opkg.version`, if a single
    path is passed, a string will be returned, and if multiple paths are passed,
    a dictionary of file/package name pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Example:

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /usr/bin/basename
    '''
    if not paths:
        return ''
    ret = {}
    cmd_search = ['opkg', 'search']
    for path in paths:
        cmd = cmd_search[:]
        cmd.append(path)
        output = __salt__['cmd.run_stdout'](cmd,
                                            output_loglevel='trace',
                                            python_shell=False)
        if output:
            ret[path] = output.split(' - ')[0].strip()
        else:
            ret[path] = ''
    if len(ret) == 1:
        return six.itervalues(ret)
    return ret

# -*- coding: utf-8 -*-
'''
Remote package support using ``pkg_add(1)``

.. warning::

    This module has been completely rewritten. Up to and including version
    0.17.0, it supported ``pkg_add(1)``, but checked for the existence of a
    pkgng local database and, if found,  would provide some of pkgng's
    functionality. The rewrite of this module has removed all pkgng support,
    and moved it to the :mod:`pkgng <salt.modules.pkgng>` execution module. For
    verisions <= 0.17.0, the documentation here should not be considered
    accurate. If your Minion is running one of these versions, then the
    documentation for this module can be viewed using the :mod:`sys.doc
    <salt.modules.sys.doc>` function:

    .. code-block:: bash

        salt bsdminion sys.doc pkg


This module acts as the default package provider for FreeBSD 9 and older. If
you need to use pkgng on a FreeBSD 9 system, you will need to override the
``pkg`` provider by setting the :conf_minion:`providers` parameter in your
Minion config file, in order to use pkgng.

.. code-block:: yaml

    providers:
      pkg: pkgng

More information on pkgng support can be found in the documentation for the
:mod:`pkgng <salt.modules.pkgng>` module.

This module will respect the ``PACKAGEROOT`` and ``PACKAGESITE`` environment
variables, if set, but these values can also be overridden in several ways:

1. :strong:`Salt configuration parameters.` The configuration parameters
   ``freebsdpkg.PACKAGEROOT`` and ``freebsdpkg.PACKAGESITE`` are recognized.
   These config parameters are looked up using :mod:`config.get
   <salt.modules.config.get>` and can thus be specified in the Master config
   file, Grains, Pillar, or in the Minion config file. Example:

   .. code-block:: yaml

        freebsdpkg.PACKAGEROOT: ftp://ftp.freebsd.org/
        freebsdpkg.PACKAGESITE: ftp://ftp.freebsd.org/pub/FreeBSD/ports/ia64/packages-9-stable/Latest/

2. :strong:`CLI arguments.` Both the ``packageroot`` (used interchangeably with
   ``fromrepo`` for API compatibility) and ``packagesite`` CLI arguments are
   recognized, and override their config counterparts from section 1 above.

   .. code-block:: bash

        salt -G 'os:FreeBSD' pkg.install zsh fromrepo=ftp://ftp2.freebsd.org/
        salt -G 'os:FreeBSD' pkg.install zsh packageroot=ftp://ftp2.freebsd.org/
        salt -G 'os:FreeBSD' pkg.install zsh packagesite=ftp://ftp2.freebsd.org/pub/FreeBSD/ports/ia64/packages-9-stable/Latest/

    .. note::

        These arguments can also be passed through in states:

        .. code-block:: yaml

            zsh:
              pkg.installed:
                - fromrepo: ftp://ftp2.freebsd.org/
'''

# Import python libs
import copy
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, MinionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Load as 'pkg' on FreeBSD versions less than 10
    '''
    if __grains__['os'] == 'FreeBSD' and float(__grains__['osrelease']) < 10:
        return __virtualname__
    return False


def _get_repo_options(fromrepo=None, packagesite=None):
    '''
    Return a list of tuples to seed the "env" list, which is used to set
    environment variables for any pkg_add commands that are spawned.

    If ``fromrepo`` or ``packagesite`` are None, then their corresponding
    config parameter will be looked up with config.get.

    If both ``fromrepo`` and ``packagesite`` are None, and neither
    freebsdpkg.PACKAGEROOT nor freebsdpkg.PACKAGESITE are specified, then an
    empty list is returned, and it is assumed that the system defaults (or
    environment variables) will be used.
    '''
    root = fromrepo if fromrepo is not None \
        else __salt__['config.get']('freebsdpkg.PACKAGEROOT', None)
    site = packagesite if packagesite is not None \
        else __salt__['config.get']('freebsdpkg.PACKAGESITE', None)
    ret = {}
    if root is not None:
        ret['PACKAGEROOT'] = root
    if site is not None:
        ret['PACKAGESITE'] = site
    return ret


def _match(names):
    '''
    Since pkg_delete requires the full "pkgname-version" string, this function
    will attempt to match the package name with its version. Returns a list of
    partial matches and package names that match the "pkgname-version" string
    required by pkg_delete, and a list of errors encountered.
    '''
    pkgs = list_pkgs(versions_as_list=True)
    errors = []

    # Look for full matches
    full_pkg_strings = []
    out = __salt__['cmd.run_stdout']('pkg_info', output_loglevel='debug')
    for line in out.splitlines():
        try:
            full_pkg_strings.append(line.split()[0])
        except IndexError:
            continue
    full_matches = [x for x in names if x in full_pkg_strings]

    # Look for pkgname-only matches
    matches = []
    ambiguous = []
    for name in set(names) - set(full_matches):
        cver = pkgs.get(name)
        if cver is not None:
            if len(cver) == 1:
                matches.append('{0}-{1}'.format(name, cver[0]))
            else:
                ambiguous.append(name)
                errors.append(
                    'Ambiguous package {0!r}. Full name/version required. '
                    'Possible matches: {1}'.format(
                        name,
                        ', '.join(['{0}-{1}'.format(name, x) for x in cver])
                    )
                )

    # Find packages that did not match anything
    not_matched = \
        set(names) - set(matches) - set(full_matches) - set(ambiguous)
    for name in not_matched:
        errors.append('Package {0!r} not found'.format(name))

    return matches + full_matches, errors


def latest_version(*names, **kwargs):
    '''
    ``pkg_add(1)`` is not capable of querying for remote packages, so this
    function will always return results as if there is no package available for
    install or upgrade.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    return '' if len(names) == 1 else dict((x, '') for x in names)

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
    ``pkg_add(1)`` does not use a local database of available packages, so this
    function simply returns ``True``. it exists merely for API compatibility.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    return True


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # 'removed' not applicable
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
    out = __salt__['cmd.run_stdout']('pkg_info', output_loglevel='debug')
    for line in out.splitlines():
        if not line:
            continue
        try:
            pkg, ver = line.split()[0].rsplit('-', 1)
        except (IndexError, ValueError):
            continue
        __salt__['pkg_resource.add_pkg'](ret, pkg, ver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def install(name=None,
            refresh=False,
            fromrepo=None,
            pkgs=None,
            sources=None,
            **kwargs):
    '''
    Install package(s) using ``pkg_add(1)``

    name
        The name of the package to be installed.

    refresh
        Whether or not to refresh the package database before installing.

    fromrepo or packageroot
        Specify a package repository from which to install. Overrides the
        system default, as well as the PACKAGEROOT environment variable.

    packagesite
        Specify the exact directory from which to install the remote package.
        Overrides the PACKAGESITE environment variable, if present.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'

    sources
        A list of packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"}, {"bar": "salt://bar.deb"}]'

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install <package name>
    '''
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not pkg_params:
        return {}

    packageroot = kwargs.get('packageroot')
    if not fromrepo and packageroot:
        fromrepo = packageroot

    env = _get_repo_options(fromrepo, kwargs.get('packagesite'))
    args = []

    if pkg_type == 'repository':
        args.append('-r')  # use remote repo

    args.extend(pkg_params)

    old = list_pkgs()
    __salt__['cmd.run'](
        'pkg_add {0}'.format(' '.join(args)),
        env=env,
        output_loglevel='debug'
    )
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    rehash()
    return salt.utils.compare_dicts(old, new)


def upgrade():
    '''
    Upgrades are not supported with ``pkg_add(1)``. This function is included
    for API compatibility only and always returns an empty dict.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    return {}


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove packages using ``pkg_delete(1)``

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
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets, errors = _match([x for x in pkg_params])
    for error in errors:
        log.error(error)
    if not targets:
        return {}
    cmd = 'pkg_delete {0}'.format(' '.join(targets))
    __salt__['cmd.run'](cmd, output_loglevel='debug')
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)

# Support pkg.delete to remove packages to more closely match pkg_delete
delete = remove
# No equivalent to purge packages, use remove instead
purge = remove


def rehash():
    '''
    Recomputes internal hash table for the PATH variable.
    Use whenever a new command is created during the current
    session.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.rehash
    '''
    shell = __salt__['cmd.run']('echo $SHELL', output_loglevel='debug')
    if shell.split('/')[-1] in ('csh', 'tcsh'):
        __salt__['cmd.run']('rehash', output_loglevel='debug')


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
    ret = file_dict(*packages)
    files = []
    for pkg_files in ret['files'].values():
        files.extend(pkg_files)
    ret['files'] = files
    return ret


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the
    system's package database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    errors = []
    files = {}

    if packages:
        match_pattern = '\'{0}-[0-9]*\''
        matches = [match_pattern.format(p) for p in packages]

        cmd = 'pkg_info -QL {0}'.format(' '.join(matches))
    else:
        cmd = 'pkg_info -QLa'

    ret = __salt__['cmd.run_all'](cmd, output_loglevel='debug')

    for line in ret['stderr'].splitlines():
        errors.append(line)

    pkg = None
    for line in ret['stdout'].splitlines():
        if pkg is not None and line.startswith('/'):
            files[pkg].append(line)
        elif ':/' in line:
            pkg, fn = line.split(':', 1)
            pkg, ver = pkg.rsplit('-', 1)
            files[pkg] = [fn]
        else:
            continue  # unexpected string

    return {'errors': errors, 'files': files}

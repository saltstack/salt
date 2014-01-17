# -*- coding: utf-8 -*-
'''
Support for YUM

:depends:   - yum Python module
            - rpmUtils Python module

This module uses the python interface to YUM. Note that with a default
/etc/yum.conf, this will cause messages to be sent to sent to syslog on
/dev/log, with a log facility of :strong:`LOG_USER`. This is in addition to
whatever is logged to /var/log/yum.log. See the manpage for ``yum.conf(5)`` for
information on how to use the ``syslog_facility`` and ``syslog_device`` config
parameters to configure how syslog is handled, or take the above defaults into
account when configuring your syslog daemon.

.. note::

    As of version 2014.1.0 (Hydrogen), this module is only used for yum-based
    distros if the minion has the following config parameter set:

    .. code-block:: yaml

        yum_provider: yumpkg
'''

# NOTE: This is no longer being developed and is not guaranteed to be
# API-compatible with pkg states. Use at your own risk.

# Import python libs
import copy
import logging
import os
import re
import yaml

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils import namespaced_function as _namespaced_function
from salt.modules.yumpkg5 import (
    _parse_repo_file, list_repos, mod_repo, get_repo, del_repo,
    expand_repo_def, __ARCHES
)

# Import third party libs
try:
    import yum
    import yum.logginglevels
    import rpmUtils.arch
    HAS_YUMDEPS = True

    class _YumLogger(yum.rpmtrans.RPMBaseCallback):
        '''
        A YUM callback handler that logs failed packages with their associated
        script output to the minion log, and logs install/remove/update/etc.
        activity to the yum log (usually /var/log/yum.log).

        See yum.rpmtrans.NoOutputCallBack in the yum package for base
        implementation.
        '''
        def __init__(self):
            yum.rpmtrans.RPMBaseCallback.__init__(self)
            self.messages = {}
            self.failed = []
            self.action = {
                yum.constants.TS_UPDATE: yum._('Updating'),
                yum.constants.TS_ERASE: yum._('Erasing'),
                yum.constants.TS_INSTALL: yum._('Installing'),
                yum.constants.TS_TRUEINSTALL: yum._('Installing'),
                yum.constants.TS_OBSOLETED: yum._('Obsoleted'),
                yum.constants.TS_OBSOLETING: yum._('Installing'),
                yum.constants.TS_UPDATED: yum._('Cleanup'),
                'repackaging': yum._('Repackaging')
            }
            # The fileaction are not translated, most sane IMHO / Tim
            self.fileaction = {
                yum.constants.TS_UPDATE: 'Updated',
                yum.constants.TS_ERASE: 'Erased',
                yum.constants.TS_INSTALL: 'Installed',
                yum.constants.TS_TRUEINSTALL: 'Installed',
                yum.constants.TS_OBSOLETED: 'Obsoleted',
                yum.constants.TS_OBSOLETING: 'Installed',
                yum.constants.TS_UPDATED: 'Cleanup'
            }
            self.logger = logging.getLogger(
                'yum.filelogging.RPMInstallCallback')

        def event(self, package, action, te_current, te_total, ts_current,
                  ts_total):
            # This would be used for a progress counter according to Yum docs
            pass

        def log_accumulated_errors(self):
            '''
            Convenience method for logging all messages from failed packages
            '''
            for pkg in self.failed:
                log.error('{0} {1}'.format(pkg, self.messages[pkg]))

        def errorlog(self, msg):
            # Log any error we receive
            log.error(msg)

        def filelog(self, package, action):
            if action == yum.constants.TS_FAILED:
                self.failed.append(package)
            else:
                if action in self.fileaction:
                    msg = '{0}: {1}'.format(self.fileaction[action], package)
                else:
                    msg = '{0}: {1}'.format(package, action)
                self.logger.info(msg)

        def scriptout(self, package, msgs):
            # This handler covers ancillary messages coming from the RPM script
            # Will sometimes contain more detailed error messages.
            self.messages[package] = msgs

    class _YumBase(yum.YumBase):
        def doLoggingSetup(self, debuglevel, errorlevel,
                           syslog_indent=None,
                           syslog_facility=None,
                           syslog_device='/dev/log'):
            '''
            This method is overridden in salt because we don't want syslog
            logging to happen.

            Additionally, no logging will be setup for yum.
            The logging handlers configure for yum were to ``sys.stdout``,
            ``sys.stderr`` and ``syslog``. We don't want none of those.
            Any logging will go through salt's logging handlers.
            '''

            # Just set the log levels to yum
            if debuglevel is not None:
                logging.getLogger('yum.verbose').setLevel(
                    yum.logginglevels.logLevelFromDebugLevel(debuglevel)
                )
            if errorlevel is not None:
                logging.getLogger('yum.verbose').setLevel(
                    yum.logginglevels.logLevelFromErrorLevel(errorlevel)
                )
            logging.getLogger('yum.filelogging').setLevel(logging.INFO)

except (ImportError, AttributeError):
    HAS_YUMDEPS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Deprecated, yumpkg5 is being used now.
    '''
    if __opts__.get('yum_provider') == 'yumpkg':
        global _parse_repo_file, list_repos, mod_repo, get_repo
        global del_repo, expand_repo_def
        _parse_repo_file = _namespaced_function(_parse_repo_file, globals())
        list_repos = _namespaced_function(list_repos, globals())
        mod_repo = _namespaced_function(mod_repo, globals())
        get_repo = _namespaced_function(get_repo, globals())
        del_repo = _namespaced_function(del_repo, globals())
        expand_repo_def = _namespaced_function(expand_repo_def, globals())
        return __virtualname__
    return False


def list_upgrades(refresh=True):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    pkgs = list_pkgs()

    yumbase = _YumBase()
    versions_list = {}
    for pkgtype in ['updates']:
        pkglist = yumbase.doPackageLists(pkgtype)
        for pkg in pkgs:
            exactmatch, matched, unmatched = yum.packages.parsePackages(
                pkglist, [pkg]
            )
            for pkg in exactmatch:
                if pkg.arch in rpmUtils.arch.legitMultiArchesInSameLib() \
                        or pkg.arch == 'noarch':
                    versions_list[pkg['name']] = '-'.join(
                        [pkg['version'], pkg['release']]
                    )
    return versions_list


def _set_repo_options(yumbase, **kwargs):
    '''
    Accepts a _YumBase() object and runs member functions to enable/disable
    repos as needed.
    '''
    # Get repo options from the kwargs
    fromrepo = kwargs.get('fromrepo', '')
    repo = kwargs.get('repo', '')
    disablerepo = kwargs.get('disablerepo', '')
    enablerepo = kwargs.get('enablerepo', '')

    # Support old 'repo' argument
    if repo and not fromrepo:
        fromrepo = repo

    try:
        if fromrepo:
            log.info('Restricting to repo {0!r}'.format(fromrepo))
            yumbase.repos.disableRepo('*')
            yumbase.repos.enableRepo(fromrepo)
        else:
            if disablerepo:
                log.info('Disabling repo {0!r}'.format(disablerepo))
                yumbase.repos.disableRepo(disablerepo)
            if enablerepo:
                log.info('Enabling repo {0!r}'.format(enablerepo))
                yumbase.repos.enableRepo(enablerepo)
    except yum.Errors.RepoError as exc:
        return exc


def _pkg_arch(name):
    '''
    Returns a 2-tuple of the name and arch parts of the passed string. Note
    that packages that are for the system architecture should not have the
    architecture specified in the passed string.
    '''
    try:
        pkgname, pkgarch = name.rsplit('.', 1)
    except ValueError:
        return name, __grains__['osarch']
    else:
        if pkgarch not in __ARCHES:
            return name, __grains__['osarch']
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

    yumbase = _YumBase()
    error = _set_repo_options(yumbase, **kwargs)
    if error:
        log.error(error)

    suffix_notneeded = rpmUtils.arch.legitMultiArchesInSameLib() + ['noarch']
    # look for available packages only, if package is already installed with
    # latest version it will not show up here.  If we want to use wildcards
    # here we can, but for now its exact match only.
    for pkgtype in ('available', 'updates'):
        pkglist = yumbase.doPackageLists(pkgtype)
        exactmatch, matched, unmatched = yum.packages.parsePackages(
            pkglist, [namearch_map[x]['name'] for x in names]
        )
        for name in names:
            for pkg in (x for x in exactmatch
                        if x.name == namearch_map[name]['name']):
                if (all(x in suffix_notneeded
                        for x in (namearch_map[name]['arch'], pkg.arch))
                        or namearch_map[name]['arch'] == pkg.arch):
                    ret[name] = '-'.join([pkg.version, pkg.release])

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
    yb = _YumBase()
    for p in yb.rpmdb:
        name = p.name
        if __grains__.get('cpuarch', '') == 'x86_64' \
                and re.match(r'i\d86', p.arch):
            name += '.{0}'.format(p.arch)
        pkgver = p.version
        if p.release:
            pkgver += '-{0}'.format(p.release)
        __salt__['pkg_resource.add_pkg'](ret, name, pkgver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def list_repo_pkgs():
    '''
    List the packages from repo in a dict::

        {'repo':{'<repo_name>':['<package_name>']}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_repo_pkgs
    '''
    yb = yum.YumBase()
    yb.conf.cache = 1
    ret = {'repo': {}}
    for pkg in sorted(yb.pkgSack.returnPackages()):
        pkgname = '{0}-{1}-{2}.{3}.rpm'.format(pkg.name,
                                               pkg.ver,
                                               pkg.release,
                                               pkg.arch)
        pkgrepo = pkg.repoid
        if ret['repo'].keys() == '' or pkgrepo not in ret['repo'].keys():
            ret['repo'].update({pkgrepo: []})
        elif pkgrepo in ret['repo'].keys():
            pkglist = ret['repo'][pkgrepo]
            pkglist.append(pkgname)
        else:
            ret = {}
    return ret


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
    yumbase = _YumBase()
    error = _set_repo_options(yumbase, **kwargs)
    if error:
        log.error(error)
        return {}

    ret = {}
    for name in names:
        pkgname, pkgarch = _pkg_arch(name)
        ret.setdefault(name, {})['found'] = bool(
            [x for x in yumbase.searchPackages(('name', 'arch'), (pkgname,))
             if x.name == pkgname and x.arch in (pkgarch, 'noarch')]
        )
        if ret[name]['found'] is False:
            provides = [
                x for x in yumbase.whatProvides(
                    pkgname, None, None
                ).returnPackages()
                if x.arch in (pkgarch, 'noarch')
            ]
            if provides:
                for pkg in provides:
                    ret[name].setdefault('suggestions', []).append(pkg.name)
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
    yumbase = _YumBase()
    yumbase.cleanMetadata()
    return True


def clean_metadata():
    '''
    Cleans local yum metadata.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.clean_metadata
    '''
    return refresh_db()


def group_install(name=None,
                  groups=None,
                  skip=None,
                  include=None,
                  **kwargs):
    '''
    Install the passed package group(s). This is basically a wrapper around
    pkg.install, which performs package group resolution for the user. This
    function is currently considered "experimental", and should be expected to
    undergo changes before it becomes official.

    name
        The name of a single package group to install. Note that this option is
        ignored if "groups" is passed.

    groups
        The names of multiple packages which are to be installed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.group_install groups='["Group 1", "Group 2"]'

    skip
        The name(s), in a list, of any packages that would normally be
        installed by the package group ("default" packages), which should not
        be installed.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'My Group' skip='["foo", "bar"]'

    include
        The name(s), in a list, of any packages which are included in a group,
        which would not normally be installed ("optional" packages). Note that
        this will nor enforce group membership; if you include packages which
        are not members of the specified groups, they will still be installed.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'My Group' include='["foo", "bar"]'

    other arguments
        Because this is essentially a wrapper around pkg.install, any argument
        which can be passed to pkg.install may also be included here, and it
        will be passed along wholesale.
    '''
    pkg_groups = []
    if groups:
        pkg_groups = yaml.safe_load(groups)
    else:
        pkg_groups.append(name)

    skip_pkgs = []
    if skip:
        skip_pkgs = yaml.safe_load(skip)

    include = []
    if include:
        include = yaml.safe_load(include)

    pkgs = []
    for group in pkg_groups:
        group_detail = group_info(group)
        for package in group_detail.get('mandatory packages', {}):
            pkgs.append(package)
        for package in group_detail.get('default packages', {}):
            if package not in skip_pkgs:
                pkgs.append(package)
        for package in include:
            pkgs.append(package)

    install_pkgs = yaml.safe_dump(pkgs)
    return install(pkgs=install_pkgs, **kwargs)


def install(name=None,
            refresh=False,
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
        Skip the GPG verification check. (e.g., ``--nogpgcheck``)

    version
        Install a specific version of the package, e.g. 1.2.3-4.el6. Ignored
        if "pkgs" or "sources" is passed.


    Repository Options:

    fromrepo
        Specify a package repository (or repositories) from which to install.
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

    enablerepo
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

    disablerepo
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
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4.el6"}]'

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

    old = list_pkgs()

    yumbase = _YumBase()
    setattr(yumbase.conf, 'assumeyes', True)
    setattr(yumbase.conf, 'gpgcheck', not skip_verify)

    version = kwargs.get('version')
    if version:
        if pkgs is None and sources is None:
            # Allow "version" to work for single package target
            pkg_params = {name: version}
        else:
            log.warning('"version" parameter will be ignored for multiple '
                        'package targets')

    error = _set_repo_options(yumbase, **kwargs)
    if error:
        log.error(error)
        return {}

    try:
        for pkgname in pkg_params:
            if pkg_type == 'file':
                log.info(
                    'Selecting "{0}" for local installation'.format(pkgname)
                )
                installed = yumbase.installLocal(pkgname)
                # if yum didn't install anything, maybe its a downgrade?
                log.debug('Added {0} transactions'.format(len(installed)))
                if len(installed) == 0 and pkgname not in old.keys():
                    log.info('Upgrade failed, trying local downgrade')
                    yumbase.downgradeLocal(pkgname)
            else:
                version = pkg_params[pkgname]
                if version is not None:
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
                    target = '{0}-{1}{2}'.format(pkgname, version, arch)
                else:
                    target = pkgname
                log.info('Selecting "{0}" for installation'.format(target))
                # Changed to pattern to allow specific package versions
                installed = yumbase.install(pattern=target)
                # if yum didn't install anything, maybe its a downgrade?
                log.debug('Added {0} transactions'.format(len(installed)))
                if len(installed) == 0 and target not in old.keys():
                    log.info('Upgrade failed, trying downgrade')
                    yumbase.downgrade(pattern=target)

        # Resolve Deps before attempting install. This needs to be improved by
        # also tracking any deps that may get upgraded/installed during this
        # process. For now only the version of the package(s) you request be
        # installed is tracked.
        log.info('Resolving dependencies')
        yumbase.resolveDeps()
        log.info('Processing transaction')
        yumlogger = _YumLogger()
        yumbase.processTransaction(rpmDisplay=yumlogger)
        yumlogger.log_accumulated_errors()
        yumbase.closeRpmDB()
    except Exception as e:
        log.error('Install failed: {0}'.format(e))

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

    yumbase = _YumBase()
    setattr(yumbase.conf, 'assumeyes', True)

    old = list_pkgs()

    try:
        # ideally we would look in the yum transaction and get info on all the
        # packages that are going to be upgraded and only look up old/new
        # version info on those packages.
        yumbase.update()
        log.info('Resolving dependencies')
        yumbase.resolveDeps()
        log.info('Processing transaction')
        yumlogger = _YumLogger()
        yumbase.processTransaction(rpmDisplay=yumlogger)
        yumlogger.log_accumulated_errors()
        yumbase.closeRpmDB()
    except Exception as e:
        log.error('Upgrade failed: {0}'.format(e))

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Removes packages using python API for yum.

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

    yumbase = _YumBase()
    setattr(yumbase.conf, 'assumeyes', True)

    # same comments as in upgrade for remove.
    for target in targets:
        if __grains__.get('cpuarch', '') == 'x86_64':
            try:
                arch = re.search(r'(\.i\d86)$', target).group(1)
            except AttributeError:
                arch = None
            else:
                # Remove arch from pkgname
                target = target[:-len(arch)]
                arch = arch.lstrip('.')
        else:
            arch = None
        yumbase.remove(name=target, arch=arch)

    log.info('Performing transaction test')
    try:
        callback = yum.callbacks.ProcessTransNoOutputCallback()
        result = yumbase._doTestTransaction(callback)
    except yum.Errors.YumRPMCheckError as exc:
        raise CommandExecutionError('\n'.join(exc.__dict__['value']))

    log.info('Resolving dependencies')
    yumbase.resolveDeps()
    log.info('Processing transaction')
    yumlogger = _YumLogger()
    yumbase.processTransaction(rpmDisplay=yumlogger)
    yumlogger.log_accumulated_errors()
    yumbase.closeRpmDB()

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported by yum, this function is identical to
    :mod:`pkg.remove <salt.modules.yumpkg.remove>`.

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


def verify(*package):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.verify
    '''
    return __salt__['lowpkg.verify'](*package)


def group_list():
    '''
    Lists all groups known by yum on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_list
    '''
    ret = {'installed': [], 'available': [], 'available languages': {}}
    yumbase = _YumBase()
    (installed, available) = yumbase.doGroupLists()
    for group in installed:
        ret['installed'].append(group.name)
    for group in available:
        if group.langonly:
            ret['available languages'][group.name] = {
                'name': group.name,
                'language': group.langonly}
        else:
            ret['available'].append(group.name)
    return ret


def group_info(groupname):
    '''
    Lists packages belonging to a certain group

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_info 'Perl Support'
    '''
    yumbase = _YumBase()
    (installed, available) = yumbase.doGroupLists()
    for group in installed + available:
        if group.name.lower() == groupname.lower():
            return {'mandatory packages': group.mandatory_packages,
                    'optional packages': group.optional_packages,
                    'default packages': group.default_packages,
                    'conditional packages': group.conditional_packages,
                    'description': group.description}


def group_diff(groupname):
    '''
    Lists packages belonging to a certain group, and which are installed

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_diff 'Perl Support'
    '''
    ret = {
        'mandatory packages': {'installed': [], 'not installed': []},
        'optional packages': {'installed': [], 'not installed': []},
        'default packages': {'installed': [], 'not installed': []},
        'conditional packages': {'installed': [], 'not installed': []},
    }
    pkgs = list_pkgs()
    yumbase = _YumBase()
    (installed, available) = yumbase.doGroupLists()
    for group in installed:
        if group.name == groupname:
            for pkg in group.mandatory_packages:
                if pkg in pkgs:
                    ret['mandatory packages']['installed'].append(pkg)
                else:
                    ret['mandatory packages']['not installed'].append(pkg)
            for pkg in group.optional_packages:
                if pkg in pkgs:
                    ret['optional packages']['installed'].append(pkg)
                else:
                    ret['optional packages']['not installed'].append(pkg)
            for pkg in group.default_packages:
                if pkg in pkgs:
                    ret['default packages']['installed'].append(pkg)
                else:
                    ret['default packages']['not installed'].append(pkg)
            for pkg in group.conditional_packages:
                if pkg in pkgs:
                    ret['conditional packages']['installed'].append(pkg)
                else:
                    ret['conditional packages']['not installed'].append(pkg)
            return {groupname: ret}


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's rpm database (not generally
    recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_list'](*packages)


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    rpm database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_dict'](*packages)

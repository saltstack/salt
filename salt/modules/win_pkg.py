# -*- coding: utf-8 -*-
'''
A module to manage software on Windows
'''

# Import python libs
from __future__ import absolute_import
import errno
import os
import locale
import logging
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    from salt.ext.six.moves import winreg as _winreg  # pylint: disable=import-error,no-name-in-module
    from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=import-error,no-name-in-module
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False
try:
    import msgpack
except ImportError:
    import msgpack_pure as msgpack
# pylint: enable=import-error

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError, SaltRenderError
import salt.utils
import salt.syspaths
from salt.exceptions import MinionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is Windows
    '''
    if salt.utils.is_windows() and HAS_DEPENDENCIES:
        return __virtualname__
    return (False, "Module win_pkg: module only works on Windows systems")


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
        salt '*' pkg.latest_version <package1> <package2> <package3> ...

    '''
    if len(names) == 0:
        return ''

    # Initialize the return dict with empty strings
    ret = {}
    for name in names:
        ret[name] = ''

    # Refresh before looking for the latest version available
    if salt.utils.is_true(kwargs.get('refresh', True)):
        refresh_db()

    installed_pkgs = list_pkgs(versions_as_list=True)
    log.trace('List of installed packages: {0}'.format(installed_pkgs))

    # iterate over all requested package names
    for name in names:
        latest_installed = '0'
        latest_available = '0'

        # get latest installed version of package
        if name in installed_pkgs:
            log.trace('Sorting out the latest available version of {0}'.format(name))
            latest_installed = sorted(installed_pkgs[name], cmp=_reverse_cmp_pkg_versions).pop()
            log.debug('Latest installed version of package {0} is {1}'.format(name, latest_installed))

        # get latest available (from winrepo_dir) version of package
        pkg_info = _get_package_info(name)
        log.trace('Raw winrepo pkg_info for {0} is {1}'.format(name, pkg_info))
        latest_available = _get_latest_pkg_version(pkg_info)
        if latest_available:
            log.debug('Latest available version of package {0} is {1}'.format(name, latest_available))

            # check, whether latest available version is newer than latest installed version
            if salt.utils.compare_versions(ver1=str(latest_available),
                                           oper='>',
                                           ver2=str(latest_installed)):
                log.debug('Upgrade of {0} from {1} to {2} is available'.format(name, latest_installed, latest_available))
                ret[name] = latest_available
            else:
                log.debug('No newer version than {0} of {1} is available'.format(latest_installed, name))
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def list_upgrades(refresh=True):
    '''
    List all available package upgrades on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    ret = {}
    for name, data in six.iteritems(get_repo_data().get('repo', {})):
        if version(name):
            latest = latest_version(name)
            if latest:
                ret[name] = latest
    return ret


def list_available(*names):
    '''
    Return a list of available versions of the specified package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_available <package name>
        salt '*' pkg.list_available <package name01> <package name02>
    '''
    if not names:
        return ''
    if len(names) == 1:
        pkginfo = _get_package_info(names[0])
        if not pkginfo:
            return ''
        versions = list(pkginfo.keys())
    else:
        versions = {}
        for name in names:
            pkginfo = _get_package_info(name)
            if not pkginfo:
                continue
            versions[name] = list(pkginfo.keys()) if pkginfo else []
    versions = sorted(versions, cmp=_reverse_cmp_pkg_versions)
    return versions


def version(*names, **kwargs):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
    '''
    ret = {}
    if len(names) == 1:
        val = __salt__['pkg_resource.version'](*names, **kwargs)
        if len(val):
            return val
        return ''
    if len(names) > 1:
        reverse_dict = {}
        nums = __salt__['pkg_resource.version'](*names, **kwargs)
        if len(nums):
            for num, val in six.iteritems(nums):
                if len(val) > 0:
                    try:
                        ret[reverse_dict[num]] = val
                    except KeyError:
                        ret[num] = val
            return ret
        return dict([(x, '') for x in names])
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

    ret = {}
    name_map = _get_name_map()
    for pkg_name, val in six.iteritems(_get_reg_software()):
        if pkg_name in name_map:
            key = name_map[pkg_name]
            if val in ['Not Found', None, False]:
                # Look up version from winrepo
                pkg_info = _get_package_info(key)
                if not pkg_info:
                    continue
                for pkg_ver in pkg_info.keys():
                    if pkg_info[pkg_ver]['full_name'] == pkg_name:
                        val = pkg_ver
        else:
            key = pkg_name
        __salt__['pkg_resource.add_pkg'](ret, key, val)

    __salt__['pkg_resource.sort_pkglist'](ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def _search_software(target):
    '''
    This searches the msi product databases for name matches
    of the list of target products, it will return a dict with
    values added to the list passed in
    '''
    search_results = {}
    software = dict(_get_reg_software().items())
    for key, value in six.iteritems(software):
        if key is not None:
            if target.lower() in key.lower():
                search_results[key] = value
    return search_results


def _get_reg_software():
    '''
    This searches the uninstall keys in the registry to find
    a match in the sub keys, it will return a dict with the
    display name as the key and the version as the value
    '''
    reg_software = {}

    #attempt to corral the wild west of the multiple ways to install
    #software in windows
    reg_entries = dict(_get_machine_keys().items())
    for reg_hive, reg_keys in six.iteritems(reg_entries):
        for reg_key in reg_keys:

            reg_handle = _open_registry_key(reg_hive, reg_key)
            if reg_handle is None:
                continue

            products = _get_product_information(reg_hive, reg_key, reg_handle)
            reg_software.update(products)

            _winreg.CloseKey(reg_handle)

    return reg_software


def _get_machine_keys():
    '''
    This will return the hive 'const' value and some registry keys where
    installed software information has been known to exist for the
    HKEY_LOCAL_MACHINE hive
    '''
    machine_hive_and_keys = {}
    machine_keys = [
        "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
        "Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
    ]
    machine_hive = _winreg.HKEY_LOCAL_MACHINE
    machine_hive_and_keys[machine_hive] = machine_keys
    return machine_hive_and_keys


def _open_registry_key(reg_hive, reg_key):
    reg_handle = None
    try:
        flags = _get_flags(reg_hive)

        reg_handle = _winreg.OpenKeyEx(
            reg_hive,
            reg_key,
            0,
            flags)
    # Unsinstall key may not exist for all users
    except Exception:
        pass

    return reg_handle


def _get_flags(reg_hive):
    try:
        reflect = _winreg.QueryReflectionKey(reg_hive)
    except NotImplemented:
        flags = reg_hive
    else:
        if reflect:
            flags = _winreg.KEY_READ | _winreg.KEY_WOW64_64KEY
        else:
            flags = _winreg.KEY_READ | _winreg.KEY_WOW64_32KEY

    return flags


def _get_product_information(reg_hive, reg_key, reg_handle):

    # This is a list of default OS reg entries that don't seem to be installed
    # software and no version information exists on any of these items
    # Also, some MS Office updates don't register a product name which means
    # their information is useless.
    ignore_list = ['AddressBook',
                   'Connection Manager',
                   'DirectDrawEx',
                   'Fontcore',
                   'IE40',
                   'IE4Data',
                   'IE5BAKEX',
                   'IEData',
                   'MobileOptionPack',
                   'SchedulingAgent',
                   'WIC',
                   'Not Found']
    encoding = locale.getpreferredencoding()

    products = {}
    try:
        i = 0
        while True:
            product_key = None
            asubkey = _winreg.EnumKey(reg_handle, i)
            rd_uninst_key = "\\".join([reg_key, asubkey])
            displayName = ''
            displayVersion = ''
            try:
                # these are not garuanteed to exist
                product_key = _open_registry_key(reg_hive, rd_uninst_key)
                displayName, value_type = _winreg.QueryValueEx(product_key, "DisplayName")
                try:
                    displayName = displayName.decode(encoding)
                except Exception:
                    pass
                displayVersion, value_type = _winreg.QueryValueEx(product_key, "DisplayVersion")
            except Exception:
                pass

            if product_key is not None:
                _winreg.CloseKey(product_key)
            i += 1

            if displayName not in ignore_list:
                # some MS Office updates don't register a product name which means
                # their information is useless
                if displayName != '':
                    products[displayName] = displayVersion

    except WindowsError:  # pylint: disable=E0602
        pass

    return products


def refresh_db(saltenv='base'):
    '''
    Just recheck the repository and return a dict::

        {'<database name>': Bool}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    __context__.pop('winrepo.data', None)
    if 'win_repo_source_dir' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_repo_source_dir\' config option is deprecated, please '
            'use \'winrepo_source_dir\' instead.'
        )
        winrepo_source_dir = __opts__['win_repo_source_dir']
    else:
        winrepo_source_dir = __opts__['winrepo_source_dir']

    # Clear minion repo-ng cache
    repo_path = '{0}\\files\\{1}\\win\\repo-ng\\salt-winrepo-ng'\
        .format(__opts__['cachedir'], saltenv)
    if not __salt__['file.remove'](repo_path):
        log.error('pkg.refresh_db: failed to clear existing cache')

    # Cache repo-ng locally
    cached_files = __salt__['cp.cache_dir'](
        winrepo_source_dir,
        saltenv,
        include_pat='*.sls'
    )
    genrepo(saltenv=saltenv)
    return cached_files


def _get_local_repo_dir(saltenv='base'):
    if 'win_repo_source_dir' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_repo_source_dir\' config option is deprecated, please '
            'use \'winrepo_source_dir\' instead.'
        )
        winrepo_source_dir = __opts__['win_repo_source_dir']
    else:
        winrepo_source_dir = __opts__['winrepo_source_dir']

    dirs = []
    dirs.append(salt.syspaths.CACHE_DIR)
    dirs.extend(['minion', 'files'])
    dirs.append(saltenv)
    dirs.extend(winrepo_source_dir[7:].strip('/').split('/'))
    return os.sep.join(dirs)


def genrepo(saltenv='base'):
    '''
    Generate winrepo_cachefile based on sls files in the winrepo

    CLI Example:

    .. code-block:: bash

        salt-run winrepo.genrepo
    '''
    ret = {}
    repo = _get_local_repo_dir(saltenv)
    if not os.path.exists(repo):
        os.makedirs(repo)
    winrepo = 'winrepo.p'
    renderers = salt.loader.render(__opts__, __salt__)
    for root, _, files in os.walk(repo):
        for name in files:
            if name.endswith('.sls'):
                try:
                    config = salt.template.compile_template(
                            os.path.join(root, name),
                            renderers,
                            __opts__['renderer'])
                except SaltRenderError as exc:
                    log.debug('Failed to compile {0}.'.format(os.path.join(root, name)))
                    log.debug('Error: {0}.'.format(exc))
                    continue

                if config:
                    revmap = {}
                    for pkgname, versions in six.iteritems(config):
                        for version, repodata in six.iteritems(versions):
                            if not isinstance(version, six.string_types):
                                config[pkgname][str(version)] = \
                                    config[pkgname].pop(version)
                            if not isinstance(repodata, dict):
                                log.debug('Failed to compile'
                                          '{0}.'.format(os.path.join(root, name)))
                                continue
                            revmap[repodata['full_name']] = pkgname
                    ret.setdefault('repo', {}).update(config)
                    ret.setdefault('name_map', {}).update(revmap)
    with salt.utils.fopen(os.path.join(repo, winrepo), 'w+b') as repo_cache:
        repo_cache.write(msgpack.dumps(ret))
    return ret


def _get_source_sum(source_hash, file_path, saltenv):
    '''
    Extract the hash sum, whether it is in a remote hash file, or just a string.
    '''
    ret = dict()
    schemes = ('salt', 'http', 'https', 'ftp', 'swift', 's3', 'file')
    invalid_hash_msg = ("Source hash '{0}' format is invalid. It must be in the format"
                        ' <hash type>=<hash>').format(source_hash)
    source_hash = str(source_hash)
    source_hash_scheme = _urlparse(source_hash).scheme

    if source_hash_scheme in schemes:
        # The source_hash is a file on a server
        cached_hash_file = __salt__['cp.cache_file'](source_hash, saltenv)

        if not cached_hash_file:
            raise CommandExecutionError(('Source hash file {0} not'
                                         ' found').format(source_hash))

        ret = __salt__['file.extract_hash'](cached_hash_file, '', file_path)
        if ret is None:
            raise SaltInvocationError(invalid_hash_msg)
    else:
        # The source_hash is a hash string
        items = source_hash.split('=', 1)

        if len(items) != 2:
            invalid_hash_msg = ('{0}, or it must be a supported protocol'
                                ': {1}').format(invalid_hash_msg, ', '.join(schemes))
            raise SaltInvocationError(invalid_hash_msg)

        ret['hash_type'], ret['hsum'] = [item.strip().lower() for item in items]

    return ret


def install(name=None, refresh=False, pkgs=None, saltenv='base', **kwargs):
    r'''
    Install the passed package(s) on the system using winrepo

    :param name:
        The name of a single package, or a comma-separated list of packages to
        install. (no spaces after the commas)
    :type name: str, list, or None

    :param bool refresh: Boolean value representing whether or not to refresh
        the winrepo db

    :param pkgs: A list of packages to install from a software repository.
        All packages listed under ``pkgs`` will be installed via a single
        command.
    :type pkgs: list or None

    :param str saltenv: The salt environment to use. Default is ``base``.

    *Keyword Arguments (kwargs)*

    :param str version:
        The specific version to install. If omitted, the latest version will be
        installed. If passed with multiple install, the version will apply to
        all packages. Recommended for single installation only.

    :param str cache_file:
        A single file to copy down for use with the installer. Copied to the
        same location as the installer. Use this over ``cache_dir`` if there
        are many files in the directory and you only need a specific file and
        don't want to cache additional files that may reside in the installer
        directory. Only applies to files on ``salt://``

    :param bool cache_dir:
        True will copy the contents of the installer directory. This is useful
        for installations that are not a single file. Only applies to
        directories on ``salt://``

    :return: Return a dict containing the new package names and versions::
    :rtype: dict

        If the package is installed by ``pkg.install``:

        .. code-block:: cfg

            {'<package>': {'old': '<old-version>',
                           'new': '<new-version>'}}

        If the package is already installed:

        .. code-block:: cfg

            {'<package>': {'current': '<current-version>'}}

    The following example will refresh the winrepo and install a single package,
    7zip.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install 7zip refresh=True

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install 7zip
        salt '*' pkg.install 7zip,filezilla
        salt '*' pkg.install pkgs='["7zip","filezilla"]'

    WinRepo Definition File Examples:

    The following example demonstrates the use of ``cache_file``. This would be
    used if you have multiple installers in the same directory that use the same
    ``install.ini`` file and you don't want to download the additional
    installers.

    .. code-block:: bash

        ntp:
          4.2.8:
            installer: 'salt://win/repo/ntp/ntp-4.2.8-win32-setup.exe'
            full_name: Meinberg NTP Windows Client
            locale: en_US
            reboot: False
            cache_file: 'salt://win/repo/ntp/install.ini'
            install_flags: '/USEFILE=C:\salt\var\cache\salt\minion\files\base\win\repo\ntp\install.ini'
            uninstaller: 'NTP/uninst.exe'

    The following example demonstrates the use of ``cache_dir``. It assumes a
    file named ``install.ini`` resides in the same directory as the installer.

    .. code-block:: bash

        ntp:
          4.2.8:
            installer: 'salt://win/repo/ntp/ntp-4.2.8-win32-setup.exe'
            full_name: Meinberg NTP Windows Client
            locale: en_US
            reboot: False
            cache_dir: True
            install_flags: '/USEFILE=C:\salt\var\cache\salt\minion\files\base\win\repo\ntp\install.ini'
            uninstaller: 'NTP/uninst.exe'
    '''
    ret = {}
    if refresh:
        refresh_db()

    # Make sure name or pkgs is passed
    if not name and not pkgs:
        return 'Must pass a single package or a list of packages'

    # Ignore pkg_type from parse_targets, Windows does not support the
    # "sources" argument
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs, **kwargs)[0]

    if pkg_params is None or len(pkg_params) == 0:
        log.error('No package definition found')
        return {}

    if not pkgs and len(pkg_params) == 1:
        # Only use the 'version' param if 'name' was not specified as a
        # comma-separated list
        pkg_params = {name: {'version': kwargs.get('version'),
                             'extra_install_flags': kwargs.get('extra_install_flags')}}

    # Get a list of currently installed software for comparison at the end
    old = list_pkgs()

    # Loop through each package
    changed = []
    latest = []
    for pkg_name, options in six.iteritems(pkg_params):

        # Load package information for the package
        pkginfo = _get_package_info(pkg_name)

        # Make sure pkginfo was found
        if not pkginfo:
            log.error('Unable to locate package {0}'.format(pkg_name))
            ret[pkg_name] = 'Unable to locate package {0}'.format(pkg_name)
            continue

        # Get the version number passed or the latest available
        version_num = ''
        if options:
            version_num = options.get('version', False)

        if not version_num:
            version_num = _get_latest_pkg_version(pkginfo)

        # Check if the version is already installed
        if version_num == old.get(pkg_name) \
                or (pkg_name in old and old[pkg_name] == 'Not Found'):
            # Desired version number already installed
            ret[pkg_name] = {'current': version_num}
            continue

        # If version number not installed, is the version available?
        elif version_num not in pkginfo:
            log.error('Version {0} not found for package '
                      '{1}'.format(version_num, pkg_name))
            ret[pkg_name] = {'not found': version_num}
            continue

        if 'latest' in pkginfo:
            latest.append(pkg_name)

        # Get the installer settings from winrepo.p
        installer = pkginfo[version_num].get('installer', False)
        cache_dir = pkginfo[version_num].get('cache_dir', False)
        cache_file = pkginfo[version_num].get('cache_file', False)

        # Is there an installer configured?
        if not installer:
            log.error('No installer configured for version {0} of package '
                      '{1}'.format(version_num, pkg_name))
            ret[pkg_name] = {'no installer': version_num}
            continue

        # Is the installer in a location that requires caching
        if installer.startswith(('salt:', 'http:', 'https:', 'ftp:')):

            # Check for the 'cache_dir' parameter in the .sls file
            # If true, the entire directory will be cached instead of the
            # individual file. This is useful for installations that are not
            # single files
            if cache_dir and installer.startswith('salt:'):
                path, _ = os.path.split(installer)
                __salt__['cp.cache_dir'](path, saltenv, False, None, 'E@init.sls$')

            # Check to see if the cache_file is cached... if passed
            if cache_file and cache_file.startswith('salt:'):

                # Check to see if the file is cached
                cached_file = __salt__['cp.is_cached'](cache_file, saltenv)
                if not cached_file:
                    cached_file = __salt__['cp.cache_file'](cache_file, saltenv)

                # Make sure the cached file is the same as the source
                if __salt__['cp.hash_file'](cache_file, saltenv) != \
                        __salt__['cp.hash_file'](cached_file):
                    cached_file = __salt__['cp.cache_file'](cache_file, saltenv)

                    # Check if the cache_file was cached successfully
                    if not cached_file:
                        log.error('Unable to cache {0}'.format(cache_file))
                        ret[pkg_name] = {'failed to cache cache_file': cache_file}
                        continue

            # Check to see if the installer is cached
            cached_pkg = __salt__['cp.is_cached'](installer, saltenv)
            if not cached_pkg:
                # It's not cached. Cache it, mate.
                cached_pkg = __salt__['cp.cache_file'](installer, saltenv)

                # Check if the installer was cached successfully
                if not cached_pkg:
                    log.error('Unable to cache file {0} from saltenv: {1}'.format(installer, saltenv))
                    ret[pkg_name] = {'unable to cache': installer}
                    continue

            # Compare the hash of the cached installer to the source only if the
            # file is hosted on salt:
            if installer.startswith('salt:'):
                if __salt__['cp.hash_file'](installer, saltenv) != \
                        __salt__['cp.hash_file'](cached_pkg):
                    try:
                        cached_pkg = __salt__['cp.cache_file'](installer, saltenv)
                    except MinionError as exc:
                        return '{0}: {1}'.format(exc, installer)

                    # Check if the installer was cached successfully
                    if not cached_pkg:
                        log.error('Unable to cache {0}'.format(installer))
                        ret[pkg_name] = {'unable to cache': installer}
                        continue
        else:
            # Run the installer directly (not hosted on salt:, https:, etc.)
            cached_pkg = installer

        # Fix non-windows slashes
        cached_pkg = cached_pkg.replace('/', '\\')
        cache_path, _ = os.path.split(cached_pkg)

        # Compare the hash sums
        source_hash = pkginfo[version_num].get('source_hash', False)
        if source_hash:
            source_sum = _get_source_sum(source_hash, cached_pkg, saltenv)
            log.debug('Source %s hash: %s', source_sum['hash_type'], source_sum['hsum'])

            cached_pkg_sum = salt.utils.get_hash(cached_pkg, source_sum['hash_type'])
            log.debug('Package %s hash: %s', source_sum['hash_type'], cached_pkg_sum)

            if source_sum['hsum'] != cached_pkg_sum:
                raise SaltInvocationError(("Source hash '{0}' does not match package hash"
                                           " '{1}'").format(source_sum['hsum'], cached_pkg_sum))
            log.debug('Source hash matches package hash.')

        # Get install flags
        install_flags = '{0}'.format(pkginfo[version_num].get('install_flags'))
        if options and options.get('extra_install_flags'):
            install_flags = '{0} {1}'.format(install_flags,
                                             options.get('extra_install_flags', ''))

        # Install the software
        # Check Use Scheduler Option
        if pkginfo[version_num].get('use_scheduler', False):

            # Build Scheduled Task Parameters
            if pkginfo[version_num].get('msiexec'):
                cmd = 'msiexec.exe'
                arguments = ['/i', cached_pkg]
                if pkginfo['version_num'].get('allusers', True):
                    arguments.append('ALLUSERS="1"')
                arguments.extend(salt.utils.shlex_split(install_flags))
            else:
                cmd = cached_pkg
                arguments = salt.utils.shlex_split(install_flags)

            # Create Scheduled Task
            __salt__['task.create_task'](name='update-salt-software',
                                         user_name='System',
                                         force=True,
                                         action_type='Execute',
                                         cmd=cmd,
                                         arguments=' '.join(arguments),
                                         start_in=cache_path,
                                         trigger_type='Once',
                                         start_date='1975-01-01',
                                         start_time='01:00')
            # Run Scheduled Task
            __salt__['task.run_wait'](name='update-salt-software')
        else:
            # Build the install command
            cmd = []
            if pkginfo[version_num].get('msiexec'):
                cmd.extend(['msiexec', '/i', cached_pkg])
                if pkginfo[version_num].get('allusers', True):
                    cmd.append('ALLUSERS="1"')
            else:
                cmd.append(cached_pkg)
            cmd.extend(salt.utils.shlex_split(install_flags))
            # Launch the command
            result = __salt__['cmd.run_stdout'](cmd,
                                                cache_path,
                                                output_loglevel='trace',
                                                python_shell=False)
            if result:
                log.error('Failed to install {0}'.format(pkg_name))
                log.error('error message: {0}'.format(result))
                ret[pkg_name] = {'failed': result}
            else:
                changed.append(pkg_name)

    # Get a new list of installed software
    new = list_pkgs()

    # For installers that have no specific version (ie: chrome)
    # The software definition file will have a version of 'latest'
    # In that case there's no way to know which version has been installed
    # Just return the current installed version
    if latest:
        for pkg_name in latest:
            if old.get(pkg_name, 'old') == new.get(pkg_name, 'new'):
                ret[pkg_name] = {'current': new[pkg_name]}

    # Check for changes in the registry
    difference = salt.utils.compare_dicts(old, new)

    # Compare the software list before and after
    # Add the difference to ret
    ret.update(difference)

    return ret


def upgrade(refresh=True):
    '''
    Run a full system upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    log.warning('pkg.upgrade not implemented on Windows yet')

    # Uncomment the below once pkg.upgrade has been implemented

    # if salt.utils.is_true(refresh):
    #    refresh_db()
    return {}


def remove(name=None, pkgs=None, version=None, **kwargs):
    '''
    Remove the passed package(s) from the system using winrepo

    :param name:
        The name of the package to be uninstalled.
    :type name: str, list, or None

    :param str version:
        The version of the package to be uninstalled. If this option is used to
        to uninstall multiple packages, then this version will be applied to all
        targeted packages. Recommended using only when uninstalling a single
        package. If this parameter is omitted, the latest version will be
        uninstalled.

    Multiple Package Options:

    :param pkgs:
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.
    :type pkgs: list or None

    .. versionadded:: 0.16.0

    :return: Returns a dict containing the changes.
    :rtype: dict

        If the package is removed by ``pkg.remove``:

            {'<package>': {'old': '<old-version>',
                           'new': '<new-version>'}}

        If the package is already uninstalled:

            {'<package>': {'current': 'not installed'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    ret = {}

    # Make sure name or pkgs is passed
    if not name and not pkgs:
        return 'Must pass a single package or a list of packages'

    # Get package parameters
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs, **kwargs)[0]

    # Get a list of currently installed software for comparison at the end
    old = list_pkgs()

    # Loop through each package
    changed = []
    for target in pkg_params:

        # Load package information for the package
        pkginfo = _get_package_info(target)

        # Make sure pkginfo was found
        if not pkginfo:
            log.error('Unable to locate package {0}'.format(name))
            ret[target] = 'Unable to locate package {0}'.format(target)
            continue

        # Get latest version if no version passed, else use passed version
        if not version:
            version_num = _get_latest_pkg_version(pkginfo)
        else:
            version_num = version

        if 'latest' in pkginfo and version_num not in pkginfo:
            version_num = 'latest'

        # Check to see if package is installed on the system
        if target not in old:
            log.error('{0} {1} not installed'.format(target, version))
            ret[target] = {'current': 'not installed'}
            continue
        else:
            if not version_num == old.get(target) \
                    and not old.get(target) == "Not Found" \
                    and not version_num == 'latest':
                log.error('{0} {1} not installed'.format(target, version))
                ret[target] = {'current': '{0} not installed'.format(version_num)}
                continue

        # Get the uninstaller
        uninstaller = pkginfo[version_num].get('uninstaller')

        # If no uninstaller found, use the installer
        if not uninstaller:
            uninstaller = pkginfo[version_num].get('installer')

        # If still no uninstaller found, fail
        if not uninstaller:
            log.error('Error: No installer or uninstaller configured for package {0}'.format(name))
            ret[target] = {'no uninstaller': version_num}
            continue

        # Where is the uninstaller
        if uninstaller.startswith(('salt:', 'http:', 'https:', 'ftp:')):

            # Check to see if the uninstaller is cached
            cached_pkg = __salt__['cp.is_cached'](uninstaller)
            if not cached_pkg:
                # It's not cached. Cache it, mate.
                cached_pkg = __salt__['cp.cache_file'](uninstaller)

                # Check if the uninstaller was cached successfully
                if not cached_pkg:
                    log.error('Unable to cache {0}'.format(uninstaller))
                    ret[target] = {'unable to cache': uninstaller}
                    continue
        else:
            # Run the uninstaller directly (not hosted on salt:, https:, etc.)
            cached_pkg = uninstaller

        # Fix non-windows slashes
        cached_pkg = cached_pkg.replace('/', '\\')
        cache_path, _ = os.path.split(cached_pkg)

        # Get parameters for cmd
        expanded_cached_pkg = str(os.path.expandvars(cached_pkg))

        # Get uninstall flags
        uninstall_flags = '{0}'.format(pkginfo[version_num].get('uninstall_flags', ''))
        if kwargs.get('extra_uninstall_flags'):
            uninstall_flags = '{0} {1}'.format(uninstall_flags,
                                               kwargs.get('extra_uninstall_flags', ""))

        # Uninstall the software
        # Check Use Scheduler Option
        if pkginfo[version_num].get('use_scheduler', False):

            # Build Scheduled Task Parameters
            if pkginfo[version_num].get('msiexec'):
                cmd = 'msiexec.exe'
                arguments = ['/x']
                arguments.extend(salt.utils.shlex_split(uninstall_flags))
            else:
                cmd = expanded_cached_pkg
                arguments = salt.utils.shlex_split(uninstall_flags)

            # Create Scheduled Task
            __salt__['task.create_task'](name='update-salt-software',
                                         user_name='System',
                                         force=True,
                                         action_type='Execute',
                                         cmd=cmd,
                                         arguments=' '.join(arguments),
                                         start_in=cache_path,
                                         trigger_type='Once',
                                         start_date='1975-01-01',
                                         start_time='01:00')
            # Run Scheduled Task
            __salt__['task.run_wait'](name='update-salt-software')
        else:
            # Build the install command
            cmd = []
            if pkginfo[version_num].get('msiexec'):
                cmd.extend(['msiexec', '/x', expanded_cached_pkg])
            else:
                cmd.append(expanded_cached_pkg)
            cmd.extend(salt.utils.shlex_split(uninstall_flags))
            # Launch the command
            result = __salt__['cmd.run_stdout'](cmd,
                                                output_loglevel='trace',
                                                python_shell=False)
            if result:
                log.error('Failed to install {0}'.format(target))
                log.error('error message: {0}'.format(result))
                ret[target] = {'failed': result}
            else:
                changed.append(target)

    # Get a new list of installed software
    new = list_pkgs()
    tries = 0
    difference = salt.utils.compare_dicts(old, new)

    while not all(name in difference for name in changed) and tries <= 1000:
        new = list_pkgs()
        difference = salt.utils.compare_dicts(old, new)
        tries += 1
        if tries == 1000:
            ret['_comment'] = 'Registry not updated.'

    # Compare the software list before and after
    # Add the difference to ret
    ret.update(difference)

    return ret


def purge(name=None, pkgs=None, version=None, **kwargs):
    '''
    Package purges are not supported, this function is identical to
    ``remove()``.

    name
        The name of the package to be deleted.

    version
        The version of the package to be deleted. If this option is used in
        combination with the ``pkgs`` option below, then this version will be
        applied to all targeted packages.


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
    return remove(name=name, pkgs=pkgs, version=version, **kwargs)


def get_repo_data(saltenv='base'):
    '''
    Returns the cached winrepo data

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_repo_data
    '''
    #if 'winrepo.data' in __context__:
    #    return __context__['winrepo.data']
    repocache_dir = _get_local_repo_dir(saltenv=saltenv)
    winrepo = 'winrepo.p'
    try:
        with salt.utils.fopen(
                os.path.join(repocache_dir, winrepo), 'rb') as repofile:
            try:
                repodata = msgpack.loads(repofile.read()) or {}
                return repodata
            except Exception as exc:
                log.exception(exc)
                return {}
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            # File doesn't exist
            raise CommandExecutionError(
                'Windows repo cache doesn\'t exist, pkg.refresh_db likely '
                'needed'
            )
        log.error('Not able to read repo file')
        log.exception(exc)
        return {}


def get_name_map():
    return _get_name_map()


def _get_name_map():
    '''
    Return a reverse map of full pkg names to the names recognized by winrepo.
    '''
    u_name_map = {}
    name_map = get_repo_data().get('name_map', {})
    for k in name_map.keys():
        u_name_map[k.decode('utf-8')] = name_map[k]
    return u_name_map


def _get_package_info(name):
    '''
    Return package info.
    Returns empty map if package not available
    TODO: Add option for version
    '''
    return get_repo_data().get('repo', {}).get(name, {})


def _reverse_cmp_pkg_versions(pkg1, pkg2):
    '''
    Compare software package versions
    '''
    if LooseVersion(pkg1) > LooseVersion(pkg2):
        return 1
    else:
        return -1


def _get_latest_pkg_version(pkginfo):
    if len(pkginfo) == 1:
        return next(six.iterkeys(pkginfo))
    return sorted(pkginfo, cmp=_reverse_cmp_pkg_versions).pop()


def compare_versions(ver1='', oper='==', ver2=''):
    '''
    Compare software package versions
    '''
    return salt.utils.compare_versions(ver1, oper, ver2)

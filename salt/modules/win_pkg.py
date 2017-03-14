# -*- coding: utf-8 -*-
'''
A module to manage software on Windows

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

The following functions require the existence of a :ref:`windows repository
<windows-package-manager>` metadata DB, typically created by running
:py:func:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>`:

- :py:func:`pkg.get_repo_data <salt.modules.win_pkg.get_repo_data>`
- :py:func:`pkg.install <salt.modules.win_pkg.install>`
- :py:func:`pkg.latest_version <salt.modules.win_pkg.latest_version>`
- :py:func:`pkg.list_available <salt.modules.win_pkg.list_available>`
- :py:func:`pkg.list_pkgs <salt.modules.win_pkg.list_pkgs>`
- :py:func:`pkg.list_upgrades <salt.modules.win_pkg.list_upgrades>`
- :py:func:`pkg.remove <salt.modules.win_pkg.remove>`

If a metadata DB does not already exist and one of these functions is run, then
one will be created from the repo SLS files that are present.

As the creation of this metadata can take some time, the
:conf_minion:`winrepo_cache_expire_min` minion config option can be used to
suppress refreshes when the metadata is less than a given number of seconds
old.
'''

# Import python future libs
from __future__ import absolute_import
from __future__ import unicode_literals
import collections
import datetime
import errno
import logging
import os
import re
import time

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error,no-name-in-module
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse

# Import salt libs
from salt.exceptions import (CommandExecutionError,
                             SaltInvocationError,
                             SaltRenderError)
import salt.utils
import salt.syspaths
import salt.payload
from salt.exceptions import MinionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return (False, "Module win_pkg: module only works on Windows systems")


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    Args:
        names (str): A single or multiple names to lookup

    Kwargs:
        saltenv (str): Salt environment. Default ``base``
        refresh (bool): Refresh package metadata. Default ``True``

    Returns:
        dict: A dictionary of packages with the latest version available

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

    saltenv = kwargs.get('saltenv', 'base')
    # Refresh before looking for the latest version available
    refresh = salt.utils.is_true(kwargs.get('refresh', True))
    # no need to call _refresh_db_conditional as list_pkgs will do it

    installed_pkgs = list_pkgs(versions_as_list=True, saltenv=saltenv, refresh=refresh)
    log.trace('List of installed packages: {0}'.format(installed_pkgs))

    # iterate over all requested package names
    for name in names:
        latest_installed = '0'
        latest_available = '0'

        # get latest installed version of package
        if name in installed_pkgs:
            log.trace('Determining latest installed version of %s', name)
            try:
                latest_installed = sorted(installed_pkgs[name]).pop()
            except IndexError:
                log.warning(
                    '%s was empty in pkg.list_pkgs return data, this is '
                    'probably a bug in list_pkgs', name
                )
            else:
                log.debug('Latest installed version of %s is %s',
                          name, latest_installed)

        # get latest available (from winrepo_dir) version of package
        pkg_info = _get_package_info(name, saltenv=saltenv)
        log.trace('Raw winrepo pkg_info for {0} is {1}'.format(name, pkg_info))
        latest_available = _get_latest_pkg_version(pkg_info)
        if latest_available:
            log.debug('Latest available version '
                      'of package {0} is {1}'.format(name, latest_available))

            # check, whether latest available version
            # is newer than latest installed version
            if salt.utils.compare_versions(ver1=str(latest_available),
                                           oper='>',
                                           ver2=str(latest_installed)):
                log.debug('Upgrade of {0} from {1} to {2} '
                          'is available'.format(name,
                                                latest_installed,
                                                latest_available))
                ret[name] = latest_available
            else:
                log.debug('No newer version than {0} of {1} '
                          'is available'.format(latest_installed, name))
    if len(names) == 1:
        return ret[names[0]]
    return ret


def upgrade_available(name, refresh=True, saltenv='base'):
    '''
    Check whether or not an upgrade is available for a given package

    Args:
        name (str): The name of a single package
        refresh (bool): Refresh package metadata. Default ``True``
        saltenv (str): The salt environment. Default ``base``

    Returns:
        bool: True if new version available, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    # Refresh before looking for the latest version available,
    # same default as latest_version
    refresh = salt.utils.is_true(refresh)

    current = version(name, saltenv=saltenv, refresh=refresh).get(name)
    latest = latest_version(name, saltenv=saltenv, refresh=False)

    return compare_versions(latest, '>', current)


def list_upgrades(refresh=True, saltenv='base'):
    '''
    List all available package upgrades on this system

    Args:
        refresh (bool): Refresh package metadata. Default ``True``
        saltenv (str): Salt environment. Default ``base``

    Returns:
        dict: A dictionary of packages with available upgrades

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    refresh = salt.utils.is_true(refresh)
    _refresh_db_conditional(saltenv, force=refresh)

    installed_pkgs = list_pkgs(refresh=False)
    available_pkgs = get_repo_data(saltenv).get('repo')
    pkgs = {}
    for pkg in installed_pkgs:
        if pkg in available_pkgs:
            latest_ver = latest_version(pkg, refresh=False)
            install_ver = installed_pkgs[pkg]
            if compare_versions(latest_ver, '>', install_ver):
                pkgs[pkg] = latest_ver

    return pkgs


def list_available(*names, **kwargs):
    '''
    Return a list of available versions of the specified package.

    Args:
        names (str): One or more package names

    Kwargs:

        saltenv (str): The salt environment to use. Default ``base``.

        refresh (bool): Refresh package metadata. Default ``True``.

        return_dict_always (bool):
            Default ``False`` dict when a single package name is queried.

    Returns:
        dict: The package name with its available versions

    .. code-block:: cfg

        {'<package name>': ['<version>', '<version>', ]}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_available <package name> return_dict_always=True
        salt '*' pkg.list_available <package name01> <package name02>
    '''
    if not names:
        return ''

    saltenv = kwargs.get('saltenv', 'base')
    refresh = salt.utils.is_true(kwargs.get('refresh', False))
    _refresh_db_conditional(saltenv, force=refresh)
    return_dict_always = \
        salt.utils.is_true(kwargs.get('return_dict_always', False))
    if len(names) == 1 and not return_dict_always:
        pkginfo = _get_package_info(names[0], saltenv=saltenv)
        if not pkginfo:
            return ''
        versions = sorted(list(pkginfo.keys()))
    else:
        versions = {}
        for name in names:
            pkginfo = _get_package_info(name, saltenv=saltenv)
            if not pkginfo:
                continue
            verlist = sorted(list(pkginfo.keys())) if pkginfo else []
            versions[name] = verlist
    return versions


def version(*names, **kwargs):
    '''
    Returns a version if the package is installed, else returns an empty string

    Args:
        name (str): One or more package names

    Kwargs:
        saltenv (str): The salt environment to use. Default ``base``.
        refresh (bool): Refresh package metadata. Default ``False``.

    Returns:
        dict: The package name(s) with the installed versions.

    .. code-block:: cfg

        {'<package name>': ['<version>', '<version>', ]}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package name01> <package name02>
    '''
    saltenv = kwargs.get('saltenv', 'base')

    installed_pkgs = list_pkgs(refresh=kwargs.get('refresh', False))
    available_pkgs = get_repo_data(saltenv).get('repo')

    ret = {}
    for name in names:
        if name in available_pkgs:
            ret[name] = installed_pkgs.get(name, '')
        else:
            ret[name] = 'not available'

    return ret


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed

    Args:
        version_as_list (bool): Returns the versions as a list

    Kwargs:
        saltenv (str): The salt environment to use. Default ``base``.
        refresh (bool): Refresh package metadata. Default ``False`.

    Returns:
        dict: A dictionary of installed software with versions installed

    .. code-block:: cfg

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
    saltenv = kwargs.get('saltenv', 'base')
    refresh = salt.utils.is_true(kwargs.get('refresh', False))
    _refresh_db_conditional(saltenv, force=refresh)

    ret = {}
    name_map = _get_name_map(saltenv)
    for pkg_name, val in six.iteritems(_get_reg_software()):
        if pkg_name in name_map:
            key = name_map[pkg_name]
            if val in ['(value not set)', 'Not Found', None, False]:
                # Look up version from winrepo
                pkg_info = _get_package_info(key, saltenv=saltenv)
                if not pkg_info:
                    continue
                for pkg_ver in pkg_info:
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
    This searches the msi product databases for name matches of the list of
    target products, it will return a dict with values added to the list passed
    in
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
    This searches the uninstall keys in the registry to find a match in the sub
    keys, it will return a dict with the display name as the key and the
    version as the value
    '''
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
                   'Not Found',
                   '(value not set)',
                   '',
                   None]
    #encoding = locale.getpreferredencoding()
    reg_software = {}

    hive = 'HKLM'
    key = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"

    def update(hive, key, reg_key, use_32bit):

        d_name = ''
        d_vers = ''

        d_name = __salt__['reg.read_value'](hive,
                                            '{0}\\{1}'.format(key, reg_key),
                                            'DisplayName',
                                            use_32bit)['vdata']

        d_vers = __salt__['reg.read_value'](hive,
                                            '{0}\\{1}'.format(key, reg_key),
                                            'DisplayVersion',
                                            use_32bit)['vdata']

        if d_name not in ignore_list:
            # some MS Office updates don't register a product name which means
            # their information is useless
            reg_software.update({d_name: str(d_vers)})

    for reg_key in __salt__['reg.list_keys'](hive, key):
        update(hive, key, reg_key, False)

    for reg_key in __salt__['reg.list_keys'](hive, key, True):
        update(hive, key, reg_key, True)

    return reg_software


def _refresh_db_conditional(saltenv, **kwargs):
    '''
    Internal use only in this module, has a different set of defaults and
    returns True or False. And supports check the age of the existing
    generated metadata db, as well as ensure metadata db exists to begin with

    Args:
        saltenv (str): Salt environment

    Returns:
        bool: True Fetched or Cache uptodate, False to indicate an issue

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    '''
    force = salt.utils.is_true(kwargs.pop('force', False))
    failhard = salt.utils.is_true(kwargs.pop('failhard', False))
    expired_max = __opts__['winrepo_cache_expire_max']
    expired_min = __opts__['winrepo_cache_expire_min']

    repo_details = _get_repo_details(saltenv)

    # Skip force if age less than minimum age
    if force and expired_min > 0 and repo_details.winrepo_age < expired_min:
        log.info(
            'Refresh skipped, age of winrepo metadata in seconds (%s) is less '
            'than winrepo_cache_expire_min (%s)',
            repo_details.winrepo_age, expired_min
        )
        force = False

    # winrepo_age is -1 if repo db does not exist
    refresh = True if force \
        or repo_details.winrepo_age == -1 \
        or repo_details.winrepo_age > expired_max \
        else False

    if not refresh:
        log.debug(
            'Using existing pkg metadata db for saltenv \'%s\' (age is %s)',
            saltenv, datetime.timedelta(seconds=repo_details.winrepo_age)
        )
        return True

    if repo_details.winrepo_age == -1:
        # no repo meta db
        log.debug(
            'No winrepo.p cache file for saltenv \'%s\', creating one now',
            saltenv
        )

    results = refresh_db(saltenv=saltenv, verbose=False, failhard=failhard)
    try:
        # Return True if there were no failed winrepo SLS files, and False if
        # failures were reported.
        return not bool(results.get('failed', 0))
    except AttributeError:
        return False


def refresh_db(**kwargs):
    '''
    Fetches metadata files and calls :py:func:`pkg.genrepo
    <salt.modules.win_pkg.genrepo>` to compile updated repository metadata.

    Kwargs:

        saltenv (str): Salt environment. Default: ``base``

        verbose (bool):
            Return verbose data structure which includes 'success_list', a list
            of all sls files and the package names contained within. Default
            'False'

        failhard (bool):
            If ``True``, an error will be raised if any repo SLS files failed to
            process. If ``False``, no error will be raised, and a dictionary
            containing the full results will be returned.

    Returns:
        dict: A dictionary containing the results of the database refresh.

    .. Warning::
        When calling this command from a state using `module.run` be sure to
        pass `failhard: False`. Otherwise the state will report failure if it
        encounters a bad software definition file.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
        salt '*' pkg.refresh_db saltenv=base
    '''
    saltenv = kwargs.pop('saltenv', 'base')
    verbose = salt.utils.is_true(kwargs.pop('verbose', False))
    failhard = salt.utils.is_true(kwargs.pop('failhard', True))
    __context__.pop('winrepo.data', None)
    repo_details = _get_repo_details(saltenv)

    log.debug(
        'Refreshing pkg metadata db for saltenv \'%s\' (age of existing '
        'metadata is %s)',
        saltenv, datetime.timedelta(seconds=repo_details.winrepo_age)
    )

    # Clear minion repo-ng cache see #35342 discussion
    log.info('Removing all *.sls files under \'%s\'', repo_details.local_dest)
    failed = []
    for root, _, files in os.walk(repo_details.local_dest, followlinks=False):
        for name in files:
            if name.endswith('.sls'):
                full_filename = os.path.join(root, name)
                try:
                    os.remove(full_filename)
                except OSError as exc:
                    if exc.errno != errno.ENOENT:
                        log.error('Failed to remove %s: %s', full_filename, exc)
                        failed.append(full_filename)
    if failed:
        raise CommandExecutionError(
            'Failed to clear one or more winrepo cache files',
            info={'failed': failed}
        )

    # Cache repo-ng locally
    cached_files = __salt__['cp.cache_dir'](
        repo_details.winrepo_source_dir,
        saltenv,
        include_pat='*.sls'
    )

    return genrepo(saltenv=saltenv, verbose=verbose, failhard=failhard)


def _get_repo_details(saltenv):
    '''
    Return repo details for the specified saltenv as a namedtuple
    '''
    contextkey = 'winrepo._get_repo_details.{0}'.format(saltenv)

    if contextkey in __context__:
        (winrepo_source_dir, local_dest, winrepo_file) = __context__[contextkey]
    else:
        winrepo_source_dir = __opts__['winrepo_source_dir']
        dirs = [__opts__['cachedir'], 'files', saltenv]
        url_parts = _urlparse(winrepo_source_dir)
        dirs.append(url_parts.netloc)
        dirs.extend(url_parts.path.strip('/').split('/'))
        local_dest = os.sep.join(dirs)

        winrepo_file = os.path.join(local_dest, 'winrepo.p')  # Default
        # Check for a valid windows file name
        if not re.search(r'[\/:*?"<>|]',
                         __opts__['winrepo_cachefile'],
                         flags=re.IGNORECASE):
            winrepo_file = os.path.join(
                local_dest,
                __opts__['winrepo_cachefile']
                )
        else:
            log.error(
                'minion cofiguration option \'winrepo_cachefile\' has been '
                'ignored as its value (%s) is invalid. Please ensure this '
                'option is set to a valid filename.',
                __opts__['winrepo_cachefile']
            )

        # Do some safety checks on the repo_path as its contents can be removed,
        # this includes check for bad coding
        paths = (
            r'[a-z]\:\\$',
            r'\\$',
            re.escape(os.environ.get('SystemRoot', r'C:\Windows'))
        )
        for path in paths:
            if re.match(path, local_dest, flags=re.IGNORECASE) is not None:
                raise CommandExecutionError(
                    'Local cache dir {0} is not a good location'.format(local_dest)
                )

        __context__[contextkey] = (winrepo_source_dir, local_dest, winrepo_file)

    try:
        os.makedirs(local_dest)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise CommandExecutionError(
                'Failed to create {0}: {1}'.format(local_dest, exc)
            )

    winrepo_age = -1
    try:
        stat_result = os.stat(winrepo_file)
        mtime = stat_result.st_mtime
        winrepo_age = time.time() - mtime
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise CommandExecutionError(
                'Failed to get age of {0}: {1}'.format(winrepo_file, exc)
            )
    except AttributeError:
        # Shouldn't happen but log if it does
        log.warning('st_mtime missing from stat result %s', stat_result)
    except TypeError:
        # Shouldn't happen but log if it does
        log.warning('mtime of %s (%s) is an invalid type', winrepo_file, mtime)

    repo_details = collections.namedtuple(
        'RepoDetails',
        ('winrepo_source_dir', 'local_dest', 'winrepo_file', 'winrepo_age')
    )
    return repo_details(winrepo_source_dir, local_dest, winrepo_file, winrepo_age)


def genrepo(**kwargs):
    '''
    Generate package metedata db based on files within the winrepo_source_dir

    Kwargs:

        saltenv (str): Salt environment. Default: ``base``

        verbose (bool):
            Return verbose data structure which includes 'success_list', a list
            of all sls files and the package names contained within. Default
            'False'

        failhard (bool):
            If ``True``, an error will be raised if any repo SLS files failed
            to process. If ``False``, no error will be raised, and a dictionary
            containing the full results will be returned.

    Returns:
        dict: A dictionary of the results of the command

    CLI Example:

    .. code-block:: bash

        salt-run pkg.genrepo
        salt -G 'os:windows' pkg.genrepo verbose=true failhard=false
        salt -G 'os:windows' pkg.genrepo saltenv=base
    '''
    saltenv = kwargs.pop('saltenv', 'base')
    verbose = salt.utils.is_true(kwargs.pop('verbose', False))
    failhard = salt.utils.is_true(kwargs.pop('failhard', True))

    ret = {}
    successful_verbose = {}
    total_files_processed = 0
    ret['repo'] = {}
    ret['errors'] = {}
    repo_details = _get_repo_details(saltenv)

    for root, _, files in os.walk(repo_details.local_dest, followlinks=False):
        short_path = os.path.relpath(root, repo_details.local_dest)
        if short_path == '.':
            short_path = ''
        for name in files:
            if name.endswith('.sls'):
                total_files_processed += 1
                _repo_process_pkg_sls(
                    os.path.join(root, name),
                    os.path.join(short_path, name),
                    ret,
                    successful_verbose
                    )
    serial = salt.payload.Serial(__opts__)
    mode = 'wb+' if six.PY3 else 'w+'
    with salt.utils.fopen(repo_details.winrepo_file, mode) as repo_cache:
        repo_cache.write(serial.dumps(ret))
    # save reading it back again. ! this breaks due to utf8 issues
    #__context__['winrepo.data'] = ret
    successful_count = len(successful_verbose)
    error_count = len(ret['errors'])
    if verbose:
        results = {
            'total': total_files_processed,
            'success': successful_count,
            'failed': error_count,
            'success_list': successful_verbose,
            'failed_list': ret['errors']
            }
    else:
        if error_count > 0:
            results = {
                'total': total_files_processed,
                'success': successful_count,
                'failed': error_count,
                'failed_list': ret['errors']
                }
        else:
            results = {
                'total': total_files_processed,
                'success': successful_count,
                'failed': error_count
                }

    if error_count > 0 and failhard:
        raise CommandExecutionError(
            'Error occurred while generating repo db',
            info=results
        )
    else:
        return results


def _repo_process_pkg_sls(file, short_path_name, ret, successful_verbose):
    renderers = salt.loader.render(__opts__, __salt__)

    def _failed_compile(msg):
        log.error(msg)
        ret.setdefault('errors', {})[short_path_name] = [msg]
        return False

    try:
        config = salt.template.compile_template(
            file,
            renderers,
            __opts__['renderer'],
            __opts__.get('renderer_blacklist', ''),
            __opts__.get('renderer_whitelist', ''))
    except SaltRenderError as exc:
        msg = 'Failed to compile \'{0}\': {1}'.format(short_path_name, exc)
        return _failed_compile(msg)
    except Exception as exc:
        msg = 'Failed to read \'{0}\': {1}'.format(short_path_name, exc)
        return _failed_compile(msg)

    if config:
        revmap = {}
        errors = []
        pkgname_ok_list = []
        for pkgname, versions in six.iteritems(config):
            if pkgname in ret['repo']:
                log.error(
                    'package \'%s\' within \'%s\' already defined, skipping',
                    pkgname, short_path_name
                )
                errors.append('package \'{0}\' already defined'.format(pkgname))
                break
            for version, repodata in six.iteritems(versions):
                # Ensure version is a string/unicode
                if not isinstance(version, six.string_types):
                    msg = (
                        'package \'{0}\'{{0}}, version number {1} '
                        'is not a string'.format(pkgname, version)
                    )
                    log.error(
                        msg.format(' within \'{0}\''.format(short_path_name))
                    )
                    errors.append(msg.format(''))
                    continue
                # Ensure version contains a dict
                if not isinstance(repodata, dict):
                    msg = (
                        'package \'{0}\'{{0}}, repo data for '
                        'version number {1} is not defined as a dictionary '
                        .format(pkgname, version)
                    )
                    log.error(
                        msg.format(' within \'{0}\''.format(short_path_name))
                    )
                    errors.append(msg.format(''))
                    continue
                revmap[repodata['full_name']] = pkgname
        if errors:
            ret.setdefault('errors', {})[short_path_name] = errors
        else:
            if pkgname not in pkgname_ok_list:
                pkgname_ok_list.append(pkgname)
            ret.setdefault('repo', {}).update(config)
            ret.setdefault('name_map', {}).update(revmap)
            successful_verbose[short_path_name] = config.keys()
    else:
        log.debug('No data within \'%s\' after processing', short_path_name)
        # no pkgname found after render
        successful_verbose[short_path_name] = []


def _get_source_sum(source_hash, file_path, saltenv):
    '''
    Extract the hash sum, whether it is in a remote hash file, or just a string.
    '''
    ret = dict()
    schemes = ('salt', 'http', 'https', 'ftp', 'swift', 's3', 'file')
    invalid_hash_msg = ("Source hash '{0}' format is invalid. It must be in "
                        "the format <hash type>=<hash>").format(source_hash)
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
                                ': {1}').format(invalid_hash_msg,
                                                ', '.join(schemes))
            raise SaltInvocationError(invalid_hash_msg)

        ret['hash_type'], ret['hsum'] = [item.strip().lower() for item in items]

    return ret


def install(name=None, refresh=False, pkgs=None, **kwargs):
    r'''
    Install the passed package(s) on the system using winrepo

    Args:

        name (str):
            The name of a single package, or a comma-separated list of packages
            to install. (no spaces after the commas)

        refresh (bool):
            Boolean value representing whether or not to refresh the winrepo db

        pkgs (list):
            A list of packages to install from a software repository. All
            packages listed under ``pkgs`` will be installed via a single
            command.

    Kwargs:

        version (str):
            The specific version to install. If omitted, the latest version
            will be installed. If passed with multiple install, the version
            will apply to all packages. Recommended for single installation
            only.

        cache_file (str):
            A single file to copy down for use with the installer. Copied to
            the same location as the installer. Use this over ``cache_dir`` if
            there are many files in the directory and you only need a specific
            file and don't want to cache additional files that may reside in
            the installer directory. Only applies to files on ``salt://``

        cache_dir (bool):
            True will copy the contents of the installer directory. This is
            useful for installations that are not a single file. Only applies
            to directories on ``salt://``

        saltenv (str): Salt environment. Default 'base'

        report_reboot_exit_codes (bool):
            If the installer exits with a recognized exit code indicating that
            a reboot is required, the module function

               *win_system.set_reboot_required_witnessed*

            will be called, preserving the knowledge of this event for the
            remainder of the current boot session. For the time being, 3010 is
            the only recognized exit code. The value of this param defaults to
            True.

            .. versionadded:: 2016.11.0

    Returns:
        dict: Return a dict containing the new package names and versions

        If the package is installed by ``pkg.install``:

        .. code-block:: cfg

            {'<package>': {'old': '<old-version>',
                           'new': '<new-version>'}}

        If the package is already installed:

        .. code-block:: cfg

            {'<package>': {'current': '<current-version>'}}

    The following example will refresh the winrepo and install a single
    package, 7zip.

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
    used if you have multiple installers in the same directory that use the
    same ``install.ini`` file and you don't want to download the additional
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
    saltenv = kwargs.pop('saltenv', 'base')

    refresh = salt.utils.is_true(refresh)
    # no need to call _refresh_db_conditional as list_pkgs will do it

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
        pkg_params = {
            name: {
                'version': kwargs.get('version'),
                'extra_install_flags': kwargs.get('extra_install_flags')
            }
        }

    # Get a list of currently installed software for comparison at the end
    old = list_pkgs(saltenv=saltenv, refresh=refresh)

    # Loop through each package
    changed = []
    latest = []
    for pkg_name, options in six.iteritems(pkg_params):

        # Load package information for the package
        pkginfo = _get_package_info(pkg_name, saltenv=saltenv)

        # Make sure pkginfo was found
        if not pkginfo:
            log.error('Unable to locate package {0}'.format(pkg_name))
            ret[pkg_name] = 'Unable to locate package {0}'.format(pkg_name)
            continue

        # Get the version number passed or the latest available
        version_num = ''
        if options:
            if options.get('version') is not None:
                version_num = str(options.get('version'))

        if not version_num:
            version_num = _get_latest_pkg_version(pkginfo)

        # Check if the version is already installed
        if version_num in old.get(pkg_name, '').split(',') \
                or (pkg_name in old and old.get(pkg_name) is None):
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
        installer = pkginfo[version_num].get('installer', '')
        cache_dir = pkginfo[version_num].get('cache_dir', False)
        cache_file = pkginfo[version_num].get('cache_file', '')

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
                __salt__['cp.cache_dir'](path,
                                         saltenv,
                                         False,
                                         None,
                                         'E@init.sls$')

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
                        ret[pkg_name] = {
                            'failed to cache cache_file': cache_file
                        }
                        continue

            # Check to see if the installer is cached
            cached_pkg = __salt__['cp.is_cached'](installer, saltenv)
            if not cached_pkg:
                # It's not cached. Cache it, mate.
                cached_pkg = __salt__['cp.cache_file'](installer, saltenv)

                # Check if the installer was cached successfully
                if not cached_pkg:
                    log.error('Unable to cache file {0} '
                              'from saltenv: {1}'.format(installer, saltenv))
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
            log.debug('Source {0} hash: {1}'.format(source_sum['hash_type'],
                                                    source_sum['hsum']))

            cached_pkg_sum = salt.utils.get_hash(cached_pkg,
                                                 source_sum['hash_type'])
            log.debug('Package {0} hash: {1}'.format(source_sum['hash_type'],
                                                     cached_pkg_sum))

            if source_sum['hsum'] != cached_pkg_sum:
                raise SaltInvocationError(
                    ("Source hash '{0}' does not match package hash"
                     " '{1}'").format(source_sum['hsum'], cached_pkg_sum)
                )
            log.debug('Source hash matches package hash.')

        # Get install flags
        install_flags = pkginfo[version_num].get('install_flags', '')
        if options and options.get('extra_install_flags'):
            install_flags = '{0} {1}'.format(
                install_flags,
                options.get('extra_install_flags', '')
            )

        # Install the software
        # Check Use Scheduler Option
        if pkginfo[version_num].get('use_scheduler', False):

            # Build Scheduled Task Parameters
            if pkginfo[version_num].get('msiexec', False):
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
                                         start_time='01:00',
                                         ac_only=False,
                                         stop_if_on_batteries=False)
            # Run Scheduled Task
            if not __salt__['task.run_wait'](name='update-salt-software'):
                log.error('Failed to install {0}'.format(pkg_name))
                log.error('Scheduled Task failed to run')
                ret[pkg_name] = {'install status': 'failed'}
        else:
            # Build the install command
            cmd = []
            if pkginfo[version_num].get('msiexec', False):
                cmd.extend(['msiexec', '/i', cached_pkg])
                if pkginfo[version_num].get('allusers', True):
                    cmd.append('ALLUSERS="1"')
            else:
                cmd.append(cached_pkg)
            cmd.extend(salt.utils.shlex_split(install_flags))
            # Launch the command
            result = __salt__['cmd.run_all'](cmd,
                                             cache_path,
                                             output_loglevel='quiet',
                                             python_shell=False,
                                             redirect_stderr=True)
            if not result['retcode']:
                ret[pkg_name] = {'install status': 'success'}
                changed.append(pkg_name)
            elif result['retcode'] == 3010:
                # 3010 is ERROR_SUCCESS_REBOOT_REQUIRED
                report_reboot_exit_codes = kwargs.pop(
                    'report_reboot_exit_codes', True)
                if report_reboot_exit_codes:
                    __salt__['system.set_reboot_required_witnessed']()
                ret[pkg_name] = {'install status': 'success, reboot required'}
                changed.append(pkg_name)
            else:
                log.error('Failed to install {0}'.format(pkg_name))
                log.error('retcode {0}'.format(result['retcode']))
                log.error('installer output: {0}'.format(result['stdout']))
                ret[pkg_name] = {'install status': 'failed'}

    # Get a new list of installed software
    new = list_pkgs(saltenv=saltenv)

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


def upgrade(**kwargs):
    '''
    Upgrade all software. Currently not implemented

    Kwargs:
        saltenv (str): The salt environment to use. Default ``base``.
        refresh (bool): Refresh package metadata. Default ``True``.

    .. note::
        This feature is not yet implemented for Windows.

    Returns:
        dict: Empty dict, until implemented

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    log.warning('pkg.upgrade not implemented on Windows yet')
    refresh = salt.utils.is_true(kwargs.get('refresh', True))
    saltenv = kwargs.get('saltenv', 'base')
    # Uncomment the below once pkg.upgrade has been implemented

    # if salt.utils.is_true(refresh):
    #    refresh_db()
    return {}


def remove(name=None, pkgs=None, version=None, **kwargs):
    '''
    Remove the passed package(s) from the system using winrepo

    .. versionadded:: 0.16.0

    Args:
        name (str): The name(s) of the package(s) to be uninstalled. Can be a
            single package or a comma delimted list of packages, no spaces.
        version (str):
            The version of the package to be uninstalled. If this option is
            used to to uninstall multiple packages, then this version will be
            applied to all targeted packages. Recommended using only when
            uninstalling a single package. If this parameter is omitted, the
            latest version will be uninstalled.
        pkgs (list):
            A list of packages to delete. Must be passed as a python list. The
            ``name`` parameter will be ignored if this option is passed.

    Kwargs:
        saltenv (str): Salt environment. Default ``base``
        refresh (bool): Refresh package metadata. Default ``False``

    Returns:
        dict: Returns a dict containing the changes.

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
    saltenv = kwargs.get('saltenv', 'base')
    refresh = salt.utils.is_true(kwargs.get('refresh', False))
    # no need to call _refresh_db_conditional as list_pkgs will do it
    ret = {}

    # Make sure name or pkgs is passed
    if not name and not pkgs:
        return 'Must pass a single package or a list of packages'

    # Get package parameters
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs, **kwargs)[0]

    # Get a list of currently installed software for comparison at the end
    old = list_pkgs(saltenv=saltenv, refresh=refresh, versions_as_list=True)

    # Loop through each package
    changed = []
    for pkgname, version_num in six.iteritems(pkg_params):

        # Load package information for the package
        pkginfo = _get_package_info(pkgname, saltenv=saltenv)

        # Make sure pkginfo was found
        if not pkginfo:
            msg = 'Unable to locate package {0}'.format(pkgname)
            log.error(msg)
            ret[pkgname] = msg
            continue

        if version_num is None and 'latest' in pkginfo:
            version_num = 'latest'

        # Check to see if package is installed on the system
        removal_targets = []
        if pkgname not in old:
            log.error('%s %s not installed', pkgname, version)
            ret[pkgname] = {'current': 'not installed'}
            continue
        else:
            if version_num is None:
                removal_targets.extend(old[pkgname])
            elif version_num not in old[pkgname] \
                    and 'Not Found' not in old[pkgname] \
                    and version_num != 'latest':
                log.error('%s %s not installed', pkgname, version)
                ret[pkgname] = {
                    'current': '{0} not installed'.format(version_num)
                }
                continue
            else:
                removal_targets.append(version_num)

        for target in removal_targets:

            # Get the uninstaller
            uninstaller = pkginfo[target].get('uninstaller', '')

            # If no uninstaller found, use the installer
            if not uninstaller:
                uninstaller = pkginfo[target].get('installer', '')

            # If still no uninstaller found, fail
            if not uninstaller:
                log.error(
                    'No installer or uninstaller configured for package %s',
                    pkgname,
                )
                ret[pkgname] = {'no uninstaller': target}
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
                        log.error('Unable to cache %s', uninstaller)
                        ret[pkgname] = {'unable to cache': uninstaller}
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
            uninstall_flags = pkginfo[target].get('uninstall_flags', '')

            if kwargs.get('extra_uninstall_flags'):
                uninstall_flags = '{0} {1}'.format(
                    uninstall_flags, kwargs.get('extra_uninstall_flags', ''))

            # Uninstall the software
            # Check Use Scheduler Option
            if pkginfo[target].get('use_scheduler', False):

                # Build Scheduled Task Parameters
                if pkginfo[target].get('msiexec', False):
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
                                             start_time='01:00',
                                             ac_only=False,
                                             stop_if_on_batteries=False)
                # Run Scheduled Task
                if not __salt__['task.run_wait'](name='update-salt-software'):
                    log.error('Failed to remove %s', pkgname)
                    log.error('Scheduled Task failed to run')
                    ret[pkgname] = {'uninstall status': 'failed'}
            else:
                # Build the install command
                cmd = []
                if pkginfo[target].get('msiexec', False):
                    cmd.extend(['msiexec', '/x', expanded_cached_pkg])
                else:
                    cmd.append(expanded_cached_pkg)
                cmd.extend(salt.utils.shlex_split(uninstall_flags))
                # Launch the command
                result = __salt__['cmd.run_all'](
                        cmd,
                        output_loglevel='trace',
                        python_shell=False,
                        redirect_stderr=True)
                if not result['retcode']:
                    ret[pkgname] = {'uninstall status': 'success'}
                    changed.append(pkgname)
                else:
                    log.error('Failed to remove %s', pkgname)
                    log.error('retcode %s', result['retcode'])
                    log.error('uninstaller output: %s', result['stdout'])
                    ret[pkgname] = {'uninstall status': 'failed'}

    # Get a new list of installed software
    new = list_pkgs(saltenv=saltenv)

    # Take the "old" package list and convert the values to strings in
    # preparation for the comparison below.
    __salt__['pkg_resource.stringify'](old)

    difference = salt.utils.compare_dicts(old, new)
    tries = 0
    while not all(name in difference for name in changed) and tries <= 1000:
        new = list_pkgs(saltenv=saltenv)
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

    .. versionadded:: 0.16.0

    Args:

        name (str): The name of the package to be deleted.

        version (str): The version of the package to be deleted. If this option
            is used in combination with the ``pkgs`` option below, then this
            version will be applied to all targeted packages.

        pkgs (list): A list of packages to delete. Must be passed as a python
            list. The ``name`` parameter will be ignored if this option is
            passed.

    Kwargs:
        saltenv (str): Salt environment. Default ``base``
        refresh (bool): Refresh package metadata. Default ``False``

    Returns:
        dict: A dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name,
                  pkgs=pkgs,
                  version=version,
                  **kwargs)


def get_repo_data(saltenv='base'):
    '''
    Returns the existing package meteadata db. Will create it, if it does not
    exist, however will not refresh it.

    Args:
        saltenv (str): Salt environment. Default ``base``

    Returns:
        dict: A dict containing contents of metadata db.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_repo_data
    '''
    # we only call refresh_db if it does not exist, as we want to return
    # the existing data even if its old, other parts of the code call this,
    # but they will call refresh if they need too.
    repo_details = _get_repo_details(saltenv)

    if repo_details.winrepo_age == -1:
        # no repo meta db
        log.debug('No winrepo.p cache file. Refresh pkg db now.')
        refresh_db(saltenv=saltenv)

    if 'winrepo.data' in __context__:
        log.trace('get_repo_data returning results from __context__')
        return __context__['winrepo.data']
    else:
        log.trace('get_repo_data called reading from disk')

    try:
        serial = salt.payload.Serial(__opts__)
        with salt.utils.fopen(repo_details.winrepo_file, 'rb') as repofile:
            try:
                repodata = serial.loads(repofile.read()) or {}
                __context__['winrepo.data'] = repodata
                return repodata
            except Exception as exc:
                log.exception(exc)
                return {}
    except IOError as exc:
        log.error('Not able to read repo file')
        log.exception(exc)
        return {}


def _get_name_map(saltenv='base'):
    '''
    Return a reverse map of full pkg names to the names recognized by winrepo.
    '''
    u_name_map = {}
    name_map = get_repo_data(saltenv).get('name_map', {})

    if six.PY3:
        return name_map

    for k in name_map:
        u_name_map[k.decode('utf-8')] = name_map[k]
    return u_name_map


def _get_package_info(name, saltenv='base'):
    '''
    Return package info. Returns empty map if package not available
    TODO: Add option for version
    '''
    return get_repo_data(saltenv).get('repo', {}).get(name, {})


def _get_latest_pkg_version(pkginfo):
    if len(pkginfo) == 1:
        return next(six.iterkeys(pkginfo))
    try:
        return sorted(list(pkginfo.keys())).pop()
    except IndexError:
        return ''


def compare_versions(ver1='', oper='==', ver2=''):
    '''
    Compare software package versions

    Args:
        ver1 (str): A software version to compare
        oper (str): The operand to use to compare
        ver2 (str): A software version to compare

    Returns:
        bool: True if the comparison is valid, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.compare_versions 1.2 >= 1.3
    '''
    return salt.utils.compare_versions(ver1, oper, ver2)

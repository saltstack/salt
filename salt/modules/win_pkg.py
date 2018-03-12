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

.. note::
    Version numbers can be `version number string`, `latest` and `Not Found`.
    Where `Not Found` means this module was not able to determine the version of
    the software installed, it can also be used as the version number in sls
    definitions file in these cases. Versions numbers are sorted in order of
    0,`Not Found`,`order version numbers`,...,`latest`.

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
import sys
from functools import cmp_to_key

# Import third party libs
from salt.ext import six
# pylint: disable=import-error,no-name-in-module
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse

# Import salt libs
from salt.exceptions import (CommandExecutionError,
                             SaltInvocationError,
                             SaltRenderError)
import salt.utils  # Can be removed once is_true, get_hash, compare_dicts are moved
import salt.utils.args
import salt.utils.files
import salt.utils.path
import salt.utils.pkg
import salt.utils.versions
import salt.syspaths
import salt.payload
from salt.exceptions import MinionError
from salt.utils.versions import LooseVersion
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
    if not names:
        return ''

    # Initialize the return dict with empty strings
    ret = {}
    for name in names:
        ret[name] = ''

    saltenv = kwargs.get('saltenv', 'base')
    # Refresh before looking for the latest version available
    refresh = salt.utils.is_true(kwargs.get('refresh', True))

    # no need to call _refresh_db_conditional as list_pkgs will do it
    installed_pkgs = list_pkgs(
        versions_as_list=True, saltenv=saltenv, refresh=refresh)
    log.trace('List of installed packages: {0}'.format(installed_pkgs))

    # iterate over all requested package names
    for name in names:
        latest_installed = '0'

        # get latest installed version of package
        if name in installed_pkgs:
            log.trace('Determining latest installed version of %s', name)
            try:
                # installed_pkgs[name] Can be version number or 'Not Found'
                # 'Not Found' occurs when version number is not found in the registry
                latest_installed = sorted(
                    installed_pkgs[name],
                    key=cmp_to_key(_reverse_cmp_pkg_versions)
                ).pop()
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

        # latest_available can be version number or 'latest' or even 'Not Found'
        latest_available = _get_latest_pkg_version(pkg_info)
        if latest_available:
            log.debug('Latest available version '
                      'of package {0} is {1}'.format(name, latest_available))

            # check, whether latest available version
            # is newer than latest installed version
            if compare_versions(ver1=six.text_type(latest_available),
                                oper='>',
                                ver2=six.text_type(latest_installed)):
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


def upgrade_available(name, **kwargs):
    '''
    Check whether or not an upgrade is available for a given package

    Args:
        name (str): The name of a single package

    Kwargs:
        refresh (bool): Refresh package metadata. Default ``True``
        saltenv (str): The salt environment. Default ``base``

    Returns:
        bool: True if new version available, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    saltenv = kwargs.get('saltenv', 'base')
    # Refresh before looking for the latest version available,
    # same default as latest_version
    refresh = salt.utils.is_true(kwargs.get('refresh', True))

    # if latest_version returns blank, the latest version is already installed or
    # their is no package definition. This is a salt standard which could be improved.
    return latest_version(name, saltenv=saltenv, refresh=refresh) != ''


def list_upgrades(refresh=True, **kwargs):
    '''
    List all available package upgrades on this system

    Args:
        refresh (bool): Refresh package metadata. Default ``True``

    Kwargs:
        saltenv (str): Salt environment. Default ``base``

    Returns:
        dict: A dictionary of packages with available upgrades

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    saltenv = kwargs.get('saltenv', 'base')
    refresh = salt.utils.is_true(refresh)
    _refresh_db_conditional(saltenv, force=refresh)

    installed_pkgs = list_pkgs(refresh=False, saltenv=saltenv)
    available_pkgs = get_repo_data(saltenv).get('repo')
    pkgs = {}
    for pkg in installed_pkgs:
        if pkg in available_pkgs:
            # latest_version() will be blank if the latest version is installed.
            # or the package name is wrong. Given we check available_pkgs, this
            # should not be the case of wrong package name.
            # Note: latest_version() is an expensive way to do this as it
            # calls list_pkgs each time.
            latest_ver = latest_version(pkg, refresh=False, saltenv=saltenv)
            if latest_ver:
                pkgs[pkg] = latest_ver

    return pkgs


def list_available(*names, **kwargs):
    '''
    Return a list of available versions of the specified package.

    Args:
        names (str): One or more package names

    Kwargs:

        saltenv (str): The salt environment to use. Default ``base``.

        refresh (bool): Refresh package metadata. Default ``False``.

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
        versions = sorted(
            list(pkginfo.keys()),
            key=cmp_to_key(_reverse_cmp_pkg_versions)
        )
    else:
        versions = {}
        for name in names:
            pkginfo = _get_package_info(name, saltenv=saltenv)
            if not pkginfo:
                continue
            verlist = sorted(
                list(pkginfo.keys()) if pkginfo else [],
                key=cmp_to_key(_reverse_cmp_pkg_versions)
            )
            versions[name] = verlist
    return versions


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    Args:
        name (str): One or more package names

    Kwargs:
        saltenv (str): The salt environment to use. Default ``base``.
        refresh (bool): Refresh package metadata. Default ``False``.

    Returns:
        str: version string when a single package is specified.
        dict: The package name(s) with the installed versions.

    .. code-block:: cfg
        {['<version>', '<version>', ]} OR
        {'<package name>': ['<version>', '<version>', ]}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package name01> <package name02>

    '''
    # Standard is return empty string even if not a valid name
    # TODO: Look at returning an error across all platforms with
    # CommandExecutionError(msg,info={'errors': errors })
    # available_pkgs = get_repo_data(saltenv).get('repo')
    # for name in names:
    #    if name in available_pkgs:
    #        ret[name] = installed_pkgs.get(name, '')

    saltenv = kwargs.get('saltenv', 'base')
    installed_pkgs = list_pkgs(saltenv=saltenv, refresh=kwargs.get('refresh', False))

    if len(names) == 1:
        return installed_pkgs.get(names[0], '')

    ret = {}
    for name in names:
        ret[name] = installed_pkgs.get(name, '')
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
    for pkg_name, val_list in six.iteritems(_get_reg_software()):
        if pkg_name in name_map:
            key = name_map[pkg_name]
            for val in val_list:
                if val == 'Not Found':
                    # Look up version from winrepo
                    pkg_info = _get_package_info(key, saltenv=saltenv)
                    if not pkg_info:
                        continue
                    for pkg_ver in pkg_info.keys():
                        if pkg_info[pkg_ver]['full_name'] == pkg_name:
                            val = pkg_ver
                __salt__['pkg_resource.add_pkg'](ret, key, val)
        else:
            key = pkg_name
            for val in val_list:
                __salt__['pkg_resource.add_pkg'](ret, key, val)

    __salt__['pkg_resource.sort_pkglist'](ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


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

    reg_software = {}
    hive = 'HKLM'
    key = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"

    def update(hive, key, reg_key, use_32bit):
        # 2018 this code has been update to reflect some of utils/pkg/win.py logic
        # i.e. check_reg, and checking of DisplayName and DisplayVersion.
        d_name = ''
        d_vers = ''

        d_name_regdata = __salt__['reg.read_value'](hive,
                                                    '{0}\\{1}'.format(key, reg_key),
                                                    'DisplayName',
                                                    use_32bit)
        if (not d_name_regdata['success'] or
            d_name_regdata['vtype'] not in ['REG_SZ', 'REG_EXPAND_SZ'] or
                d_name_regdata['vdata'] in ['(value not set)', None, False]):
            return
        d_name = d_name_regdata['vdata']

        d_vers_regdata = __salt__['reg.read_value'](hive,
                                                    '{0}\\{1}'.format(key, reg_key),
                                                    'DisplayVersion',
                                                    use_32bit)
        if (not d_vers_regdata['success'] or
            d_vers_regdata['vtype'] not in ['REG_SZ', 'REG_EXPAND_SZ', 'REG_DWORD'] or
                d_vers_regdata['vdata'] in [None, False]):
            return

        if isinstance(d_vers_regdata['vdata'], int):
            d_vers = six.text_type(d_vers_regdata['vdata'])
        else:
            d_vers = d_vers_regdata['vdata']

        if not d_vers or d_vers == '(value not set)':
            d_vers = 'Not Found'

        check_ok = False
        for check_reg in ['UninstallString', 'QuietUninstallString', 'ModifyPath']:
            check_regdata = __salt__['reg.read_value'](hive,
                                                       '{0}\\{1}'.format(key, reg_key),
                                                       check_reg,
                                                       use_32bit)
            if (not check_regdata['success'] or
                check_regdata['vtype'] not in ['REG_SZ', 'REG_EXPAND_SZ'] or
                    check_regdata['vdata'] in ['(value not set)', None, False]):
                continue
            else:
                check_ok = True

        if not check_ok:
            return

        if d_name not in ignore_list:
            # some MS Office updates don't register a product name which means
            # their information is useless
            reg_software.setdefault(d_name, []).append(d_vers)

    for reg_key in __salt__['reg.list_keys'](hive, key):
        update(hive, key, reg_key, False)

    for reg_key in __salt__['reg.list_keys'](hive, key, True):
        update(hive, key, reg_key, True)

    return reg_software


def _refresh_db_conditional(saltenv, **kwargs):
    '''
    Internal use only in this module, has a different set of defaults and
    returns True or False. And supports checking the age of the existing
    generated metadata db, as well as ensure metadata db exists to begin with

    Args:
        saltenv (str): Salt environment

    Kwargs:

        force (bool):
            Force a refresh if the minimum age has been reached. Default is
            False.

        failhard (bool):
            If ``True``, an error will be raised if any repo SLS files failed to
            process.

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
    r'''
    Generates the local software metadata database (`winrepo.p`) on the minion.
    The database is stored in a serialized format located by default at the
    following location:

    `C:\salt\var\cache\salt\minion\files\base\win\repo-ng\winrepo.p`

    This module performs the following steps to generate the software metadata
    database:

    - Fetch the package definition files (.sls) from `winrepo_source_dir`
      (default `salt://win/repo-ng`) and cache them in
      `<cachedir>\files\<saltenv>\<winrepo_source_dir>`
      (default: `C:\salt\var\cache\salt\minion\files\base\win\repo-ng`)
    - Call :py:func:`pkg.genrepo <salt.modules.win_pkg.genrepo>` to parse the
      package definition files and generate the repository metadata database
      file (`winrepo.p`)
    - Return the report received from
      :py:func:`pkg.genrepo <salt.modules.win_pkg.genrepo>`

    The default winrepo directory on the master is `/srv/salt/win/repo-ng`. All
    files that end with `.sls` in this and all subdirectories will be used to
    generate the repository metadata database (`winrepo.p`).

    .. note::
        - Hidden directories (directories beginning with '`.`', such as
          '`.git`') will be ignored.

    .. note::
        There is no need to call `pkg.refresh_db` every time you work with the
        pkg module. Automatic refresh will occur based on the following minion
        configuration settings:
            - `winrepo_cache_expire_min`
            - `winrepo_cache_expire_max`
        However, if the package definition files have changed, as would be the
        case if you are developing a new package definition, this function
        should be called to ensure the minion has the latest information about
        packages available to it.

    .. warning::
        Directories and files fetched from <winrepo_source_dir>
        (`/srv/salt/win/repo-ng`) will be processed in alphabetical order. If
        two or more software definition files contain the same name, the last
        one processed replaces all data from the files processed before it.

    For more information see
    :ref:`Windows Software Repository <windows-package-manager>`

    Kwargs:

        saltenv (str): Salt environment. Default: ``base``

        verbose (bool):
            Return a verbose data structure which includes 'success_list', a
            list of all sls files and the package names contained within.
            Default is 'False'

        failhard (bool):
            If ``True``, an error will be raised if any repo SLS files fails to
            process. If ``False``, no error will be raised, and a dictionary
            containing the full results will be returned.

    Returns:
        dict: A dictionary containing the results of the database refresh.

    .. note::
        A result with a `total: 0` generally means that the files are in the
        wrong location on the master. Try running the following command on the
        minion: `salt-call -l debug pkg.refresh saltenv=base`

    .. warning::
        When calling this command from a state using `module.run` be sure to
        pass `failhard: False`. Otherwise the state will report failure if it
        encounters a bad software definition file.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
        salt '*' pkg.refresh_db saltenv=base
    '''
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
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
    log.info('Fetching *.sls files from {0}'.format(repo_details.winrepo_source_dir))
    __salt__['cp.cache_dir'](
        path=repo_details.winrepo_source_dir,
        saltenv=saltenv,
        include_pat='*.sls',
        exclude_pat=r'E@\/\..*?\/'  # Exclude all hidden directories (.git)
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
                'minion configuration option \'winrepo_cachefile\' has been '
                'ignored as its value (%s) is invalid. Please ensure this '
                'option is set to a valid filename.',
                __opts__['winrepo_cachefile']
            )

        # Do some safety checks on the repo_path as its contents can be removed,
        # this includes check for bad coding
        system_root = os.environ.get('SystemRoot', r'C:\Windows')
        if not salt.utils.path.safe_path(
                path=local_dest,
                allow_path='\\'.join([system_root, 'TEMP'])):

            raise CommandExecutionError(
                'Attempting to delete files from a possibly unsafe location: '
                '{0}'.format(local_dest)
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
            of all sls files and the package names contained within.
            Default ``False``.

        failhard (bool):
            If ``True``, an error will be raised if any repo SLS files failed
            to process. If ``False``, no error will be raised, and a dictionary
            containing the full results will be returned.

    .. note::
        - Hidden directories (directories beginning with '`.`', such as
          '`.git`') will be ignored.

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

        # Skip hidden directories (.git)
        if re.search(r'[\\/]\..*', root):
            log.debug('Skipping files in directory: {0}'.format(root))
            continue

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
    # TODO: 2016.11 has PY2 mode as 'w+b' develop has 'w+' ? PY3 is 'wb+'
    # also the reading of this is 'rb' in get_repo_data()
    mode = 'w+' if six.PY2 else 'wb+'

    with salt.utils.fopen(repo_details.winrepo_file, mode) as repo_cache:
        repo_cache.write(serial.dumps(ret))
    # For some reason we can not save ret into __context__['winrepo.data'] as this breaks due to utf8 issues
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


def _repo_process_pkg_sls(filename, short_path_name, ret, successful_verbose):
    renderers = salt.loader.render(__opts__, __salt__)

    def _failed_compile(prefix_msg, error_msg):
        log.error('{0} \'{1}\': {2} '.format(prefix_msg, short_path_name, error_msg))
        ret.setdefault('errors', {})[short_path_name] = ['{0}, {1} '.format(prefix_msg, error_msg)]
        return False

    try:
        config = salt.template.compile_template(
            filename,
            renderers,
            __opts__['renderer'],
            __opts__.get('renderer_blacklist', ''),
            __opts__.get('renderer_whitelist', ''))
    except SaltRenderError as exc:
        return _failed_compile('Failed to compile', exc)
    except Exception as exc:
        return _failed_compile('Failed to read', exc)

    if config and isinstance(config, dict):
        revmap = {}
        errors = []
        for pkgname, version_list in six.iteritems(config):
            if pkgname in ret['repo']:
                log.error(
                    'package \'%s\' within \'%s\' already defined, skipping',
                    pkgname, short_path_name
                )
                errors.append('package \'{0}\' already defined'.format(pkgname))
                break
            for version_str, repodata in six.iteritems(version_list):
                # Ensure version is a string/unicode
                if not isinstance(version_str, six.string_types):
                    msg = (
                        'package \'{0}\'{{0}}, version number {1} '
                        'is not a string'.format(pkgname, version_str)
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
                        .format(pkgname, version_str)
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
            ret.setdefault('repo', {}).update(config)
            ret.setdefault('name_map', {}).update(revmap)
            successful_verbose[short_path_name] = config.keys()
    elif config:
        return _failed_compile('Compiled contents', 'not a dictionary/hash')
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
    source_hash = six.text_type(source_hash)
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


def _get_msiexec(use_msiexec):
    '''
    Return if msiexec.exe will be used and the command to invoke it.
    '''
    if use_msiexec is False:
        return False, ''
    if isinstance(use_msiexec, six.string_types):
        if os.path.isfile(use_msiexec):
            return True, use_msiexec
        else:
            log.warning(("msiexec path '{0}' not found. Using system registered"
                         " msiexec instead").format(use_msiexec))
            use_msiexec = True
    if use_msiexec is True:
        return True, 'msiexec'


def install(name=None, refresh=False, pkgs=None, **kwargs):
    r'''
    Install the passed package(s) on the system using winrepo

    Args:

        name (str):
            The name of a single package, or a comma-separated list of packages
            to install. (no spaces after the commas)

        refresh (bool):
            Boolean value representing whether or not to refresh the winrepo db.
            Default ``False``.

        pkgs (list):
            A list of packages to install from a software repository. All
            packages listed under ``pkgs`` will be installed via a single
            command.

            You can specify a version by passing the item as a dict:

            CLI Example:

            .. code-block:: bash

                # will install the latest version of foo and bar
                salt '*' pkg.install pkgs='["foo", "bar"]'

                # will install the latest version of foo and version 1.2.3 of bar
                salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3"}]'

    Kwargs:

        version (str):
            The specific version to install. If omitted, the latest version will
            be installed. Recommend for use when installing a single package.

            If passed with a list of packages in the ``pkgs`` parameter, the
            version will be ignored.

            CLI Example:

             .. code-block:: bash

                # Version is ignored
                salt '*' pkg.install pkgs="['foo', 'bar']" version=1.2.3

            If passed with a comma separated list in the ``name`` parameter, the
            version will apply to all packages in the list.

            CLI Example:

             .. code-block:: bash

                # Version 1.2.3 will apply to packages foo and bar
                salt '*' pkg.install foo,bar version=1.2.3

        extra_install_flags (str):
            Additional install flags that will be appended to the
            ``install_flags`` defined in the software definition file. Only
            applies when single package is passed.

        saltenv (str):
            Salt environment. Default 'base'

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

    if len(pkg_params) > 1:
        if kwargs.get('extra_install_flags') is not None:
            log.warning('\'extra_install_flags\' argument will be ignored for '
                        'multiple package targets')

    # Windows expects an Options dictionary containing 'version'
    for pkg in pkg_params:
        pkg_params[pkg] = {'version': pkg_params[pkg]}

    if not pkg_params:
        log.error('No package definition found')
        return {}

    if not pkgs and len(pkg_params) == 1:
        # Only use the 'version' param if a single item was passed to the 'name'
        # parameter
        pkg_params = {
            name: {
                'version': kwargs.get('version'),
                'extra_install_flags': kwargs.get('extra_install_flags')
            }
        }

    # Get a list of currently installed software for comparison at the end
    old = list_pkgs(saltenv=saltenv, refresh=refresh, versions_as_list=True)

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

        # Get the version number passed or the latest available (must be a string)
        version_num = None
        if options:
            version_num = options.get('version', None)
            #  Using the salt cmdline with version=5.3 might be interpreted
            #  as a float it must be converted to a string in order for
            #  string matching to work.
            if not isinstance(version_num, six.text_type) and version_num is not None:
                version_num = six.text_type(version_num)

        if not version_num:
            if pkg_name in old:
                log.debug('A version ({0}) already installed for package '
                          '{1}'.format(version_num, pkg_name))
                continue
            # following can be version number or latest or Not Found
            version_num = _get_latest_pkg_version(pkginfo)

        if version_num == 'latest' and 'latest' not in pkginfo:
            version_num = _get_latest_pkg_version(pkginfo)

        # Check if the version is already installed
        if version_num in old.get(pkg_name, []):
            # Desired version number already installed
            ret[pkg_name] = {'current': version_num}
            continue
        # If version number not installed, is the version available?
        elif version_num != 'latest' and version_num not in pkginfo:
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
                __salt__['cp.cache_dir'](path=path,
                                         saltenv=saltenv,
                                         include_empty=False,
                                         include_pat=None,
                                         exclude_pat='E@init.sls$')

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

        # Compute msiexec string
        use_msiexec, msiexec = _get_msiexec(pkginfo[version_num].get('msiexec', False))

        # Build cmd and arguments
        # cmd and arguments must be separated for use with the task scheduler
        cmd_shell = os.getenv('ComSpec', '{0}\\system32\\cmd.exe'.format(os.getenv('WINDIR')))
        if use_msiexec:
            arguments = '"{0}" /I "{1}"'.format(msiexec, cached_pkg)
            if pkginfo[version_num].get('allusers', True):
                arguments = '{0} ALLUSERS=1'.format(arguments)
        else:
            arguments = '"{0}"'.format(cached_pkg)

        if install_flags:
            arguments = '{0} {1}'.format(arguments, install_flags)

        # Install the software
        # Check Use Scheduler Option
        if pkginfo[version_num].get('use_scheduler', False):
            # Create Scheduled Task
            __salt__['task.create_task'](name='update-salt-software',
                                         user_name='System',
                                         force=True,
                                         action_type='Execute',
                                         cmd=cmd_shell,
                                         arguments='/s /c "{0}"'.format(arguments),
                                         start_in=cache_path,
                                         trigger_type='Once',
                                         start_date='1975-01-01',
                                         start_time='01:00',
                                         ac_only=False,
                                         stop_if_on_batteries=False)

            # Run Scheduled Task
            # Special handling for installing salt
            if re.search(r'salt[\s_.-]*minion',
                         pkg_name,
                         flags=re.IGNORECASE + re.UNICODE) is not None:
                ret[pkg_name] = {'install status': 'task started'}
                if not __salt__['task.run'](name='update-salt-software'):
                    log.error('Failed to install {0}'.format(pkg_name))
                    log.error('Scheduled Task failed to run')
                    ret[pkg_name] = {'install status': 'failed'}
                else:

                    # Make sure the task is running, try for 5 secs
                    t_end = time.time() + 5
                    while time.time() < t_end:
                        time.sleep(0.25)
                        task_running = __salt__['task.status'](
                                'update-salt-software') == 'Running'
                        if task_running:
                            break

                    if not task_running:
                        log.error(
                            'Failed to install {0}'.format(pkg_name))
                        log.error('Scheduled Task failed to run')
                        ret[pkg_name] = {'install status': 'failed'}

            # All other packages run with task scheduler
            else:
                if not __salt__['task.run_wait'](name='update-salt-software'):
                    log.error('Failed to install {0}'.format(pkg_name))
                    log.error('Scheduled Task failed to run')
                    ret[pkg_name] = {'install status': 'failed'}
        else:
            # Launch the command
            result = __salt__['cmd.run_all']('"{0}" /s /c "{1}"'.format(cmd_shell, arguments),
                                             cache_path,
                                             output_loglevel='trace',
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
            elif result['retcode'] == 1641:
                # 1641 is ERROR_SUCCESS_REBOOT_INITIATED
                ret[pkg_name] = {'install status': 'success, reboot initiated'}
                changed.append(pkg_name)
            else:
                log.error('Failed to install {0}'.format(pkg_name))
                log.error('retcode {0}'.format(result['retcode']))
                log.error('installer output: {0}'.format(result['stdout']))
                ret[pkg_name] = {'install status': 'failed'}

    # Get a new list of installed software
    new = list_pkgs(saltenv=saltenv, refresh=False)

    # Take the "old" package list and convert the values to strings in
    # preparation for the comparison below.
    __salt__['pkg_resource.stringify'](old)

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
    refresh = salt.utils.is_true(kwargs.get('refresh', True))
    saltenv = kwargs.get('saltenv', 'base')
    log.warning('pkg.upgrade not implemented on Windows yet refresh:%s saltenv:%s', refresh, saltenv)
    # Uncomment the below once pkg.upgrade has been implemented

    # if salt.utils.is_true(refresh):
    #    refresh_db()
    return {}


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove the passed package(s) from the system using winrepo

    .. versionadded:: 0.16.0

    Args:
        name (str):
            The name(s) of the package(s) to be uninstalled. Can be a
            single package or a comma delimited list of packages, no spaces.

        pkgs (list):
            A list of packages to delete. Must be passed as a python list. The
            ``name`` parameter will be ignored if this option is passed.

    Kwargs:

        version (str):
            The version of the package to be uninstalled. If this option is
            used to to uninstall multiple packages, then this version will be
            applied to all targeted packages. Recommended using only when
            uninstalling a single package. If this parameter is omitted, the
            latest version will be uninstalled.

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
    changed = []  # list of changed package names
    for pkgname, version_num in six.iteritems(pkg_params):

        # Load package information for the package
        pkginfo = _get_package_info(pkgname, saltenv=saltenv)

        # Make sure pkginfo was found
        if not pkginfo:
            msg = 'Unable to locate package {0}'.format(pkgname)
            log.error(msg)
            ret[pkgname] = msg
            continue

        # Check to see if package is installed on the system
        if pkgname not in old:
            log.debug('%s %s not installed', pkgname, version_num if version_num else '')
            ret[pkgname] = {'current': 'not installed'}
            continue

        removal_targets = []
        # Only support a single version number
        if version_num is not None:
            #  Using the salt cmdline with version=5.3 might be interpreted
            #  as a float it must be converted to a string in order for
            #  string matching to work.
            version_num = six.text_type(version_num)

        # At least one version of the software is installed.
        if version_num is None:
            for ver_install in old[pkgname]:
                if ver_install not in pkginfo and 'latest' in pkginfo:
                    log.debug('%s %s using package latest entry to to remove', pkgname, version_num)
                    removal_targets.append('latest')
                else:
                    removal_targets.append(ver_install)
        else:
            if version_num in pkginfo:
                # we known how to remove this version
                if version_num in old[pkgname]:
                    removal_targets.append(version_num)
                else:
                    log.debug('%s %s not installed', pkgname, version_num)
                    ret[pkgname] = {'current': '{0} not installed'.format(version_num)}
                    continue
            elif 'latest' in pkginfo:
                # we do not have version entry, assume software can self upgrade and use latest
                log.debug('%s %s using package latest entry to to remove', pkgname, version_num)
                removal_targets.append('latest')

        if not removal_targets:
            log.error('%s %s no definition to remove this version', pkgname, version_num)
            ret[pkgname] = {
                    'current': '{0} no definition, cannot removed'.format(version_num)
                }
            continue

        for target in removal_targets:
            # Get the uninstaller
            uninstaller = pkginfo[target].get('uninstaller', '')
            cache_dir = pkginfo[target].get('cache_dir', False)
            uninstall_flags = pkginfo[target].get('uninstall_flags', '')

            # If no uninstaller found, use the installer with uninstall flags
            if not uninstaller and uninstall_flags:
                uninstaller = pkginfo[target].get('installer', '')

            # If still no uninstaller found, fail
            if not uninstaller:
                log.error(
                    'No installer or uninstaller configured for package %s',
                    pkgname,
                )
                ret[pkgname] = {'no uninstaller defined': target}
                continue

            # Where is the uninstaller
            if uninstaller.startswith(('salt:', 'http:', 'https:', 'ftp:')):

                # Check for the 'cache_dir' parameter in the .sls file
                # If true, the entire directory will be cached instead of the
                # individual file. This is useful for installations that are not
                # single files

                if cache_dir and uninstaller.startswith('salt:'):
                    path, _ = os.path.split(uninstaller)
                    __salt__['cp.cache_dir'](path,
                                             saltenv,
                                             False,
                                             None,
                                             'E@init.sls$')

                # Check to see if the uninstaller is cached
                cached_pkg = __salt__['cp.is_cached'](uninstaller, saltenv)
                if not cached_pkg:
                    # It's not cached. Cache it, mate.
                    cached_pkg = __salt__['cp.cache_file'](uninstaller, saltenv)

                    # Check if the uninstaller was cached successfully
                    if not cached_pkg:
                        log.error('Unable to cache %s', uninstaller)
                        ret[pkgname] = {'unable to cache': uninstaller}
                        continue

                # Compare the hash of the cached installer to the source only if
                # the file is hosted on salt:
                # TODO cp.cache_file does cache and hash checking? So why do it again?
                if uninstaller.startswith('salt:'):
                    if __salt__['cp.hash_file'](uninstaller, saltenv) != \
                            __salt__['cp.hash_file'](cached_pkg):
                        try:
                            cached_pkg = __salt__['cp.cache_file'](
                                uninstaller, saltenv)
                        except MinionError as exc:
                            return '{0}: {1}'.format(exc, uninstaller)

                        # Check if the installer was cached successfully
                        if not cached_pkg:
                            log.error('Unable to cache {0}'.format(uninstaller))
                            ret[pkgname] = {'unable to cache': uninstaller}
                            continue
            else:
                # Run the uninstaller directly
                # (not hosted on salt:, https:, etc.)
                cached_pkg = os.path.expandvars(uninstaller)

            # Fix non-windows slashes
            cached_pkg = cached_pkg.replace('/', '\\')
            cache_path, _ = os.path.split(cached_pkg)

            # os.path.expandvars is not required as we run everything through cmd.exe /s /c

            if kwargs.get('extra_uninstall_flags'):
                uninstall_flags = '{0} {1}'.format(
                    uninstall_flags, kwargs.get('extra_uninstall_flags', ''))

            # Compute msiexec string
            use_msiexec, msiexec = _get_msiexec(pkginfo[target].get('msiexec', False))
            cmd_shell = os.getenv('ComSpec', '{0}\\system32\\cmd.exe'.format(os.getenv('WINDIR')))

            # Build cmd and arguments
            # cmd and arguments must be separated for use with the task scheduler
            if use_msiexec:
                # Check if uninstaller is set to {guid}, if not we assume its a remote msi file.
                # which has already been downloaded.
                arguments = '"{0}" /X "{1}"'.format(msiexec, cached_pkg)
            else:
                arguments = '"{0}"'.format(cached_pkg)

            if uninstall_flags:
                arguments = '{0} {1}'.format(arguments, uninstall_flags)

            # Uninstall the software
            changed.append(pkgname)
            # Check Use Scheduler Option
            if pkginfo[target].get('use_scheduler', False):
                # Create Scheduled Task
                __salt__['task.create_task'](name='update-salt-software',
                                             user_name='System',
                                             force=True,
                                             action_type='Execute',
                                             cmd=cmd_shell,
                                             arguments='/s /c "{0}"'.format(arguments),
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
                # Launch the command
                result = __salt__['cmd.run_all'](
                        '"{0}" /s /c "{1}"'.format(cmd_shell, arguments),
                        output_loglevel='trace',
                        python_shell=False,
                        redirect_stderr=True)
                if not result['retcode']:
                    ret[pkgname] = {'uninstall status': 'success'}
                    changed.append(pkgname)
                elif result['retcode'] == 3010:
                    # 3010 is ERROR_SUCCESS_REBOOT_REQUIRED
                    report_reboot_exit_codes = kwargs.pop(
                        'report_reboot_exit_codes', True)
                    if report_reboot_exit_codes:
                        __salt__['system.set_reboot_required_witnessed']()
                    ret[pkgname] = {'uninstall status': 'success, reboot required'}
                    changed.append(pkgname)
                elif result['retcode'] == 1641:
                    # 1641 is ERROR_SUCCESS_REBOOT_INITIATED
                    ret[pkgname] = {'uninstall status': 'success, reboot initiated'}
                    changed.append(pkgname)
                else:
                    log.error('Failed to remove %s', pkgname)
                    log.error('retcode %s', result['retcode'])
                    log.error('uninstaller output: %s', result['stdout'])
                    ret[pkgname] = {'uninstall status': 'failed'}

    # Get a new list of installed software
    new = list_pkgs(saltenv=saltenv, refresh=False)

    # Take the "old" package list and convert the values to strings in
    # preparation for the comparison below.
    __salt__['pkg_resource.stringify'](old)

    # Check for changes in the registry
    difference = salt.utils.compare_dicts(old, new)
    found_chgs = all(name in difference for name in changed)
    end_t = time.time() + 3  # give it 3 seconds to catch up.
    while not found_chgs and time.time() < end_t:
        time.sleep(0.5)
        new = list_pkgs(saltenv=saltenv, refresh=False)
        difference = salt.utils.compare_dicts(old, new)
        found_chgs = all(name in difference for name in changed)

    if not found_chgs:
        log.warning('Expected changes for package removal may not have occured')

    # Compare the software list before and after
    # Add the difference to ret
    ret.update(difference)
    return ret


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported, this function is identical to
    ``remove()``.

    .. versionadded:: 0.16.0

    Args:

        name (str): The name of the package to be deleted.

        version (str):
            The version of the package to be deleted. If this option is
            used in combination with the ``pkgs`` option below, then this
            version will be applied to all targeted packages.

        pkgs (list):
            A list of packages to delete. Must be passed as a python
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

    if not six.PY2:
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


def _reverse_cmp_pkg_versions(pkg1, pkg2):
    '''
    Compare software package versions
    '''
    return 1 if LooseVersion(pkg1) > LooseVersion(pkg2) else -1


def _get_latest_pkg_version(pkginfo):
    '''
    Returns the latest version of the package.
    Will return 'latest' or version number string, and
    'Not Found' if 'Not Found' is the only entry.
    '''
    if len(pkginfo) == 1:
        return next(six.iterkeys(pkginfo))
    try:
        return sorted(
            pkginfo,
            key=cmp_to_key(_reverse_cmp_pkg_versions)
        ).pop()
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
    if not ver1:
        raise SaltInvocationError('compare_version, ver1 is blank')
    if not ver2:
        raise SaltInvocationError('compare_version, ver2 is blank')

    # Support version being the special meaning of 'latest'
    if ver1 == 'latest':
        ver1 = six.text_type(sys.maxsize)
    if ver2 == 'latest':
        ver2 = six.text_type(sys.maxsize)
    # Support version being the special meaning of 'Not Found'
    if ver1 == 'Not Found':
        ver1 = '0.0.0.0.0'
    if ver2 == 'Not Found':
        ver2 = '0.0.0.0.0'

    return salt.utils.compare_versions(ver1, oper, ver2, ignore_epoch=True)

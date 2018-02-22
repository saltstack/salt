# -*- coding: utf-8 -*-
'''
Package support for openSUSE via the zypper package manager

:depends: - ``rpm`` Python module.  Install with ``zypper install rpm-python``

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import fnmatch
import logging
import re
import os
import time
import datetime

# Import 3rd-party libs
# pylint: disable=import-error,redefined-builtin,no-name-in-module
from salt.ext import six
from salt.ext.six.moves import configparser
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse
# pylint: enable=import-error,redefined-builtin,no-name-in-module

from xml.dom import minidom as dom
from xml.parsers.expat import ExpatError

# Import salt libs
import salt.utils.data
import salt.utils.event
import salt.utils.files
import salt.utils.functools
import salt.utils.path
import salt.utils.pkg
import salt.utils.stringutils
import salt.utils.systemd
from salt.utils.versions import LooseVersion
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError

log = logging.getLogger(__name__)

HAS_ZYPP = False
ZYPP_HOME = '/etc/zypp'
LOCKS = '{0}/locks'.format(ZYPP_HOME)
REPOS = '{0}/repos.d'.format(ZYPP_HOME)
DEFAULT_PRIORITY = 99

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is openSUSE
    '''
    if __grains__.get('os_family', '') != 'Suse':
        return (False, "Module zypper: non SUSE OS not suppored by zypper package manager")
    # Not all versions of SUSE use zypper, check that it is available
    if not salt.utils.path.which('zypper'):
        return (False, "Module zypper: zypper package manager not found")
    return __virtualname__


class _Zypper(object):
    '''
    Zypper parallel caller.
    Validates the result and either raises an exception or reports an error.
    Allows serial zypper calls (first came, first won).
    '''

    SUCCESS_EXIT_CODES = [0, 100, 101, 102, 103]
    LOCK_EXIT_CODE = 7
    XML_DIRECTIVES = ['-x', '--xmlout']
    ZYPPER_LOCK = '/var/run/zypp.pid'
    TAG_RELEASED = 'zypper/released'
    TAG_BLOCKED = 'zypper/blocked'

    def __init__(self):
        '''
        Constructor
        '''
        self.__called = False
        self._reset()

    def _reset(self):
        '''
        Resets values of the call setup.

        :return:
        '''
        self.__cmd = ['zypper', '--non-interactive']
        self.__exit_code = 0
        self.__call_result = dict()
        self.__error_msg = ''
        self.__env = {'SALT_RUNNING': "1"}  # Subject to change

        # Call config
        self.__xml = False
        self.__no_lock = False
        self.__no_raise = False
        self.__refresh = False
        self.__ignore_repo_failure = False
        self.__systemd_scope = False

    def __call__(self, *args, **kwargs):
        '''
        :param args:
        :param kwargs:
        :return:
        '''
        # Ignore exit code for 106 (repo is not available)
        if 'no_repo_failure' in kwargs:
            self.__ignore_repo_failure = kwargs['no_repo_failure']
        if 'systemd_scope' in kwargs:
            self.__systemd_scope = kwargs['systemd_scope']
        return self

    def __getattr__(self, item):
        '''
        Call configurator.

        :param item:
        :return:
        '''
        # Reset after the call
        if self.__called:
            self._reset()
            self.__called = False

        if item == 'xml':
            self.__xml = True
        elif item == 'nolock':
            self.__no_lock = True
        elif item == 'noraise':
            self.__no_raise = True
        elif item == 'refreshable':
            self.__refresh = True
        elif item == 'call':
            return self.__call
        else:
            return self.__dict__[item]

        # Prevent the use of "refreshable" together with "nolock".
        if self.__no_lock:
            self.__no_lock = not self.__refresh

        return self

    @property
    def exit_code(self):
        return self.__exit_code

    @exit_code.setter
    def exit_code(self, exit_code):
        self.__exit_code = int(exit_code or '0')

    @property
    def error_msg(self):
        return self.__error_msg

    @error_msg.setter
    def error_msg(self, msg):
        if self._is_error():
            self.__error_msg = msg and os.linesep.join(msg) or "Check Zypper's logs."

    @property
    def stdout(self):
        return self.__call_result.get('stdout', '')

    @property
    def stderr(self):
        return self.__call_result.get('stderr', '')

    @property
    def pid(self):
        return self.__call_result.get('pid', '')

    def _is_error(self):
        '''
        Is this is an error code?

        :return:
        '''
        return self.exit_code not in self.SUCCESS_EXIT_CODES

    def _is_lock(self):
        '''
        Is this is a lock error code?

        :return:
        '''
        return self.exit_code == self.LOCK_EXIT_CODE

    def _is_xml_mode(self):
        '''
        Is Zypper's output is in XML format?

        :return:
        '''
        return [itm for itm in self.XML_DIRECTIVES if itm in self.__cmd] and True or False

    def _check_result(self):
        '''
        Check and set the result of a zypper command. In case of an error,
        either raise a CommandExecutionError or extract the error.

        result
            The result of a zypper command called with cmd.run_all
        '''
        if not self.__call_result:
            raise CommandExecutionError('No output result from Zypper?')

        self.exit_code = self.__call_result['retcode']
        if self._is_lock():
            return False

        if self._is_error():
            _error_msg = list()
            if not self._is_xml_mode():
                msg = self.__call_result['stderr'] and self.__call_result['stderr'].strip() or ""
                if msg:
                    _error_msg.append(msg)
            else:
                try:
                    doc = dom.parseString(self.__call_result['stdout'])
                except ExpatError as err:
                    log.error(err)
                    doc = None
                if doc:
                    msg_nodes = doc.getElementsByTagName('message')
                    for node in msg_nodes:
                        if node.getAttribute('type') == 'error':
                            _error_msg.append(node.childNodes[0].nodeValue)
                elif self.__call_result['stderr'].strip():
                    _error_msg.append(self.__call_result['stderr'].strip())
            self.error_msg = _error_msg
        return True

    def __call(self, *args, **kwargs):
        '''
        Call Zypper.

        :param state:
        :return:
        '''
        self.__called = True
        if self.__xml:
            self.__cmd.append('--xmlout')
        if not self.__refresh:
            self.__cmd.append('--no-refresh')

        self.__cmd.extend(args)
        kwargs['output_loglevel'] = 'trace'
        kwargs['python_shell'] = False
        kwargs['env'] = self.__env.copy()
        if self.__no_lock:
            kwargs['env']['ZYPP_READONLY_HACK'] = "1"  # Disables locking for read-only operations. Do not try that at home!

        # Zypper call will stuck here waiting, if another zypper hangs until forever.
        # However, Zypper lock needs to be always respected.
        was_blocked = False
        while True:
            cmd = []
            if self.__systemd_scope:
                cmd.extend(['systemd-run', '--scope'])
            cmd.extend(self.__cmd)
            log.debug("Calling Zypper: " + ' '.join(cmd))
            self.__call_result = __salt__['cmd.run_all'](cmd, **kwargs)
            if self._check_result():
                break

            if os.path.exists(self.ZYPPER_LOCK):
                try:
                    with salt.utils.files.fopen(self.ZYPPER_LOCK) as rfh:
                        data = __salt__['ps.proc_info'](int(rfh.readline()),
                                                        attrs=['pid', 'name', 'cmdline', 'create_time'])
                        data['cmdline'] = ' '.join(data['cmdline'])
                        data['info'] = 'Blocking process created at {0}.'.format(
                            datetime.datetime.utcfromtimestamp(data['create_time']).isoformat())
                        data['success'] = True
                except Exception as err:
                    data = {'info': 'Unable to retrieve information about blocking process: {0}'.format(err.message),
                            'success': False}
            else:
                data = {'info': 'Zypper is locked, but no Zypper lock has been found.', 'success': False}

            if not data['success']:
                log.debug("Unable to collect data about blocking process.")
            else:
                log.debug("Collected data about blocking process.")

            __salt__['event.fire_master'](data, self.TAG_BLOCKED)
            log.debug("Fired a Zypper blocked event to the master with the data: %s", data)
            log.debug("Waiting 5 seconds for Zypper gets released...")
            time.sleep(5)
            if not was_blocked:
                was_blocked = True

        if was_blocked:
            __salt__['event.fire_master']({'success': not len(self.error_msg),
                                           'info': self.error_msg or 'Zypper has been released'},
                                          self.TAG_RELEASED)
        if self.error_msg and not self.__no_raise and not self.__ignore_repo_failure:
            raise CommandExecutionError('Zypper command failure: {0}'.format(self.error_msg))

        return self._is_xml_mode() and dom.parseString(self.__call_result['stdout']) or self.__call_result['stdout']


__zypper__ = _Zypper()


class Wildcard(object):
    '''
    .. versionadded:: 2017.7.0

    Converts string wildcard to a zypper query.
    Example:
       '1.2.3.4*' is '1.2.3.4.whatever.is.here' and is equal to:
       '1.2.3.4 >= and < 1.2.3.5'

    :param ptn: Pattern
    :return: Query range
    '''

    Z_OP = ['<', '<=', '=', '>=', '>']

    def __init__(self, zypper):
        '''
        :type zypper: a reference to an instance of a _Zypper class.
        '''
        self.name = None
        self.version = None
        self.zypper = zypper
        self._attr_solvable_version = 'edition'
        self._op = None

    def __call__(self, pkg_name, pkg_version):
        '''
        Convert a string wildcard to a zypper query.

        :param pkg_name:
        :param pkg_version:
        :return:
        '''
        if pkg_version:
            self.name = pkg_name
            self._set_version(pkg_version)  # Dissects possible operator
            versions = sorted([LooseVersion(vrs)
                               for vrs in self._get_scope_versions(self._get_available_versions())])
            return versions and '{0}{1}'.format(self._op or '', versions[-1]) or None

    def _get_available_versions(self):
        '''
        Get available versions of the package.
        :return:
        '''
        solvables = self.zypper.nolock.xml.call('se', '-xv', self.name).getElementsByTagName('solvable')
        if not solvables:
            raise CommandExecutionError('No packages found matching \'{0}\''.format(self.name))

        return sorted(set([slv.getAttribute(self._attr_solvable_version)
                           for slv in solvables if slv.getAttribute(self._attr_solvable_version)]))

    def _get_scope_versions(self, pkg_versions):
        '''
        Get available difference between next possible matches.

        :return:
        '''
        get_in_versions = []
        for p_version in pkg_versions:
            if fnmatch.fnmatch(p_version, self.version):
                get_in_versions.append(p_version)
        return get_in_versions

    def _set_version(self, version):
        '''
        Stash operator from the version, if any.

        :return:
        '''
        if not version:
            return

        exact_version = re.sub(r'[<>=+]*', '', version)
        self._op = version.replace(exact_version, '') or None
        if self._op and self._op not in self.Z_OP:
            raise CommandExecutionError('Zypper do not supports operator "{0}".'.format(self._op))
        self.version = exact_version


def _systemd_scope():
    return salt.utils.systemd.has_scope(__context__) \
        and __salt__['config.get']('systemd.scope', True)


def _clean_cache():
    '''
    Clean cached results
    '''
    for cache_name in ['pkg.list_pkgs', 'pkg.list_provides']:
        __context__.pop(cache_name, None)


def list_upgrades(refresh=True, **kwargs):
    '''
    List all available package upgrades on this system

    refresh
        force a refresh if set to True (default).
        If set to False it depends on zypper if a refresh is
        executed.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if refresh:
        refresh_db()

    ret = dict()
    cmd = ['list-updates']
    if 'fromrepo' in kwargs:
        repo_name = kwargs['fromrepo']
        if not isinstance(repo_name, six.string_types):
            repo_name = six.text_type(repo_name)
        cmd.extend(['--repo', repo_name])
    for update_node in __zypper__.nolock.xml.call(*cmd).getElementsByTagName('update'):
        if update_node.getAttribute('kind') == 'package':
            ret[update_node.getAttribute('name')] = update_node.getAttribute('edition')

    return ret

# Provide a list_updates function for those used to using zypper list-updates
list_updates = salt.utils.functools.alias_function(list_upgrades, 'list_updates')


def info_installed(*names, **kwargs):
    '''
    Return the information of the named package(s), installed on the system.

    :param names:
        Names of the packages to get information about.

    :param attr:
        Comma-separated package attributes. If no 'attr' is specified, all available attributes returned.

        Valid attributes are:
            version, vendor, release, build_date, build_date_time_t, install_date, install_date_time_t,
            build_host, group, source_rpm, arch, epoch, size, license, signature, packager, url,
            summary, description.

    :param errors:
        Handle RPM field errors. If 'ignore' is chosen, then various mistakes are simply ignored and omitted
        from the texts or strings. If 'report' is chonen, then a field with a mistake is not returned, instead
        a 'N/A (broken)' (not available, broken) text is placed.

        Valid attributes are:
            ignore, report

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> attr=version,vendor
        salt '*' pkg.info_installed <package1> <package2> <package3> ... attr=version,vendor
        salt '*' pkg.info_installed <package1> <package2> <package3> ... attr=version,vendor errors=ignore
        salt '*' pkg.info_installed <package1> <package2> <package3> ... attr=version,vendor errors=report
    '''
    ret = dict()
    for pkg_name, pkg_nfo in __salt__['lowpkg.info'](*names, **kwargs).items():
        t_nfo = dict()
        # Translate dpkg-specific keys to a common structure
        for key, value in six.iteritems(pkg_nfo):
            if isinstance(value, six.string_types):
                # Check, if string is encoded in a proper UTF-8
                if six.PY3:
                    value_ = value.encode('UTF-8', 'ignore').decode('UTF-8', 'ignore')
                else:
                    value_ = value.decode('UTF-8', 'ignore').encode('UTF-8', 'ignore')
                if value != value_:
                    value = kwargs.get('errors', 'ignore') == 'ignore' and value_ or 'N/A (invalid UTF-8)'
                    log.error('Package %s has bad UTF-8 code in %s: %s', pkg_name, key, value)
            if key == 'source_rpm':
                t_nfo['source'] = value
            else:
                t_nfo[key] = value
        ret[pkg_name] = t_nfo

    return ret


def info_available(*names, **kwargs):
    '''
    Return the information of the named package available for the system.

    refresh
        force a refresh if set to True (default).
        If set to False it depends on zypper if a refresh is
        executed or not.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_available <package1>
        salt '*' pkg.info_available <package1> <package2> <package3> ...
    '''
    ret = {}

    if not names:
        return ret
    else:
        names = sorted(list(set(names)))

    # Refresh db before extracting the latest package
    if kwargs.get('refresh', True):
        refresh_db()

    pkg_info = []
    batch = names[:]
    batch_size = 200

    # Run in batches
    while batch:
        pkg_info.extend(re.split(r"Information for package*",
                                 __zypper__.nolock.call('info', '-t', 'package', *batch[:batch_size])))
        batch = batch[batch_size:]

    for pkg_data in pkg_info:
        nfo = {}
        for line in [data for data in pkg_data.split('\n') if ':' in data]:
            if line.startswith('-----'):
                continue
            kw = [data.strip() for data in line.split(':', 1)]
            if len(kw) == 2 and kw[1]:
                nfo[kw[0].lower()] = kw[1]
        if nfo.get('name'):
            name = nfo.pop('name')
            ret[name] = nfo
        if nfo.get('status'):
            nfo['status'] = nfo.get('status')
        if nfo.get('installed'):
            nfo['installed'] = nfo.get('installed').lower() == 'yes' and True or False

    return ret


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    dict will be returned for that package.

    refresh
        force a refresh if set to True (default).
        If set to False it depends on zypper if a refresh is
        executed or not.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    ret = dict()

    if not names:
        return ret

    names = sorted(list(set(names)))
    package_info = info_available(*names, **kwargs)
    for name in names:
        pkg_info = package_info.get(name, {})
        status = pkg_info.get('status', '').lower()
        if status.find('not installed') > -1 or status.find('out-of-date') > -1:
            ret[name] = pkg_info.get('version')

    # Return a string if only one package name passed
    if len(names) == 1 and len(ret):
        return ret[names[0]]

    return ret


# available_version is being deprecated
available_version = salt.utils.functools.alias_function(latest_version, 'available_version')


def upgrade_available(name, **kwargs):
    '''
    Check whether or not an upgrade is available for a given package

    refresh
        force a refresh if set to True (default).
        If set to False it depends on zypper if a refresh is
        executed or not.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    # The "not not" tactic is intended here as it forces the return to be False.
    return not not latest_version(name, **kwargs)  # pylint: disable=C0113


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty dict if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs) or {}


def version_cmp(ver1, ver2, ignore_epoch=False):
    '''
    .. versionadded:: 2015.5.4

    Do a cmp-style comparison on two packages. Return -1 if ver1 < ver2, 0 if
    ver1 == ver2, and 1 if ver1 > ver2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2015.8.10,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2-001' '0.2.0.1-002'
    '''
    return __salt__['lowpkg.version_cmp'](ver1, ver2, ignore_epoch=ignore_epoch)


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict. By default, the dict
    contains versions as a comma separated string::

        {'<package_name>': '<version>[,<version>...]'}

    versions_as_list:
        If set to true, the versions are provided as a list

        {'<package_name>': ['<version>', '<version>']}

    attr:
        If a list of package attributes is specified, returned value will
        contain them in addition to version, eg.::

        {'<package_name>': [{'version' : 'version', 'arch' : 'arch'}]}

        Valid attributes are: ``epoch``, ``version``, ``release``, ``arch``,
        ``install_date``, ``install_date_time_t``.

        If ``all`` is specified, all valid attributes will be returned.

            .. versionadded:: 2018.3.0

    removed:
        not supported

    purge_desired:
        not supported

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs attr=version,arch
        salt '*' pkg.list_pkgs attr='["version", "arch"]'
    '''
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any([salt.utils.data.is_true(kwargs.get(x))
            for x in ('removed', 'purge_desired')]):
        return {}

    attr = kwargs.get('attr')
    if attr is not None:
        attr = salt.utils.args.split_input(attr)

    contextkey = 'pkg.list_pkgs'

    if contextkey not in __context__:

        cmd = ['rpm', '-qa', '--queryformat', (
            "%{NAME}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}_|-"
            "%|EPOCH?{%{EPOCH}}:{}|_|-%{INSTALLTIME}\\n")]
        ret = {}
        for line in __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False).splitlines():
            name, pkgver, rel, arch, epoch, install_time = line.split('_|-')
            install_date = datetime.datetime.utcfromtimestamp(int(install_time)).isoformat() + "Z"
            install_date_time_t = int(install_time)

            all_attr = {'epoch': epoch, 'version': pkgver, 'release': rel, 'arch': arch,
                        'install_date': install_date, 'install_date_time_t': install_date_time_t}
            __salt__['pkg_resource.add_pkg'](ret, name, all_attr)

        for pkgname in ret:
            ret[pkgname] = sorted(ret[pkgname], key=lambda d: d['version'])

        __context__[contextkey] = ret

    return __salt__['pkg_resource.format_pkg_list'](
        __context__[contextkey],
        versions_as_list,
        attr)


def _get_configured_repos():
    '''
    Get all the info about repositories from the configurations.
    '''

    repos_cfg = configparser.ConfigParser()
    repos_cfg.read([REPOS + '/' + fname for fname in os.listdir(REPOS)])

    return repos_cfg


def _get_repo_info(alias, repos_cfg=None):
    '''
    Get one repo meta-data.
    '''
    try:
        meta = dict((repos_cfg or _get_configured_repos()).items(alias))
        meta['alias'] = alias
        for key, val in six.iteritems(meta):
            if val in ['0', '1']:
                meta[key] = int(meta[key]) == 1
            elif val == 'NONE':
                meta[key] = None
        return meta
    except (ValueError, configparser.NoSectionError):
        return {}


def get_repo(repo, **kwargs):  # pylint: disable=unused-argument
    '''
    Display a repo.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_repo alias
    '''
    return _get_repo_info(repo)


def list_repos():
    '''
    Lists all repos.

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
    '''
    repos_cfg = _get_configured_repos()
    all_repos = {}
    for alias in repos_cfg.sections():
        all_repos[alias] = _get_repo_info(alias, repos_cfg=repos_cfg)

    return all_repos


def del_repo(repo):
    '''
    Delete a repo.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo alias
    '''
    repos_cfg = _get_configured_repos()
    for alias in repos_cfg.sections():
        if alias == repo:
            doc = __zypper__.xml.call('rr', '--loose-auth', '--loose-query', alias)
            msg = doc.getElementsByTagName('message')
            if doc.getElementsByTagName('progress') and msg:
                return {
                    repo: True,
                    'message': msg[0].childNodes[0].nodeValue,
                }

    raise CommandExecutionError('Repository \'{0}\' not found.'.format(repo))


def mod_repo(repo, **kwargs):
    '''
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified:

    repo or alias
        alias by which the zypper refers to the repo

    url, mirrorlist or baseurl
        the URL for zypper to reference

    enabled
        Enable or disable (True or False) repository,
        but do not remove if disabled.

    refresh
        Enable or disable (True or False) auto-refresh of the repository.

    cache
        Enable or disable (True or False) RPM files caching.

    gpgcheck
        Enable or disable (True or False) GPG check for this repository.

    gpgautoimport
        Automatically trust and import new repository.

    Key/Value pairs may also be removed from a repo's configuration by setting
    a key to a blank value. Bear in mind that a name cannot be deleted, and a
    url can only be deleted if a mirrorlist is specified (or vice versa).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo alias alias=new_alias
        salt '*' pkg.mod_repo alias url= mirrorlist=http://host.com/
    '''

    repos_cfg = _get_configured_repos()
    added = False

    # An attempt to add new one?
    if repo not in repos_cfg.sections():
        url = kwargs.get('url', kwargs.get('mirrorlist', kwargs.get('baseurl')))
        if not url:
            raise CommandExecutionError(
                'Repository \'{0}\' not found, and neither \'baseurl\' nor '
                '\'mirrorlist\' was specified'.format(repo)
            )

        if not _urlparse(url).scheme:
            raise CommandExecutionError(
                'Repository \'{0}\' not found and URL for baseurl/mirrorlist '
                'is malformed'.format(repo)
            )

        # Is there already such repo under different alias?
        for alias in repos_cfg.sections():
            repo_meta = _get_repo_info(alias, repos_cfg=repos_cfg)

            # Complete user URL, in case it is not
            new_url = _urlparse(url)
            if not new_url.path:
                new_url = _urlparse.ParseResult(scheme=new_url.scheme,  # pylint: disable=E1123
                                                netloc=new_url.netloc,
                                                path='/',
                                                params=new_url.params,
                                                query=new_url.query,
                                                fragment=new_url.fragment)
            base_url = _urlparse(repo_meta['baseurl'])

            if new_url == base_url:
                raise CommandExecutionError(
                    'Repository \'{0}\' already exists as \'{1}\'.'.format(
                        repo,
                        alias
                    )
                )

        # Add new repo
        __zypper__.xml.call('ar', url, repo)

        # Verify the repository has been added
        repos_cfg = _get_configured_repos()
        if repo not in repos_cfg.sections():
            raise CommandExecutionError(
                'Failed add new repository \'{0}\' for unspecified reason. '
                'Please check zypper logs.'.format(repo))
        added = True

    repo_info = _get_repo_info(repo)
    if (
        not added and 'baseurl' in kwargs and
        not (kwargs['baseurl'] == repo_info['baseurl'])
    ):
        # Note: zypper does not support changing the baseurl
        # we need to remove the repository and add it again with the new baseurl
        repo_info.update(kwargs)
        repo_info.setdefault('cache', False)
        del_repo(repo)
        return mod_repo(repo, **repo_info)

    # Modify added or existing repo according to the options
    cmd_opt = []
    global_cmd_opt = []
    call_refresh = False

    if 'enabled' in kwargs:
        cmd_opt.append(kwargs['enabled'] and '--enable' or '--disable')

    if 'refresh' in kwargs:
        cmd_opt.append(kwargs['refresh'] and '--refresh' or '--no-refresh')

    if 'cache' in kwargs:
        cmd_opt.append(
            kwargs['cache'] and '--keep-packages' or '--no-keep-packages'
        )

    if 'gpgcheck' in kwargs:
        cmd_opt.append(kwargs['gpgcheck'] and '--gpgcheck' or '--no-gpgcheck')

    if 'priority' in kwargs:
        cmd_opt.append("--priority={0}".format(kwargs.get('priority', DEFAULT_PRIORITY)))

    if 'humanname' in kwargs:
        cmd_opt.append("--name='{0}'".format(kwargs.get('humanname')))

    if kwargs.get('gpgautoimport') is True:
        global_cmd_opt.append('--gpg-auto-import-keys')
        call_refresh = True

    if cmd_opt:
        cmd_opt = global_cmd_opt + ['mr'] + cmd_opt + [repo]
        __zypper__.refreshable.xml.call(*cmd_opt)

    comment = None
    if call_refresh:
        # when used with "zypper ar --refresh" or "zypper mr --refresh"
        # --gpg-auto-import-keys is not doing anything
        # so we need to specifically refresh here with --gpg-auto-import-keys
        refresh_opts = global_cmd_opt + ['refresh'] + [repo]
        __zypper__.xml.call(*refresh_opts)
    elif not added and not cmd_opt:
        comment = 'Specified arguments did not result in modification of repo'

    repo = get_repo(repo)
    if comment:
        repo['comment'] = comment

    return repo


def refresh_db():
    '''
    Force a repository refresh by calling ``zypper refresh --force``, return a dict::

        {'<database name>': Bool}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    ret = {}
    out = __zypper__.refreshable.call('refresh', '--force')

    for line in out.splitlines():
        if not line:
            continue
        if line.strip().startswith('Repository') and '\'' in line:
            try:
                key = line.split('\'')[1].strip()
                if 'is up to date' in line:
                    ret[key] = False
            except IndexError:
                continue
        elif line.strip().startswith('Building') and '\'' in line:
            key = line.split('\'')[1].strip()
            if 'done' in line:
                ret[key] = True
    return ret


def install(name=None,
            refresh=False,
            fromrepo=None,
            pkgs=None,
            sources=None,
            downloadonly=None,
            skip_verify=False,
            version=None,
            ignore_repo_failure=False,
            **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any zypper commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Install the passed package(s), add refresh=True to force a 'zypper refresh'
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either ``pkgs`` or ``sources`` is passed. Additionally,
        please note that this option can only be used to install packages from
        a software repository. To install a package file manually, use the
        ``sources`` option.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on zypper if a refresh is
        executed.

    fromrepo
        Specify a package repository to install from.

    downloadonly
        Only download the packages, do not install.

    skip_verify
        Skip the GPG verification check (e.g., ``--no-gpg-checks``)

    version
        Can be either a version number, or the combination of a comparison
        operator (<, >, <=, >=, =) and a version number (ex. '>1.2.3-4').
        This parameter is ignored if ``pkgs`` or ``sources`` is passed.

    resolve_capabilities
        If this option is set to True zypper will take capabilites into
        account. In this case names which are just provided by a package
        will get installed. Default is False.

    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version. As with the ``version`` parameter above, comparison operators
        can be used to target a specific version of a package.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4"}]'
            salt '*' pkg.install pkgs='["foo", {"bar": "<1.2.3-4"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"},{"bar": "salt://bar.rpm"}]'

    ignore_repo_failure
        Zypper returns error code 106 if one of the repositories are not available for various reasons.
        In case to set strict check, this parameter needs to be set to True. Default: False.

    diff_attr:
        If a list of package attributes is specified, returned value will
        contain them, eg.::

            {'<package>': {
                'old': {
                    'version': '<old-version>',
                    'arch': '<old-arch>'},

                'new': {
                    'version': '<new-version>',
                    'arch': '<new-arch>'}}}

        Valid attributes are: ``epoch``, ``version``, ``release``, ``arch``,
        ``install_date``, ``install_date_time_t``.

        If ``all`` is specified, all valid attributes will be returned.

        .. versionadded:: 2018.3.0


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    If an attribute list is specified in ``diff_attr``, the dict will also contain
    any specified attribute, eg.::

        {'<package>': {
            'old': {
                'version': '<old-version>',
                'arch': '<old-arch>'},

            'new': {
                'version': '<new-version>',
                'arch': '<new-arch>'}}}
    '''
    if refresh:
        refresh_db()

    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name, pkgs, sources, **kwargs)
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    version_num = Wildcard(__zypper__)(name, version)
    if pkg_type == 'repository':
        targets = []
        for param, version_num in six.iteritems(pkg_params):
            if version_num is None:
                log.debug('targeting package: %s', param)
                targets.append(param)
            else:
                prefix, verstr = salt.utils.pkg.split_comparison(version_num)
                if not prefix:
                    prefix = '='
                target = '{0}{1}{2}'.format(param, prefix, verstr)
                log.debug('targeting package: %s', target)
                targets.append(target)
    elif pkg_type == 'advisory':
        targets = []
        cur_patches = list_patches()
        for advisory_id in pkg_params:
            if advisory_id not in cur_patches:
                raise CommandExecutionError('Advisory id "{0}" not found'.format(advisory_id))
            else:
                targets.append(advisory_id)
    else:
        targets = pkg_params

    diff_attr = kwargs.get("diff_attr")
    old = list_pkgs(attr=diff_attr) if not downloadonly else list_downloaded()
    downgrades = []
    if fromrepo:
        fromrepoopt = ['--force', '--force-resolution', '--from', fromrepo]
        log.info('Targeting repo \'%s\'', fromrepo)
    else:
        fromrepoopt = ''
    cmd_install = ['install', '--auto-agree-with-licenses']

    cmd_install.append(kwargs.get('resolve_capabilities') and '--capability' or '--name')

    if not refresh:
        cmd_install.insert(0, '--no-refresh')
    if skip_verify:
        cmd_install.insert(0, '--no-gpg-checks')
    if downloadonly:
        cmd_install.append('--download-only')
    if fromrepo:
        cmd_install.extend(fromrepoopt)

    errors = []
    if pkg_type == 'advisory':
        targets = ["patch:{0}".format(t) for t in targets]

    # Split the targets into batches of 500 packages each, so that
    # the maximal length of the command line is not broken
    systemd_scope = _systemd_scope()
    while targets:
        cmd = cmd_install + targets[:500]
        targets = targets[500:]
        for line in __zypper__(no_repo_failure=ignore_repo_failure, systemd_scope=systemd_scope).call(*cmd).splitlines():
            match = re.match(r"^The selected package '([^']+)'.+has lower version", line)
            if match:
                downgrades.append(match.group(1))

    while downgrades:
        cmd = cmd_install + ['--force'] + downgrades[:500]
        downgrades = downgrades[500:]
        __zypper__(no_repo_failure=ignore_repo_failure).call(*cmd)

    _clean_cache()
    new = list_pkgs(attr=diff_attr) if not downloadonly else list_downloaded()

    # Handle packages which report multiple new versions
    # (affects only kernel packages at this point)
    for pkg_name in new:
        pkg_data = new[pkg_name]
        if isinstance(pkg_data, six.string_types):
            new[pkg_name] = pkg_data.split(',')[-1]

    ret = salt.utils.data.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered {0} package(s)'.format(
                'downloading' if downloadonly else 'installing'
            ),
            info={'errors': errors, 'changes': ret}
        )

    return ret


def upgrade(refresh=True,
            dryrun=False,
            dist_upgrade=False,
            fromrepo=None,
            novendorchange=False,
            skip_verify=False,
            **kwargs):  # pylint: disable=unused-argument
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any zypper commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Run a full system upgrade, a zypper upgrade

    refresh
        force a refresh if set to True (default).
        If set to False it depends on zypper if a refresh is
        executed.

    dryrun
        If set to True, it creates a debug solver log file and then perform
        a dry-run upgrade (no changes are made). Default: False

    dist_upgrade
        Perform a system dist-upgrade. Default: False

    fromrepo
        Specify a list of package repositories to upgrade from. Default: None

    novendorchange
        If set to True, no allow vendor changes. Default: False

    skip_verify
        Skip the GPG verification check (e.g., ``--no-gpg-checks``)

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
        salt '*' pkg.upgrade dist-upgrade=True fromrepo='["MyRepoName"]' novendorchange=True
        salt '*' pkg.upgrade dist-upgrade=True dryrun=True
    '''
    cmd_update = (['dist-upgrade'] if dist_upgrade else ['update']) + ['--auto-agree-with-licenses']

    if skip_verify:
        # The '--no-gpg-checks' needs to be placed before the Zypper command.
        cmd_update.insert(0, '--no-gpg-checks')

    if refresh:
        refresh_db()

    if dryrun:
        cmd_update.append('--dry-run')

    if dist_upgrade:
        if fromrepo:
            for repo in fromrepo:
                cmd_update.extend(['--from', repo])
            log.info('Targeting repos: %s', fromrepo)

        if novendorchange:
            # TODO: Grains validation should be moved to Zypper class
            if __grains__['osrelease_info'][0] > 11:
                cmd_update.append('--no-allow-vendor-change')
                log.info('Disabling vendor changes')
            else:
                log.warning('Disabling vendor changes is not supported on this Zypper version')

        if dryrun:
            # Creates a solver test case for debugging.
            log.info('Executing debugsolver and performing a dry-run dist-upgrade')
            __zypper__(systemd_scope=_systemd_scope()).noraise.call(*cmd_update + ['--debug-solver'])

    old = list_pkgs()

    __zypper__(systemd_scope=_systemd_scope()).noraise.call(*cmd_update)
    _clean_cache()
    new = list_pkgs()

    # Handle packages which report multiple new versions
    # (affects only kernel packages at this point)
    for pkg in new:
        new[pkg] = new[pkg].split(',')[-1]
    ret = salt.utils.data.compare_dicts(old, new)

    if __zypper__.exit_code not in __zypper__.SUCCESS_EXIT_CODES:
        result = {
            'retcode': __zypper__.exit_code,
            'stdout': __zypper__.stdout,
            'stderr': __zypper__.stderr,
            'pid': __zypper__.pid,
        }
        raise CommandExecutionError(
            'Problem encountered upgrading packages',
            info={'changes': ret, 'result': result}
        )

    if dryrun:
        ret = (__zypper__.stdout + os.linesep + __zypper__.stderr).strip()

    return ret


def _uninstall(name=None, pkgs=None):
    '''
    Remove and purge do identical things but with different Zypper commands,
    this function performs the common logic.
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [target for target in pkg_params if target in old]
    if not targets:
        return {}

    systemd_scope = _systemd_scope()

    errors = []
    while targets:
        __zypper__(systemd_scope=systemd_scope).call('remove', *targets[:500])
        targets = targets[500:]

    _clean_cache()
    ret = salt.utils.data.compare_dicts(old, list_pkgs())

    if errors:
        raise CommandExecutionError(
            'Problem encountered removing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def remove(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any zypper commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages with ``zypper -n remove``

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
    return _uninstall(name=name, pkgs=pkgs)


def purge(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any zypper commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``zypper -n remove -u``

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
    return _uninstall(name=name, pkgs=pkgs)


def list_locks():
    '''
    List current package locks.

    Return a dict containing the locked package with attributes::

        {'<package>': {'case_sensitive': '<case_sensitive>',
                       'match_type': '<match_type>'
                       'type': '<type>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_locks
    '''
    locks = {}
    if os.path.exists(LOCKS):
        with salt.utils.files.fopen(LOCKS) as fhr:
            items = salt.utils.stringutils.to_unicode(fhr.read()).split('\n\n')
            for meta in [item.split('\n') for item in items]:
                lock = {}
                for element in [el for el in meta if el]:
                    if ':' in element:
                        lock.update(dict([tuple([i.strip() for i in element.split(':', 1)]), ]))
                if lock.get('solvable_name'):
                    locks[lock.pop('solvable_name')] = lock

    return locks


def clean_locks():
    '''
    Remove unused locks that do not currently (with regard to repositories
    used) lock any package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.clean_locks
    '''
    LCK = "removed"
    out = {LCK: 0}
    if not os.path.exists("/etc/zypp/locks"):
        return out

    for node in __zypper__.xml.call('cl').getElementsByTagName("message"):
        text = node.childNodes[0].nodeValue.lower()
        if text.startswith(LCK):
            out[LCK] = text.split(" ")[1]
            break

    return out


def remove_lock(packages, **kwargs):  # pylint: disable=unused-argument
    '''
    Remove specified package lock.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove_lock <package name>
        salt '*' pkg.remove_lock <package1>,<package2>,<package3>
        salt '*' pkg.remove_lock pkgs='["foo", "bar"]'
    '''

    locks = list_locks()
    try:
        packages = list(__salt__['pkg_resource.parse_targets'](packages)[0].keys())
    except MinionError as exc:
        raise CommandExecutionError(exc)

    removed = []
    missing = []
    for pkg in packages:
        if locks.get(pkg):
            removed.append(pkg)
        else:
            missing.append(pkg)

    if removed:
        __zypper__.call('rl', *removed)

    return {'removed': len(removed), 'not_found': missing}


def add_lock(packages, **kwargs):  # pylint: disable=unused-argument
    '''
    Add a package lock. Specify packages to lock by exact name.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.add_lock <package name>
        salt '*' pkg.add_lock <package1>,<package2>,<package3>
        salt '*' pkg.add_lock pkgs='["foo", "bar"]'
    '''
    locks = list_locks()
    added = []
    try:
        packages = list(__salt__['pkg_resource.parse_targets'](packages)[0].keys())
    except MinionError as exc:
        raise CommandExecutionError(exc)

    for pkg in packages:
        if not locks.get(pkg):
            added.append(pkg)

    if added:
        __zypper__.call('al', *added)

    return {'added': len(added), 'packages': added}


def verify(*names, **kwargs):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    Files with an attribute of config, doc, ghost, license or readme in the
    package header can be ignored using the ``ignore_types`` keyword argument

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.verify
        salt '*' pkg.verify httpd
        salt '*' pkg.verify 'httpd postfix'
        salt '*' pkg.verify 'httpd postfix' ignore_types=['config','doc']
    '''
    return __salt__['lowpkg.verify'](*names, **kwargs)


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of *every* file on the system's rpm database (not generally
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
    specifying any packages will return a list of *every* file on the system's
    rpm database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_dict'](*packages)


def modified(*packages, **flags):
    '''
    List the modified files that belong to a package. Not specifying any packages
    will return a list of _all_ modified files on the system's RPM database.

    .. versionadded:: 2015.5.0

    Filtering by flags (True or False):

    size
        Include only files where size changed.

    mode
        Include only files which file's mode has been changed.

    checksum
        Include only files which MD5 checksum has been changed.

    device
        Include only files which major and minor numbers has been changed.

    symlink
        Include only files which are symbolic link contents.

    owner
        Include only files where owner has been changed.

    group
        Include only files where group has been changed.

    time
        Include only files where modification time of the file has been changed.

    capabilities
        Include only files where capabilities differ or not. Note: supported only on newer RPM versions.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.modified
        salt '*' pkg.modified httpd
        salt '*' pkg.modified httpd postfix
        salt '*' pkg.modified httpd owner=True group=False
    '''

    return __salt__['lowpkg.modified'](*packages, **flags)


def owner(*paths):
    '''
    Return the name of the package that owns the file. Multiple file paths can
    be passed. If a single path is passed, a string will be returned,
    and if multiple paths are passed, a dictionary of file/package name
    pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /etc/httpd/conf/httpd.conf
    '''
    return __salt__['lowpkg.owner'](*paths)


def _get_patterns(installed_only=None):
    '''
    List all known patterns in repos.
    '''
    patterns = {}
    for element in __zypper__.nolock.xml.call('se', '-t', 'pattern').getElementsByTagName('solvable'):
        installed = element.getAttribute('status') == 'installed'
        if (installed_only and installed) or not installed_only:
            patterns[element.getAttribute('name')] = {
                'installed': installed,
                'summary': element.getAttribute('summary'),
            }

    return patterns


def list_patterns(refresh=False):
    '''
    List all known patterns from available repos.

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on zypper if a refresh is
        executed.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_patterns
    '''
    if refresh:
        refresh_db()

    return _get_patterns()


def list_installed_patterns():
    '''
    List installed patterns on the system.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_installed_patterns
    '''
    return _get_patterns(installed_only=True)


def search(criteria, refresh=False, **kwargs):
    '''
    List known packags, available to the system.

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on zypper if a refresh is
        executed.

    match (str)
        One of `exact`, `words`, `substrings`. Search for an `exact` match
        or for the whole `words` only. Default to `substrings` to patch
        partial words.

    provides (bool)
        Search for packages which provide the search strings.

    recommends (bool)
        Search for packages which recommend the search strings.

    requires (bool)
        Search for packages which require the search strings.

    suggests (bool)
        Search for packages which suggest the search strings.

    conflicts (bool)
        Search packages conflicting with search strings.

    obsoletes (bool)
        Search for packages which obsolete the search strings.

    file_list (bool)
        Search for a match in the file list of packages.

    search_descriptions (bool)
        Search also in package summaries and descriptions.

    case_sensitive (bool)
        Perform case-sensitive search.

    installed_only (bool)
        Show only installed packages.

    not_installed_only (bool)
        Show only packages which are not installed.

    details (bool)
        Show version and repository

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.search <criteria>
    '''
    ALLOWED_SEARCH_OPTIONS = {
            'provides': '--provides',
            'recommends': '--recommends',
            'requires': '--requires',
            'suggests': '--suggests',
            'conflicts': '--conflicts',
            'obsoletes': '--obsoletes',
            'file_list': '--file-list',
            'search_descriptions': '--search-descriptions',
            'case_sensitive': '--case-sensitive',
            'installed_only': '--installed-only',
            'not_installed_only': '-u',
            'details': '--details'
            }
    if refresh:
        refresh_db()

    cmd = ['search']
    if kwargs.get('match') == 'exact':
        cmd.append('--match-exact')
    elif kwargs.get('match') == 'words':
        cmd.append('--match-words')
    elif kwargs.get('match') == 'substrings':
        cmd.append('--match-substrings')

    for opt in kwargs:
        if opt in ALLOWED_SEARCH_OPTIONS:
            cmd.append(ALLOWED_SEARCH_OPTIONS.get(opt))

    cmd.append(criteria)
    solvables = __zypper__.nolock.noraise.xml.call(*cmd).getElementsByTagName('solvable')
    if not solvables:
        raise CommandExecutionError(
            'No packages found matching \'{0}\''.format(criteria)
        )

    out = {}
    for solvable in solvables:
        out[solvable.getAttribute('name')] = dict()
        for k, v in solvable.attributes.items():
            out[solvable.getAttribute('name')][k] = v

    return out


def _get_first_aggregate_text(node_list):
    '''
    Extract text from the first occurred DOM aggregate.
    '''
    if not node_list:
        return ''

    out = []
    for node in node_list[0].childNodes:
        if node.nodeType == dom.Document.TEXT_NODE:
            out.append(node.nodeValue)
    return '\n'.join(out)


def list_products(all=False, refresh=False):
    '''
    List all available or installed SUSE products.

    all
        List all products available or only installed. Default is False.

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on zypper if a refresh is
        executed.

    Includes handling for OEM products, which read the OEM productline file
    and overwrite the release value.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_products
        salt '*' pkg.list_products all=True
    '''
    if refresh:
        refresh_db()

    ret = list()
    OEM_PATH = "/var/lib/suseRegister/OEM"
    cmd = list()
    if not all:
        cmd.append('--disable-repos')
    cmd.append('products')
    if not all:
        cmd.append('-i')

    product_list = __zypper__.nolock.xml.call(*cmd).getElementsByTagName('product-list')
    if not product_list:
        return ret  # No products found

    for prd in product_list[0].getElementsByTagName('product'):
        p_nfo = dict()
        for k_p_nfo, v_p_nfo in prd.attributes.items():
            if k_p_nfo in ['isbase', 'installed']:
                p_nfo[k_p_nfo] = bool(v_p_nfo in ['true', '1'])
            elif v_p_nfo:
                p_nfo[k_p_nfo] = v_p_nfo

        eol = prd.getElementsByTagName('endoflife')
        if eol:
            p_nfo['eol'] = eol[0].getAttribute('text')
            p_nfo['eol_t'] = int(eol[0].getAttribute('time_t') or 0)
        p_nfo['description'] = " ".join(
            [line.strip() for line in _get_first_aggregate_text(
                prd.getElementsByTagName('description')
            ).split(os.linesep)]
        )
        if 'productline' in p_nfo and p_nfo['productline']:
            oem_file = os.path.join(OEM_PATH, p_nfo['productline'])
            if os.path.isfile(oem_file):
                with salt.utils.files.fopen(oem_file, 'r') as rfile:
                    oem_release = salt.utils.stringutils.to_unicode(rfile.readline()).strip()
                    if oem_release:
                        p_nfo['release'] = oem_release
        ret.append(p_nfo)

    return ret


def download(*packages, **kwargs):
    '''
    Download packages to the local disk.

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on zypper if a refresh is
        executed.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.download httpd
        salt '*' pkg.download httpd postfix
    '''
    if not packages:
        raise SaltInvocationError('No packages specified')

    refresh = kwargs.get('refresh', False)
    if refresh:
        refresh_db()

    pkg_ret = {}
    for dld_result in __zypper__.xml.call('download', *packages).getElementsByTagName("download-result"):
        repo = dld_result.getElementsByTagName("repository")[0]
        path = dld_result.getElementsByTagName("localfile")[0].getAttribute("path")
        pkg_info = {
            'repository-name': repo.getAttribute('name'),
            'repository-alias': repo.getAttribute('alias'),
            'path': path,
        }
        key = _get_first_aggregate_text(
            dld_result.getElementsByTagName('name')
        )
        if __salt__['lowpkg.checksum'](pkg_info['path']):
            pkg_ret[key] = pkg_info

    if pkg_ret:
        failed = [pkg for pkg in packages if pkg not in pkg_ret]
        if failed:
            pkg_ret['_error'] = ('The following package(s) failed to download: {0}'.format(', '.join(failed)))
        return pkg_ret

    raise CommandExecutionError(
        'Unable to download packages: {0}'.format(', '.join(packages))
    )


def list_downloaded():
    '''
    .. versionadded:: 2017.7.0

    List prefetched packages downloaded by Zypper in the local disk.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.list_downloaded
    '''
    CACHE_DIR = '/var/cache/zypp/packages/'

    ret = {}
    for root, dirnames, filenames in salt.utils.path.os_walk(CACHE_DIR):
        for filename in fnmatch.filter(filenames, '*.rpm'):
            package_path = os.path.join(root, filename)
            pkg_info = __salt__['lowpkg.bin_pkg_info'](package_path)
            pkg_timestamp = int(os.path.getctime(package_path))
            ret.setdefault(pkg_info['name'], {})[pkg_info['version']] = {
                'path': package_path,
                'size': os.path.getsize(package_path),
                'creation_date_time_t': pkg_timestamp,
                'creation_date_time': datetime.datetime.utcfromtimestamp(pkg_timestamp).isoformat(),
            }
    return ret


def diff(*paths):
    '''
    Return a formatted diff between current files and original in a package.
    NOTE: this function includes all files (configuration and not), but does
    not work on binary content.

    :param path: Full path to the installed file
    :return: Difference string or raises and exception if examined file is binary.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.diff /etc/apache2/httpd.conf /etc/sudoers
    '''
    ret = {}

    pkg_to_paths = {}
    for pth in paths:
        pth_pkg = __salt__['lowpkg.owner'](pth)
        if not pth_pkg:
            ret[pth] = os.path.exists(pth) and 'Not managed' or 'N/A'
        else:
            if pkg_to_paths.get(pth_pkg) is None:
                pkg_to_paths[pth_pkg] = []
            pkg_to_paths[pth_pkg].append(pth)

    if pkg_to_paths:
        local_pkgs = __salt__['pkg.download'](*pkg_to_paths.keys())
        for pkg, files in six.iteritems(pkg_to_paths):
            for path in files:
                ret[path] = __salt__['lowpkg.diff'](
                    local_pkgs[pkg]['path'],
                    path
                ) or 'Unchanged'

    return ret


def _get_patches(installed_only=False):
    '''
    List all known patches in repos.
    '''
    patches = {}
    for element in __zypper__.nolock.xml.call('se', '-t', 'patch').getElementsByTagName('solvable'):
        installed = element.getAttribute('status') == 'installed'
        if (installed_only and installed) or not installed_only:
            patches[element.getAttribute('name')] = {
                'installed': installed,
                'summary': element.getAttribute('summary'),
            }

    return patches


def list_patches(refresh=False):
    '''
    .. versionadded:: 2017.7.0

    List all known advisory patches from available repos.

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on zypper if a refresh is
        executed.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_patches
    '''
    if refresh:
        refresh_db()

    return _get_patches()


def list_installed_patches():
    '''
    .. versionadded:: 2017.7.0

    List installed advisory patches on the system.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_installed_patches
    '''
    return _get_patches(installed_only=True)


def list_provides(**kwargs):
    '''
    .. versionadded:: 2018.3.0

    List package provides of installed packages as a dict.
    {'<provided_name>': ['<package_name>', '<package_name>', ...]}

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_provides
    '''
    ret = __context__.get('pkg.list_provides')
    if not ret:
        cmd = ['rpm', '-qa', '--queryformat', '[%{PROVIDES}_|-%{NAME}\n]']
        ret = dict()
        for line in __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False).splitlines():
            provide, realname = line.split('_|-')

            if provide == realname:
                continue
            if provide not in ret:
                ret[provide] = list()
            ret[provide].append(realname)

        __context__['pkg.list_provides'] = ret

    return ret


def resolve_capabilities(pkgs, refresh, **kwargs):
    '''
    .. versionadded:: 2018.3.0

    Convert name provides in ``pkgs`` into real package names if
    ``resolve_capabilities`` parameter is set to True. In case of
    ``resolve_capabilities`` is set to False the package list
    is returned unchanged.

    refresh
        force a refresh if set to True.
        If set to False (default) it depends on zypper if a refresh is
        executed.

    resolve_capabilities
        If this option is set to True the input will be checked if
        a package with this name exists. If not, this function will
        search for a package which provides this name. If one is found
        the output is exchanged with the real package name.
        In case this option is set to False (Default) the input will
        be returned unchanged.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.resolve_capabilities resolve_capabilities=True w3m_ssl
    '''
    if refresh:
        refresh_db()

    ret = list()
    for pkg in pkgs:
        if isinstance(pkg, dict):
            name = next(iter(pkg))
            version = pkg[name]
        else:
            name = pkg
            version = None

        if kwargs.get('resolve_capabilities', False):
            try:
                search(name, match='exact')
            except CommandExecutionError:
                # no package this such a name found
                # search for a package which provides this name
                try:
                    result = search(name, provides=True, match='exact')
                    if len(result) == 1:
                        name = result.keys()[0]
                    elif len(result) > 1:
                        log.warn("Found ambiguous match for capability '%s'.", pkg)
                except CommandExecutionError as exc:
                    # when search throws an exception stay with original name and version
                    log.debug("Search failed with: %s", exc)

        if version:
            ret.append({name: version})
        else:
            ret.append(name)
    return ret

# -*- coding: utf-8 -*-
'''
Support for Portage

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

:optdepends:    - portage Python adapter

For now all package names *MUST* include the package category,
i.e. ``'vim'`` will not work, ``'app-editors/vim'`` will.
'''
from __future__ import absolute_import

# Import python libs
import copy
import logging
import re

# Import salt libs
import salt.utils
import salt.utils.systemd
from salt.exceptions import CommandExecutionError, MinionError
import salt.ext.six as six

# Import third party libs
HAS_PORTAGE = False
try:
    import portage
    HAS_PORTAGE = True
except ImportError:
    import os
    import sys
    if os.path.isdir('/usr/lib/portage/pym'):
        try:
            # In a virtualenv, the portage python path needs to be manually added
            sys.path.insert(0, '/usr/lib/portage/pym')
            import portage
            HAS_PORTAGE = True
        except ImportError:
            pass

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confirm this module is on a Gentoo based system
    '''
    if HAS_PORTAGE and __grains__['os'] == 'Gentoo':
        return __virtualname__
    return (False, 'The ebuild execution module cannot be loaded: either the system is not Gentoo or the portage python library is not available.')


def _vartree():
    import portage  # pylint: disable=3rd-party-module-not-gated
    portage = reload(portage)
    return portage.db[portage.root]['vartree']


def _porttree():
    import portage  # pylint: disable=3rd-party-module-not-gated
    portage = reload(portage)
    return portage.db[portage.root]['porttree']


def _p_to_cp(p):
    ret = _porttree().dbapi.xmatch("match-all", p)
    if ret:
        return portage.cpv_getkey(ret[0])
    return None


def _allnodes():
    if 'portage._allnodes' in __context__:
        return __context__['portage._allnodes']
    else:
        ret = _porttree().getallnodes()
        __context__['portage._allnodes'] = ret
        return ret


def _cpv_to_cp(cpv):
    ret = portage.cpv_getkey(cpv)
    if ret:
        return ret
    else:
        return cpv


def _cpv_to_version(cpv):
    return portage.versions.cpv_getversion(cpv)


def _process_emerge_err(stdout, stderr):
    '''
    Used to parse emerge output to provide meaningful output when emerge fails
    '''
    ret = {}
    rexp = re.compile(r'^[<>=][^ ]+/[^ ]+ [^\n]+', re.M)

    slot_conflicts = re.compile(r'^[^ \n]+/[^ ]+:[^ ]', re.M).findall(stderr)
    if slot_conflicts:
        ret['slot conflicts'] = slot_conflicts

    blocked = re.compile(r'(?m)^\[blocks .+\] '
                         r'([^ ]+/[^ ]+-[0-9]+[^ ]+)'
                         r'.*$').findall(stdout)

    unsatisfied = re.compile(
            r'Error: The above package list contains').findall(stderr)

    # If there were blocks and emerge could not resolve it.
    if blocked and unsatisfied:
        ret['blocked'] = blocked

    sections = re.split('\n\n', stderr)
    for section in sections:
        if 'The following keyword changes' in section:
            ret['keywords'] = rexp.findall(section)
        elif 'The following license changes' in section:
            ret['license'] = rexp.findall(section)
        elif 'The following USE changes' in section:
            ret['use'] = rexp.findall(section)
        elif 'The following mask changes' in section:
            ret['mask'] = rexp.findall(section)
    return ret


def check_db(*names, **kwargs):
    '''
    .. versionadded:: 0.17.0

    Returns a dict containing the following information for each specified
    package:

    1. A key ``found``, which will be a boolean value denoting if a match was
       found in the package database.
    2. If ``found`` is ``False``, then a second key called ``suggestions`` will
       be present, which will contain a list of possible matches. This list
       will be empty if the package name was specified in ``category/pkgname``
       format, since the suggestions are only intended to disambiguate
       ambiguous package names (ones submitted without a category).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.check_db <package1> <package2> <package3>
    '''
    ### NOTE: kwargs is not used here but needs to be present due to it being
    ### required in the check_db function in other package providers.
    ret = {}
    for name in names:
        if name in ret:
            log.warning('pkg.check_db: Duplicate package name \'{0}\' '
                        'submitted'.format(name))
            continue
        if '/' not in name:
            ret.setdefault(name, {})['found'] = False
            ret[name]['suggestions'] = porttree_matches(name)
        else:
            ret.setdefault(name, {})['found'] = name in _allnodes()
            if ret[name]['found'] is False:
                ret[name]['suggestions'] = []
    return ret


def ex_mod_init(low):
    '''
    If the config option ``ebuild.enforce_nice_config`` is set to True, this
    module will enforce a nice tree structure for /etc/portage/package.*
    configuration files.

    .. versionadded:: 0.17.0
       Initial automatic enforcement added when pkg is used on a Gentoo system.

    .. versionchanged:: 2014.1.0-Hydrogen
       Configure option added to make this behaviour optional, defaulting to
       off.

    .. seealso::
       ``ebuild.ex_mod_init`` is called automatically when a state invokes a
       pkg state on a Gentoo system.
       :py:func:`salt.states.pkg.mod_init`

       ``ebuild.ex_mod_init`` uses ``portage_config.enforce_nice_config`` to do
       the lifting.
       :py:func:`salt.modules.portage_config.enforce_nice_config`

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.ex_mod_init
    '''
    if __salt__['config.get']('ebuild.enforce_nice_config', False):
        __salt__['portage_config.enforce_nice_config']()
    return True


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', True))

    if len(names) == 0:
        return ''

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
        installed = _cpv_to_version(_vartree().dep_bestmatch(name))
        avail = _cpv_to_version(_porttree().dep_bestmatch(name))
        if avail and (not installed or salt.utils.compare_versions(ver1=installed, oper='<', ver2=avail, cmp_func=version_cmp)):
            ret[name] = avail

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def _get_upgradable(backtrack=3):
    '''
    Utility function to get upgradable packages

    Sample return data:
    { 'pkgname': '1.2.3-45', ... }
    '''

    cmd = ['emerge',
           '--ask', 'n',
           '--backtrack', '{0}'.format(backtrack),
           '--pretend',
           '--update',
           '--newuse',
           '--deep',
           '@world']

    call = __salt__['cmd.run_all'](cmd,
                                   output_loglevel='trace',
                                   python_shell=False)

    if call['retcode'] != 0:
        msg = 'Failed to get upgrades'
        for key in ('stderr', 'stdout'):
            if call[key]:
                msg += ': ' + call[key]
                break
        raise CommandExecutionError(msg)
    else:
        out = call['stdout']

    rexp = re.compile(r'(?m)^\[.+\] '
                      r'([^ ]+/[^ ]+)'    # Package string
                      '-'
                      r'([0-9]+[^ ]+)'          # Version
                      r'.*$')
    keys = ['name', 'version']
    _get = lambda l, k: l[keys.index(k)]

    upgrades = rexp.findall(out)

    ret = {}
    for line in upgrades:
        name = _get(line, 'name')
        version_num = _get(line, 'version')
        ret[name] = version_num

    return ret


def list_upgrades(refresh=True, backtrack=3, **kwargs):  # pylint: disable=W0613
    '''
    List all available package upgrades.

    refresh
        Whether or not to sync the portage tree before checking for upgrades.

    backtrack
        Specifies an integer number of times to backtrack if dependency
        calculation fails due to a conflict or an unsatisfied dependency
        (default: ´3´).

        .. versionadded: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    return _get_upgradable(backtrack)


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


def porttree_matches(name):
    '''
    Returns a list containing the matches for a given package name from the
    portage tree. Note that the specific version of the package will not be
    provided for packages that have several versions in the portage tree, but
    rather the name of the package (i.e. "dev-python/paramiko").
    '''
    matches = []
    for category in _porttree().dbapi.categories:
        if _porttree().dbapi.cp_list(category + "/" + name):
            matches.append(category + "/" + name)
    return matches


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
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

    ret = {}
    pkgs = _vartree().dbapi.cpv_all()
    for cpv in pkgs:
        __salt__['pkg_resource.add_pkg'](ret,
                                         _cpv_to_cp(cpv),
                                         _cpv_to_version(cpv))
    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def refresh_db():
    '''
    Updates the portage tree (emerge --sync). Uses eix-sync if available.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    if 'eix.sync' in __salt__:
        return __salt__['eix.sync']()

    if 'makeconf.features_contains'in __salt__ and __salt__['makeconf.features_contains']('webrsync-gpg'):
        # GPG sign verify is supported only for "webrsync"
        cmd = 'emerge-webrsync -q'
        # We prefer 'delta-webrsync' to 'webrsync'
        if salt.utils.which('emerge-delta-webrsync'):
            cmd = 'emerge-delta-webrsync -q'
        return __salt__['cmd.retcode'](cmd, python_shell=False) == 0
    else:
        if __salt__['cmd.retcode']('emerge --ask n --quiet --sync',
                                   python_shell=False) == 0:
            return True
        # We fall back to "webrsync" if "rsync" fails for some reason
        cmd = 'emerge-webrsync -q'
        # We prefer 'delta-webrsync' to 'webrsync'
        if salt.utils.which('emerge-delta-webrsync'):
            cmd = 'emerge-delta-webrsync -q'
        return __salt__['cmd.retcode'](cmd, python_shell=False) == 0


def _flags_changed(inst_flags, conf_flags):
    '''
    @type inst_flags: list
    @param inst_flags: list of use flags which were used
        when package was installed
    @type conf_flags: list
    @param conf_flags: list of use flags form portage/package.use
    @rtype: bool
    @return: True, if lists have changes
    '''
    conf_flags = conf_flags[:]
    for i in inst_flags:
        try:
            conf_flags.remove(i)
        except ValueError:
            return True
    return True if conf_flags else False


def install(name=None,
            refresh=False,
            pkgs=None,
            sources=None,
            slot=None,
            fromrepo=None,
            uses=None,
            binhost=None,
            **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any emerge commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Install the passed package(s), add refresh=True to sync the portage tree
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to emerge a package from the
        portage tree. To install a tbz2 package manually, use the "sources"
        option described below.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to sync the portage tree before installing.

    version
        Install a specific version of the package, e.g. 1.0.9-r1. Ignored
        if "pkgs" or "sources" is passed.

    slot
        Similar to version, but specifies a valid slot to be installed. It
        will install the latest available version in the specified slot.
        Ignored if "pkgs" or "sources" or "version" is passed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sys-devel/gcc slot='4.4'

    fromrepo
        Similar to slot, but specifies the repository from the package will be
        installed. It will install the latest available version in the
        specified repository.
        Ignored if "pkgs" or "sources" or "version" is passed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install salt fromrepo='gentoo'

    uses
        Similar to slot, but specifies a list of use flag.
        Ignored if "pkgs" or "sources" or "version" is passed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sys-devel/gcc uses='["nptl","-nossp"]'


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from the portage tree. Must be passed as
        a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo","bar","~category/package:slot::repository[use]"]'

    sources
        A list of tbz2 packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.tbz2"},{"bar": "salt://bar.tbz2"}]'
    binhost
        has two options try and force.
        try - tells emerge to try and install the package from a configured binhost.
        force - forces emerge to install the package from a binhost otherwise it fails out.

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    log.debug('Called modules.pkg.install: {0}'.format(
        {
            'name': name,
            'refresh': refresh,
            'pkgs': pkgs,
            'sources': sources,
            'kwargs': kwargs,
            'binhost': binhost,
        }
    ))
    if salt.utils.is_true(refresh):
        refresh_db()

    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    # Handle version kwarg for a single package target
    if pkgs is None and sources is None:
        version_num = kwargs.get('version')
        if version_num:
            pkg_params = {name: version_num}
        else:
            version_num = ''
            if slot is not None:
                version_num += ':{0}'.format(slot)
            if fromrepo is not None:
                version_num += '::{0}'.format(fromrepo)
            if uses is not None:
                version_num += '[{0}]'.format(','.join(uses))
            pkg_params = {name: version_num}

    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        emerge_opts = ['tbz2file']
    else:
        emerge_opts = []

    if binhost == 'try':
        bin_opts = ['-g']
    elif binhost == 'force':
        bin_opts = ['-G']
    else:
        bin_opts = []

    changes = {}

    if pkg_type == 'repository':
        targets = list()
        for param, version_num in six.iteritems(pkg_params):
            original_param = param
            param = _p_to_cp(param)
            if param is None:
                raise portage.dep.InvalidAtom(original_param)

            if version_num is None:
                targets.append(param)
            else:
                keyword = None

                match = re.match('^(~)?([<>])?(=)?([^<>=]*)$', version_num)
                if match:
                    keyword, gt_lt, eq, verstr = match.groups()
                    prefix = gt_lt or ''
                    prefix += eq or ''
                    # If no prefix characters were supplied and verstr contains a version, use '='
                    if len(verstr) > 0 and verstr[0] != ':' and verstr[0] != '[':
                        prefix = prefix or '='
                        target = '{0}{1}-{2}'.format(prefix, param, verstr)
                    else:
                        target = '{0}{1}'.format(param, verstr)
                else:
                    target = '{0}'.format(param)

                if '[' in target:
                    old = __salt__['portage_config.get_flags_from_package_conf']('use', target)
                    __salt__['portage_config.append_use_flags'](target)
                    new = __salt__['portage_config.get_flags_from_package_conf']('use', target)
                    if old != new:
                        changes[param + '-USE'] = {'old': old, 'new': new}
                    target = target[:target.rfind('[')]

                if keyword is not None:
                    __salt__['portage_config.append_to_package_conf']('accept_keywords',
                                                                        target,
                                                                        ['~ARCH'])
                    changes[param + '-ACCEPT_KEYWORD'] = {'old': '', 'new': '~ARCH'}

                if not changes:
                    inst_v = version(param)

                    # Prevent latest_version from calling refresh_db. Either we
                    # just called it or we were asked not to.
                    if latest_version(param, refresh=False) == inst_v:
                        all_uses = __salt__['portage_config.get_cleared_flags'](param)
                        if _flags_changed(*all_uses):
                            changes[param] = {'version': inst_v,
                                              'old': {'use': all_uses[0]},
                                              'new': {'use': all_uses[1]}}
                targets.append(target)
    else:
        targets = pkg_params

    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend(['emerge', '--ask', 'n', '--quiet'])
    cmd.extend(bin_opts)
    cmd.extend(emerge_opts)
    cmd.extend(targets)

    old = list_pkgs()
    call = __salt__['cmd.run_all'](cmd,
                                   output_loglevel='trace',
                                   python_shell=False)
    if call['retcode'] != 0:
        needed_changes = _process_emerge_err(call['stdout'], call['stderr'])
    else:
        needed_changes = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    changes.update(salt.utils.compare_dicts(old, new))

    if needed_changes:
        raise CommandExecutionError(
            'Error occurred installing package(s)',
            info={'needed changes': needed_changes, 'changes': changes}
        )

    return changes


def update(pkg, slot=None, fromrepo=None, refresh=False, binhost=None):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any emerge commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Updates the passed package (emerge --update package)

    slot
        Restrict the update to a particular slot. It will update to the
        latest version within the slot.

    fromrepo
        Restrict the update to a particular repository. It will update to the
        latest version within the repository.
    binhost
        has two options try and force.
        try - tells emerge to try and install the package from a configured binhost.
        force - forces emerge to install the package from a binhost otherwise it fails out.

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.update <package name>
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    full_atom = pkg

    if slot is not None:
        full_atom = '{0}:{1}'.format(full_atom, slot)

    if fromrepo is not None:
        full_atom = '{0}::{1}'.format(full_atom, fromrepo)

    if binhost == 'try':
        bin_opts = ['-g']
    elif binhost == 'force':
        bin_opts = ['-G']
    else:
        bin_opts = []

    old = list_pkgs()
    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend(['emerge',
                '--ask', 'n',
                '--quiet',
                '--update',
                '--newuse',
                '--oneshot'])
    cmd.extend(bin_opts)
    cmd.append(full_atom)
    call = __salt__['cmd.run_all'](cmd,
                                   output_loglevel='trace',
                                   python_shell=False)
    if call['retcode'] != 0:
        needed_changes = _process_emerge_err(call['stdout'], call['stderr'])
    else:
        needed_changes = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if needed_changes:
        raise CommandExecutionError(
            'Problem encountered updating package(s)',
            info={'needed_changes': needed_changes, 'changes': ret}
        )

    return ret


def upgrade(refresh=True, binhost=None, backtrack=3):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any emerge commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Run a full system upgrade (emerge -uDN @world)

    binhost
        has two options try and force.
        try - tells emerge to try and install the package from a configured binhost.
        force - forces emerge to install the package from a binhost otherwise it fails out.

    backtrack
        Specifies an integer number of times to backtrack if dependency
        calculation fails due to a conflict or an unsatisfied dependency
        (default: ´3´).

        .. versionadded: 2015.8.0

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
           'comment': ''}

    if salt.utils.is_true(refresh):
        refresh_db()

    if binhost == 'try':
        bin_opts = ['--getbinpkg']
    elif binhost == 'force':
        bin_opts = ['--getbinpkgonly']
    else:
        bin_opts = []

    old = list_pkgs()
    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend(['emerge',
                '--ask', 'n',
                '--quiet',
                '--backtrack', '{0}'.format(backtrack),
                '--update',
                '--newuse',
                '--deep'])
    if bin_opts:
        cmd.extend(bin_opts)
    cmd.append('@world')

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


def remove(name=None, slot=None, fromrepo=None, pkgs=None, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any emerge commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages via emerge --unmerge.

    name
        The name of the package to be deleted.

    slot
        Restrict the remove to a specific slot. Ignored if ``name`` is None.

    fromrepo
        Restrict the remove to a specific slot. Ignored if ``name`` is None.

    Multiple Package Options:

    pkgs
        Uninstall multiple packages. ``slot`` and ``fromrepo`` arguments are
        ignored if this argument is present. Must be passed as a python list.

    .. versionadded:: 0.16.0

    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package name> slot=4.4 fromrepo=gentoo
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    if name and not pkgs and (slot is not None or fromrepo is not None)and len(pkg_params) == 1:
        fullatom = name
        if slot is not None:
            targets = ['{0}:{1}'.format(fullatom, slot)]
        if fromrepo is not None:
            targets = ['{0}::{1}'.format(fullatom, fromrepo)]
        targets = [fullatom]
    else:
        targets = [x for x in pkg_params if x in old]

    if not targets:
        return {}

    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend(['emerge',
                '--ask', 'n',
                '--quiet',
                '--unmerge',
                '--quiet-unmerge-warn'])
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


def purge(name=None, slot=None, fromrepo=None, pkgs=None, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any emerge commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Portage does not have a purge, this function calls remove followed
    by depclean to emulate a purge process

    name
        The name of the package to be deleted.

    slot
        Restrict the remove to a specific slot. Ignored if name is None.

    fromrepo
        Restrict the remove to a specific slot. Ignored if ``name`` is None.

    Multiple Package Options:

    pkgs
        Uninstall multiple packages. ``slot`` and ``fromrepo`` arguments are
        ignored if this argument is present. Must be passed as a python list.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package name> slot=4.4
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    ret = remove(name=name, slot=slot, fromrepo=fromrepo, pkgs=pkgs)
    ret.update(depclean(name=name, slot=slot, fromrepo=fromrepo, pkgs=pkgs))
    return ret


def depclean(name=None, slot=None, fromrepo=None, pkgs=None):
    '''
    Portage has a function to remove unused dependencies. If a package
    is provided, it will only removed the package if no other package
    depends on it.

    name
        The name of the package to be cleaned.

    slot
        Restrict the remove to a specific slot. Ignored if ``name`` is None.

    fromrepo
        Restrict the remove to a specific slot. Ignored if ``name`` is None.

    pkgs
        Clean multiple packages. ``slot`` and ``fromrepo`` arguments are
        ignored if this argument is present. Must be passed as a python list.

    Return a list containing the removed packages:

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.depclean <package name>
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    if name and not pkgs and (slot is not None or fromrepo is not None)and len(pkg_params) == 1:
        fullatom = name
        if slot is not None:
            targets = ['{0}:{1}'.format(fullatom, slot)]
        if fromrepo is not None:
            targets = ['{0}::{1}'.format(fullatom, fromrepo)]
        targets = [fullatom]
    else:
        targets = [x for x in pkg_params if x in old]

    cmd = ['emerge', '--ask', 'n', '--quiet', '--depclean'] + targets
    __salt__['cmd.run_all'](cmd,
                            output_loglevel='trace',
                            python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def version_cmp(pkg1, pkg2, **kwargs):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2.4-0' '0.2.4.1-0'
    '''
    # ignore_epoch is not supported here, but has to be included for API
    # compatibility. Rather than putting this argument into the function
    # definition (and thus have it show up in the docs), we just pop it out of
    # the kwargs dict and then raise an exception if any kwargs other than
    # ignore_epoch were passed.
    kwargs = salt.utils.clean_kwargs(**kwargs)
    kwargs.pop('ignore_epoch', None)
    if kwargs:
        salt.utils.invalid_kwargs(kwargs)

    regex = r'^~?([^:\[]+):?[^\[]*\[?.*$'
    ver1 = re.match(regex, pkg1)
    ver2 = re.match(regex, pkg2)

    if ver1 and ver2:
        return portage.versions.vercmp(ver1.group(1), ver2.group(1))
    return None


def version_clean(version):
    '''
    Clean the version string removing extra data.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_clean <version_string>
    '''
    return re.match(r'^~?[<>]?=?([^<>=:\[]+).*$', version)


def check_extra_requirements(pkgname, pkgver):
    '''
    Check if the installed package already has the given requirements.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.check_extra_requirements 'sys-devel/gcc' '~>4.1.2:4.1::gentoo[nls,fortran]'
    '''
    keyword = None

    match = re.match('^(~)?([<>])?(=)?([^<>=]*)$', pkgver)
    if match:
        keyword, gt_lt, eq, verstr = match.groups()
        prefix = gt_lt or ''
        prefix += eq or ''
        # We need to delete quotes around use flag list elements
        verstr = verstr.replace("'", "")
        # If no prefix characters were supplied and verstr contains a version, use '='
        if verstr[0] != ':' and verstr[0] != '[':
            prefix = prefix or '='
            atom = '{0}{1}-{2}'.format(prefix, pkgname, verstr)
        else:
            atom = '{0}{1}'.format(pkgname, verstr)
    else:
        return True

    try:
        cpv = _porttree().dbapi.xmatch('bestmatch-visible', atom)
    except portage.exception.InvalidAtom as iae:
        log.error('Unable to find a matching package for {0}: ({1})'.format(atom, iae))
        return False

    if cpv == '':
        return False

    try:
        cur_repo, cur_use = _vartree().dbapi.aux_get(cpv, ['repository', 'USE'])
    except KeyError:
        return False

    des_repo = re.match(r'^.+::([^\[]+).*$', atom)
    if des_repo and des_repo.group(1) != cur_repo:
        return False

    des_uses = set(portage.dep.dep_getusedeps(atom))
    cur_use = cur_use.split()
    if len([x for x in des_uses.difference(cur_use)
            if x[0] != '-' or x[1:] in cur_use]) > 0:
        return False

    if keyword:
        if not __salt__['portage_config.has_flag']('accept_keywords', atom, '~ARCH'):
            return False

    return True

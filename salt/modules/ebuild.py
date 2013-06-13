'''
Support for Portage

:optdepends:    - portage Python adapter

For now all package names *MUST* include the package category,
i.e. ``'vim'`` will not work, ``'app-editors/vim'`` will.
'''

# Import python libs
import copy
import logging
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

HAS_PORTAGE = False

# Import third party libs
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


def __virtual__():
    '''
    Confirm this module is on a Gentoo based system
    '''
    return 'pkg' if (HAS_PORTAGE and __grains__['os'] == 'Gentoo') else False


def _vartree():
    return portage.db[portage.root]['vartree']


def _porttree():
    return portage.db[portage.root]['porttree']


def _cpv_to_name(cpv):
    if cpv == '':
        return ''
    return str(portage.cpv_getkey(cpv))


def _cpv_to_version(cpv):
    return portage.versions.cpv_getversion(cpv)

def _process_emerge_err(stderr):
    '''
    Used to parse emerge output to provide meaningful output when emerge fails
    '''
    ret = {}
    changes = {}
    rexp = re.compile(r'([<>=][^ ]+/[^ ]+ [^\n]+)')

    sections = re.split('\n\n', stderr)
    for section in sections:
        if 'The following keyword changes' in section:
            changes['keywords'] = rexp.findall(section)
        elif 'The following license changes' in section:
            changes['license'] = rexp.findall(section)
        elif 'The following USE changes' in section:
            changes['use'] = rexp.findall(section)
        elif 'The following mask changes' in section:
            changes['mask'] = rexp.findall(section)
    ret['changes'] = changes
    return ret


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
        installed = _cpv_to_version(_vartree().dep_bestmatch(name))
        avail = _cpv_to_version(_porttree().dep_bestmatch(name))
        if avail:
            if not installed or compare(pkg1=installed, oper='<', pkg2=avail):
                ret[name] = avail

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def _get_upgradable():
    '''
    Utility function to get upgradable packages

    Sample return data:
    { 'pkgname': '1.2.3-45', ... }
    '''

    cmd = 'emerge --pretend --update --newuse --deep --ask n --with-bdeps=y world'
    out = __salt__['cmd.run_stdout'](cmd)

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


def list_upgrades(refresh=True):
    '''
    List all available package upgrades.

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    return _get_upgradable()


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

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
    if not name:
        return []
    else:
        return [x for x in _porttree().getallnodes()
                if x.endswith('/' + str(name))]


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

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
    pkgs = _vartree().dbapi.cpv_all()
    for cpv in pkgs:
        __salt__['pkg_resource.add_pkg'](ret,
                                         _cpv_to_name(cpv),
                                         _cpv_to_version(cpv))
    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def refresh_db():
    '''
    Updates the portage tree (emerge --sync). Uses eix-sync if available.

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    if 'eix.sync' in __salt__:
        return __salt__['eix.sync']()

    if 'makeconf.features_contains'in __salt__ and __salt__['makeconf.features_contains']('webrsync-gpg'):
        # GPG sign verify is supported only for "webrsync"
        cmd = 'emerge-webrsync -q'
        if salt.utils.which('emerge-delta-webrsync'): # We prefer 'delta-webrsync' to 'webrsync'
            cmd = 'emerge-delta-webrsync -q'
        return __salt__['cmd.retcode'](cmd) == 0
    else:
        if __salt__['cmd.retcode']('emerge --sync --ask n --quiet') == 0:
            return True
        # We fall back to "webrsync" if "rsync" fails for some reason
        cmd = 'emerge-webrsync -q'
        if salt.utils.which('emerge-delta-webrsync'): # We prefer 'delta-webrsync' to 'webrsync'
            cmd = 'emerge-delta-webrsync -q'
        return __salt__['cmd.retcode'](cmd) == 0

def install(name=None,
            refresh=False,
            pkgs=None,
            sources=None,
            slot=None,
            **kwargs):
    '''
    Install the passed package(s), add refresh=True to sync the portage tree
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to emerge a package from the
        portage tree. To install a tbz2 package manually, use the "sources"
        option described below.

        CLI Example::
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

        CLI Example::
            salt '*' pkg.install sys-devel/gcc slot='4.4'


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from the portage tree. Must be passed as
        a python list.

        CLI Example::
            salt '*' pkg.install pkgs='["foo","bar"]'

    sources
        A list of tbz2 packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::
            salt '*' pkg.install sources='[{"foo": "salt://foo.tbz2"},{"bar": "salt://bar.tbz2"}]'


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
            'kwargs': kwargs
        }
    ))
    if salt.utils.is_true(refresh):
        refresh_db()

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources,
                                                                  **kwargs)

    # Handle version kwarg for a single package target
    if pkgs is None and sources is None:
        version_num = kwargs.get('version')
        if version_num:
            pkg_params = {name: version_num}
        elif slot is not None:
            pkg_params = {name: ':{0}'.format(slot)}

    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        emerge_opts = 'tbz2file'
    else:
        emerge_opts = ''

    if pkg_type == 'repository':
        targets = list()
        for param, version_num in pkg_params.iteritems():
            if version_num is None:
                targets.append(param)
            elif version_num.startswith(':'):
                # Really this 'version' is a slot
                targets.append('{0}{1}'.format(param, version_num))
            else:
                match = re.match('^([<>])?(=)?([^<>=]+)$', version_num)
                if match:
                    gt_lt, eq, verstr = match.groups()
                    prefix = gt_lt or ''
                    prefix += eq or ''
                    # If no prefix characters were supplied, use '='
                    prefix = prefix or '='
                    targets.append('"{0}{1}-{2}"'.format(prefix, param, verstr))
    else:
        targets = pkg_params
    cmd = 'emerge --quiet --ask n {0} {1}'.format(emerge_opts, ' '.join(targets))
    old = list_pkgs()
    call = __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    if call['retcode'] != 0:
        return _process_emerge_err(call['stderr'])
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def update(pkg, slot=None, refresh=False):
    '''
    Updates the passed package (emerge --update package)

    slot
        Restrict the update to a particular slot. It will update to the
        latest version within the slot.

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.update <package name>
    '''
    if(refresh):
        refresh_db()

    if slot is not None:
        full_atom = '{0}:{1}'.format(pkg, slot)
    else:
        full_atom = pkg

    old = list_pkgs()
    cmd = 'emerge --update --newuse --oneshot --with-bdeps=y --ask n --quiet {0}'.format(full_atom)
    call = __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    if call['retcode'] != 0:
        return _process_emerge_err(call['stderr'])
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def upgrade(refresh=True):
    '''
    Run a full system upgrade (emerge --update world)

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    old = list_pkgs()
    cmd = 'emerge --update --newuse --deep --with-bdeps=y --ask n --quiet world'
    call = __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    if call['retcode'] != 0:
        return _process_emerge_err(call['stderr'])
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, slot=None, pkgs=None, **kwargs):
    '''
    Remove packages via emerge --unmerge.

    name
        The name of the package to be deleted.

    slot
        Restrict the remove to a specific slot. Ignored if ``name`` is None.


    Multiple Package Options:

    pkgs
        Uninstall multiple packages. ``slot`` argument is ignored if this
        argument is present. Must be passed as a python list.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package name> slot=4.4
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    old = list_pkgs()
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]

    if name and not pkgs and slot is not None and len(pkg_params) == 1:
        targets = ['{0}:{1}'.format(name, slot)]
    else:
        targets = [x for x in pkg_params if x in old]

    if not targets:
        return {}
    cmd = 'emerge --unmerge --quiet --quiet-unmerge-warn --ask n' \
          '{0}'.format(' '.join(targets))
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def purge(name=None, slot=None, pkgs=None, **kwargs):
    '''
    Portage does not have a purge, this function calls remove followed
    by depclean to emulate a purge process

    name
        The name of the package to be deleted.

    slot
        Restrict the remove to a specific slot. Ignored if name is None.


    Multiple Package Options:

    pkgs
        Uninstall multiple packages. ``slot`` argument is ignored if this
        argument is present. Must be passed as a python list.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package name> slot=4.4
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    ret = remove(name=name, slot=slot, pkgs=pkgs)
    ret.update(depclean(name=name, slot=slot, pkgs=pkgs))
    return ret


def depclean(name=None, slot=None, pkgs=None):
    '''
    Portage has a function to remove unused dependencies. If a package
    is provided, it will only removed the package if no other package
    depends on it.

    name
        The name of the package to be cleaned.

    slot
        Restrict the remove to a specific slot. Ignored if ``name`` is None.

    pkgs
        Clean multiple packages. ``slot`` argument is ignored if this
        argument is present. Must be passed as a python list.

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.depclean <package name>
    '''
    old = list_pkgs()
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]

    if name and not pkgs and slot is not None and len(pkg_params) == 1:
        targets = ['{0}:{1}'.format(name, slot)]
    else:
        targets = [x for x in pkg_params if x in old]

    cmd = 'emerge --depclean --ask n --quiet {0}'.format(' '.join(targets))
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def perform_cmp(pkg1='', pkg2=''):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example::

        salt '*' pkg.perform_cmp '0.2.4-0' '0.2.4.1-0'
        salt '*' pkg.perform_cmp pkg1='0.2.4-0' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.perform_cmp'](pkg1=pkg1, pkg2=pkg2)


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Compare two version strings.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '<' '0.2.4.1-0'
        salt '*' pkg.compare pkg1='0.2.4-0' oper='<' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](pkg1=pkg1, oper=oper, pkg2=pkg2)

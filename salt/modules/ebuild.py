'''
Support for Portage

:optdepends:    - portage Python adapter

For now all package names *MUST* include the package category,
i.e. :code:`'vim'` will not work, :code:`'app-editors/vim'` will.
'''

# Import python libs
import logging

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
    if cpv == '':
        return ''
    return str(cpv[len(_cpv_to_name(cpv) + '-'):])


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    return _cpv_to_version(_porttree().dep_bestmatch(name))


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    return _cpv_to_version(_vartree().dep_bestmatch(name))


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


def list_pkgs():
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    ret = {}
    pkgs = _vartree().dbapi.cpv_all()
    for cpv in pkgs:
        ret[_cpv_to_name(cpv)] = _cpv_to_version(cpv)
        __salt__['pkg_resource.add_pkg'](ret,
                                         _cpv_to_name(cpv),
                                         _cpv_to_version(cpv))
    __salt__['pkg_resource.sort_pkglist'](ret)
    return ret


def refresh_db():
    '''
    Updates the portage tree (emerge --sync). Uses eix-sync if available.

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    if 'eix.sync' in __salt__:
        return __salt__['eix.sync']()
    return __salt__['cmd.retcode']('emerge --sync --quiet') == 0


def install(name=None, refresh=False, pkgs=None, sources=None, **kwargs):
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

    logging.debug('Called modules.pkg.install: {0}'.format(
        {
            'name': name,
            'refresh': refresh,
            'pkgs': pkgs,
            'sources': sources,
            'kwargs': kwargs
        }
    ))
    # Catch both boolean input from state and string input from CLI
    if refresh is True or refresh == 'True':
        refresh_db()

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources)
    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        emerge_opts = 'tbz2file'
    else:
        emerge_opts = ''

    cmd = 'emerge --quiet {0} {1}'.format(emerge_opts, ' '.join(pkg_params))
    old = list_pkgs()
    stderr = __salt__['cmd.run_all'](cmd).get('stderr', '')
    if stderr:
        log.error(stderr)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def update(pkg, refresh=False):
    '''
    Updates the passed package (emerge --update package)

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.update <package name>
    '''
    if(refresh):
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'emerge --update --newuse --oneshot --quiet {0}'.format(pkg)
    __salt__['cmd.retcode'](cmd)
    new_pkgs = list_pkgs()

    for pkg in new_pkgs:
        if pkg in old_pkgs:
            if old_pkgs[pkg] == new_pkgs[pkg]:
                continue
            else:
                ret_pkgs[pkg] = {'old': old_pkgs[pkg],
                             'new': new_pkgs[pkg]}
        else:
            ret_pkgs[pkg] = {'old': '',
                         'new': new_pkgs[pkg]}

    return ret_pkgs


def upgrade(refresh=False):
    '''
    Run a full system upgrade (emerge --update world)

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    if(refresh):
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'emerge --update --newuse --deep --with-bdeps=y --quiet world'
    __salt__['cmd.retcode'](cmd)
    new_pkgs = list_pkgs()

    for pkg in new_pkgs:
        if pkg in old_pkgs:
            if old_pkgs[pkg] == new_pkgs[pkg]:
                continue
            else:
                ret_pkgs[pkg] = {'old': old_pkgs[pkg],
                                 'new': new_pkgs[pkg]}
        else:
            ret_pkgs[pkg] = {'old': '',
                             'new': new_pkgs[pkg]}

    return ret_pkgs


def remove(pkg):
    '''
    Remove a single package via emerge --unmerge

    Return a list containing the names of the removed packages:

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    cmd = 'emerge --unmerge --quiet --quiet-unmerge-warn {0}'.format(pkg)
    __salt__['cmd.retcode'](cmd)
    new_pkgs = list_pkgs()

    for pkg in old_pkgs:
        if not pkg in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def purge(pkg):
    '''
    Portage does not have a purge, this function calls remove followed
    by depclean to emulate a purge process

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.purge <package name>

    '''
    return remove(pkg) + depclean()


def depclean(pkg=None):
    '''
    Portage has a function to remove unused dependencies. If a package
    is provided, it will only removed the package if no other package
    depends on it.

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.depclean <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    cmd = 'emerge --depclean --quiet {0}'.format(pkg)
    __salt__['cmd.retcode'](cmd)
    new_pkgs = list_pkgs()

    for pkg in old_pkgs:
        if not pkg in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def compare(version1='', version2=''):
    '''
    Compare two version strings. Return -1 if version1 < version2,
    0 if version1 == version2, and 1 if version1 > version2. Return None if
    there was a problem making the comparison.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](version1, version2)

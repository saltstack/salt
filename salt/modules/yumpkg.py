'''
Support for YUM

:depends:   - yum Python module
            - rpmUtils Python module
'''

# Import python libs
import copy
import os
import logging
import yaml

# Import salt libs
import salt.utils

# Import third party libs
try:
    import yum
    import rpmUtils.arch
    HAS_YUMDEPS = True
except (ImportError, AttributeError):
    HAS_YUMDEPS = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    if not HAS_YUMDEPS:
        return False

    # Work only on RHEL/Fedora based distros with python 2.6 or greater
    # TODO: Someone decide if we can just test os_family and pythonversion
    os_grain = __grains__['os']
    os_family = __grains__['os_family']
    try:
        os_major = int(__grains__['osrelease'].split('.')[0])
    except ValueError:
        os_major = 0

    if os_grain == 'Amazon':
        return 'pkg'
    elif os_grain == 'Fedora':
        # Fedora <= 10 used Python 2.5 and below
        if os_major >= 11:
            return 'pkg'
    elif os_grain == 'XCP':
        if os_major >= 2:
            return 'pkg'
    elif os_grain == 'XenServer':
        if os_major > 6:
            return 'pkg'
    elif os_family == 'RedHat' and os_major >= 6:
        return 'pkg'
    return False


class _YumErrorLogger(object):
    '''
    A YUM callback handler that logs failed packages with their associated
    script output.

    See yum.rpmtrans.NoOutputCallBack in the yum package for base
    implementation.
    '''
    def __init__(self):
        self.messages = {}
        self.failed = []

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
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
        # TODO: extend this for more conclusive transaction handling for
        # installs and removes VS. the pkg list compare method used now.
        #
        # See yum.constants and yum.rpmtrans.RPMBaseCallback in the yum
        # package for more information about the received actions.
        if action == yum.constants.TS_FAILED:
            self.failed.append(package)

    def scriptout(self, package, msgs):
        # This handler covers ancillary messages coming from the RPM script
        # Will sometimes contain more detailed error messages.
        self.messages[package] = msgs


def list_upgrades(refresh=True):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    pkgs = list_pkgs()

    yumbase = yum.YumBase()
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
    Accepts a yum.YumBase() object and runs member functions to enable/disable
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
            log.info('Restricting to repo \'{0}\''.format(fromrepo))
            yumbase.repos.disableRepo('*')
            yumbase.repos.enableRepo(fromrepo)
        else:
            if disablerepo:
                log.info('Disabling repo \'{0}\''.format(disablerepo))
                yumbase.repos.disableRepo(disablerepo)
            if enablerepo:
                log.info('Enabling repo \'{0}\''.format(enablerepo))
                yumbase.repos.enableRepo(enablerepo)
    except yum.Errors.RepoError as e:
        return e


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=epel-testing
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''

    yumbase = yum.YumBase()
    error = _set_repo_options(yumbase, **kwargs)
    if error:
        log.error(error)

    # look for available packages only, if package is already installed with
    # latest version it will not show up here.  If we want to use wildcards
    # here we can, but for now its exact match only.
    for pkgtype in ('available', 'updates'):
        pkglist = yumbase.doPackageLists(pkgtype)
        exactmatch, matched, unmatched = yum.packages.parsePackages(
            pkglist, names
        )
        for pkg in exactmatch:
            if pkg.name in ret \
                    and (pkg.arch in rpmUtils.arch.legitMultiArchesInSameLib()
                         or pkg.arch == 'noarch'):
                ret[pkg.name] = '-'.join([pkg.version, pkg.release])

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


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
    yb = yum.YumBase()
    for p in yb.rpmdb:
        name = p.name
        if __grains__.get('cpuarch', '') == 'x86_64' and p.arch == 'i686':
            name += '.i686'
        pkgver = p.version
        if p.release:
            pkgver += '-{0}'.format(p.release)
        __salt__['pkg_resource.add_pkg'](ret, name, pkgver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    yumbase = yum.YumBase()
    yumbase.cleanMetadata()
    return True


def clean_metadata():
    '''
    Cleans local yum metadata.

    CLI Example::

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

        CLI Example::

            salt '*' pkg.group_install groups='["Group 1", "Group 2"]'

    skip
        The name(s), in a list, of any packages that would normally be
        installed by the package group ("default" packages), which should not
        be installed.

        CLI Examples::

            salt '*' pkg.group_install 'My Group' skip='["foo", "bar"]'

    include
        The name(s), in a list, of any packages which are included in a group,
        which would not normally be installed ("optional" packages). Note that
        this will nor enforce group membership; if you include packages which
        are not members of the specified groups, they will still be installed.

        CLI Examples::

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

        32-bit packages can be installed on 64-bit systems by appending
        ``.i686`` to the end of the package name.

        CLI Example::
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

        CLI Examples::
            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4.el6"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::
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

    yumbase = yum.YumBase()
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
                    if __grains__.get('cpuarch', '') == 'x86_64' \
                            and pkgname.endswith('.i686'):
                        # Remove '.i686' from pkgname
                        pkgname = pkgname[:-5]
                        arch = '.i686'
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
        yumlogger = _YumErrorLogger()
        yumbase.processTransaction(rpmDisplay=yumlogger)
        yumlogger.log_accumulated_errors()
        yumbase.closeRpmDB()
    except Exception as e:
        log.error('Install failed: {0}'.format(e))

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def upgrade(refresh=True):
    '''
    Run a full system upgrade, a yum upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    yumbase = yum.YumBase()
    setattr(yumbase.conf, 'assumeyes', True)

    old = list_pkgs()

    try:
        # ideally we would look in the yum transaction and get info on all the
        # packages that are going to be upgraded and only look up old/new
        # version info on those packages.
        yumbase.update()
        log.info('Resolving dependencies')
        yumbase.resolveDeps()
        yumlogger = _YumErrorLogger()
        log.info('Processing transaction')
        yumbase.processTransaction(rpmDisplay=yumlogger)
        yumlogger.log_accumulated_errors()
        yumbase.closeRpmDB()
    except Exception as e:
        log.error('Upgrade failed: {0}'.format(e))

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Removes packages using python API for yum.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''

    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    yumbase = yum.YumBase()
    setattr(yumbase.conf, 'assumeyes', True)

    # same comments as in upgrade for remove.
    for target in targets:
        if __grains__.get('cpuarch', '') == 'x86_64' \
                and target.endswith('.i686'):
            target = target[:-5]
            arch = 'i686'
        else:
            arch = None
        yumbase.remove(name=target, arch=arch)

    log.info('Resolving dependencies')
    yumbase.resolveDeps()
    yumlogger = _YumErrorLogger()
    log.info('Processing transaction')
    yumbase.processTransaction(rpmDisplay=yumlogger)
    yumlogger.log_accumulated_errors()
    yumbase.closeRpmDB()

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported by yum, this function is identical to
    ``remove()``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs)


def verify(*package):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    CLI Example::

        salt '*' pkg.verify
    '''
    return __salt__['lowpkg.verify'](*package)


def group_list():
    '''
    Lists all groups known by yum on this system

    CLI Example::

        salt '*' pkg.group_list
    '''
    ret = {'installed': [], 'available': [], 'available languages': {}}
    yumbase = yum.YumBase()
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

    CLI Example::

        salt '*' pkg.group_info 'Perl Support'
    '''
    yumbase = yum.YumBase()
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

    CLI Example::

        salt '*' pkg.group_diff 'Perl Support'
    '''
    ret = {
        'mandatory packages': {'installed': [], 'not installed': []},
        'optional packages': {'installed': [], 'not installed': []},
        'default packages': {'installed': [], 'not installed': []},
        'conditional packages': {'installed': [], 'not installed': []},
    }
    pkgs = list_pkgs()
    yumbase = yum.YumBase()
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


def list_repos(basedir='/etc/yum.repos.d'):
    '''
    Lists all repos in <basedir> (default: /etc/yum.repos.d/).

    CLI Example::

        salt '*' pkg.list_repos
    '''
    repos = {}
    for repofile in os.listdir(basedir):
        repopath = '{0}/{1}'.format(basedir, repofile)
        if not repofile.endswith('.repo'):
            continue
        header, filerepos = _parse_repo_file(repopath)
        for reponame in filerepos.keys():
            repo = filerepos[reponame]
            repo['file'] = repopath
            repos[reponame] = repo
    return repos


def get_repo(repo, basedir='/etc/yum.repos.d', **kwargs):
    '''
    Display a repo from <basedir> (default basedir: /etc/yum.repos.d).

    CLI Examples::

        salt '*' pkg.get_repo myrepo
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir
    '''
    repos = list_repos(basedir)

    # Find out what file the repo lives in
    repofile = ''
    for arepo in repos.keys():
        if arepo == repo:
            repofile = repos[arepo]['file']
    if not repofile:
        raise Exception('repo {0} was not found in {1}'.format(repo, basedir))

    # Return just one repo
    header, filerepos = _parse_repo_file(repofile)
    return filerepos[repo]


def del_repo(repo, basedir='/etc/yum.repos.d', **kwargs):
    '''
    Delete a repo from <basedir> (default basedir: /etc/yum.repos.d).

    If the .repo file that the repo exists in does not contain any other repo
    configuration, the file itself will be deleted.

    CLI Examples::

        salt '*' pkg.del_repo myrepo
        salt '*' pkg.del_repo myrepo basedir=/path/to/dir
    '''
    repos = list_repos(basedir)

    if repo not in repos:
        return 'Error: the {0} repo does not exist in {1}'.format(repo, basedir)

    # Find out what file the repo lives in
    repofile = ''
    for arepo in repos:
        if arepo == repo:
            repofile = repos[arepo]['file']

    # See if the repo is the only one in the file
    onlyrepo = True
    for arepo in repos.keys():
        if arepo == repo:
            continue
        if repos[arepo]['file'] == repofile:
            onlyrepo = False

    # If this is the only repo in the file, delete the file itself
    if onlyrepo:
        os.remove(repofile)
        return 'File {0} containing repo {1} has been removed'.format(
            repofile, repo)

    # There must be other repos in this file, write the file with them
    header, filerepos = _parse_repo_file(repofile)
    content = header
    for stanza in filerepos.keys():
        if stanza == repo:
            continue
        comments = ''
        if 'comments' in filerepos[stanza]:
            comments = '\n'.join(filerepos[stanza]['comments'])
            del filerepos[stanza]['comments']
        content += '\n[{0}]'.format(stanza)
        for line in filerepos[stanza]:
            content += '\n{0}={1}'.format(line, filerepos[stanza][line])
        content += '\n{0}\n'.format(comments)
    fileout = open(repofile, 'w')
    fileout.write(content)
    fileout.close()

    return 'Repo {0} has been remooved from {1}'.format(repo, repofile)


def mod_repo(repo, basedir=None, **kwargs):
    '''
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified::

        repo (name by which the yum refers to the repo)
        name (a human-readable name for the repo)
        baseurl or mirrorlist (the URL for yum to reference)

    Key/Value pairs may also be removed from a repo's configuration by setting
    a key to a blank value. Bear in mind that a name cannot be deleted, and a
    baseurl can only be deleted if a mirrorlist is specified (or vice versa).

    CLI Examples::

        salt '*' pkg.mod_repo reponame enabled=1 gpgcheck=1
        salt '*' pkg.mod_repo reponame basedir=/path/to/dir enabled=1
        salt '*' pkg.mod_repo reponame baseurl= mirrorlist=http://host.com/
    '''
    # Build a list of keys to be deleted
    todelete = []
    for key in kwargs.keys():
        if kwargs[key] != 0 and not kwargs[key]:
            del kwargs[key]
            todelete.append(key)

    # Fail if the user tried to delete the name
    if 'name' in todelete:
        return 'Error: The repo name cannot be deleted'

    # Give the user the ability to change the basedir
    repos = {}
    if basedir:
        repos = list_repos(basedir)
    else:
        repos = list_repos()
        basedir = '/etc/yum.repos.d'

    repofile = ''
    header = ''
    filerepos = {}
    if repo not in repos:
        # If the repo doesn't exist, create it in a new file
        repofile = '{0}/{1}.repo'.format(basedir, repo)

        if 'name' not in kwargs:
            return ('Error: The repo does not exist and needs to be created, '
                    'but a name was not given')

        if 'baseurl' not in kwargs and 'mirrorlist' not in kwargs:
            return ('Error: The repo does not exist and needs to be created, '
                    'but either a baseurl or a mirrorlist needs to be given')
        filerepos[repo] = {}
    else:
        # The repo does exist, open its file
        repofile = repos[repo]['file']
        header, filerepos = _parse_repo_file(repofile)

    # Error out if they tried to delete baseurl or mirrorlist improperly
    if 'baseurl' in todelete:
        if 'mirrorlist' not in kwargs and 'mirrorlist' \
                not in filerepos[repo].keys():
            return 'Error: Cannot delete baseurl without specifying mirrorlist'
    if 'mirrorlist' in todelete:
        if 'baseurl' not in kwargs and 'baseurl' \
                not in filerepos[repo].keys():
            return 'Error: Cannot delete mirrorlist without specifying baseurl'

    # Delete anything in the todelete list
    for key in todelete:
        if key in filerepos[repo].keys():
            del filerepos[repo][key]

    # Old file or new, write out the repos(s)
    filerepos[repo].update(kwargs)
    content = header
    for stanza in filerepos.keys():
        comments = ''
        if 'comments' in filerepos[stanza].keys():
            comments = '\n'.join(filerepos[stanza]['comments'])
            del filerepos[stanza]['comments']
        content += '\n[{0}]'.format(stanza)
        for line in filerepos[stanza].keys():
            content += '\n{0}={1}'.format(line, filerepos[stanza][line])
        content += '\n{0}\n'.format(comments)
    fileout = open(repofile, 'w')
    fileout.write(content)
    fileout.close()

    return {repofile: filerepos}


def _parse_repo_file(filename):
    '''
    Turn a single repo file into a dict
    '''
    rfile = open(filename, 'r')
    repos = {}
    header = ''
    repo = ''
    for line in rfile:
        if line.startswith('['):
            repo = line.strip().replace('[', '').replace(']', '')
            repos[repo] = {}

        # Even though these are essentially uselss, I want to allow the user
        # to maintain their own comments, etc
        if not line:
            if not repo:
                header += line
        if line.startswith('#'):
            if not repo:
                header += line
            else:
                if 'comments' not in repos[repo]:
                    repos[repo]['comments'] = []
                repos[repo]['comments'].append(line.strip())
            continue

        # These are the actual configuration lines that matter
        if '=' in line:
            comps = line.strip().split('=')
            repos[repo][comps[0].strip()] = '='.join(comps[1:])

    return (header, repos)


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


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's rpm database (not generally
    recommended).

    CLI Examples::

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

    CLI Examples::

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_dict'](*packages)


def expand_repo_def(repokwargs):
    '''
    Take a repository definition and expand it to the full pkg repository dict
    that can be used for comparison.  This is a helper function to make
    certain repo managers sane for comparison in the pkgrepo states.

    There is no use to calling this function via the CLI.
    '''
    # YUM doesn't need the data massaged.
    return repokwargs

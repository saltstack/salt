'''
Support for YUM

:depends:   - yum Python module
            - rpmUtils Python module
'''

# Import python libs
import yaml
import os
import logging

# Import third party libs
try:
    import yum
    from rpmUtils.arch import getBaseArch
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


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    # Force input to be a list so below loop works
    if not isinstance(old, list):
        old = [old]
    if not isinstance(new, list):
        new = [new]
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)

    return pkgs


def list_upgrades(refresh=True):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
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
                if pkg.arch == getBaseArch() or pkg.arch == 'noarch':
                    versions_list[pkg['name']] = '-'.join(
                        [pkg['version'], pkg['release']]
                    )
    return versions_list


def available_version(*names):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.available_version <package name>
        salt '*' pkg.available_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
    yumbase = yum.YumBase()
    # look for available packages only, if package is already installed with
    # latest version it will not show up here.  If we want to use wildcards
    # here we can, but for now its exact match only.
    for pkgtype in ['available', 'updates']:
        pkglist = yumbase.doPackageLists(pkgtype)
        exactmatch, matched, unmatched = yum.packages.parsePackages(
            pkglist, names
        )
        for pkg in exactmatch:
            if pkg.name in ret \
                    and (pkg.arch == getBaseArch() or pkg.arch == 'noarch'):
                ret[pkg.name] = '-'.join([pkg.version, pkg.release])

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return available_version(name) != ''


def version(*names):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    pkgs = list_pkgs()
    for name in names:
        ret[name] = pkgs.get(name, '')
    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


def list_pkgs():
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    ret = {}
    yb = yum.YumBase()
    for p in yb.rpmdb:
        pkgver = p.version
        if p.release:
            pkgver += '-{0}'.format(p.release)
        __salt__['pkg_resource.add_pkg'](ret, p.name, pkgver)
    __salt__['pkg_resource.sort_pkglist'](ret)
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
    
            salt '*' pkg.groupinstall groups='["Group 1", "Group 2"]'

    skip
        The name(s), in a list, of any packages that would normally be
        installed by the package group ("default" packages), which should not
        be installed.

        CLI Examples::
    
            salt '*' pkg.groupinstall 'My Group' skip='["foo", "bar"]'

    include
        The name(s), in a list, of any packages which are included in a group,
        which would not normally be installed ("optional" packages). Note that
        this will nor enforce group membership; if you include packages which
        are not members of the specified groups, they will still be installed.

        CLI Examples::
    
            salt '*' pkg.groupinstall 'My Group' include='["foo", "bar"]'

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

    ret = {}
    pkgs = []
    for group in pkg_groups:
        group_detail = group_info(group)
        for package in group_detail['mandatory packages'].keys():
            pkgs.append(package)
        for package in group_detail['default packages'].keys():
            if package not in skip_pkgs:
                pkgs.append(package)
        for package in include:
            pkgs.append(package)

    install_pkgs = yaml.safe_dump(pkgs)
    return install(pkgs=install_pkgs, **kwargs)


def install(name=None,
            refresh=False,
            fromrepo=None,
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
            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"},{"bar": "salt://bar.rpm"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    old = list_pkgs()

    yumbase = yum.YumBase()
    setattr(yumbase.conf, 'assumeyes', True)
    setattr(yumbase.conf, 'gpgcheck', not skip_verify)

    # Get repo options from the kwargs
    disablerepo = kwargs.get('disablerepo', '')
    enablerepo = kwargs.get('enablerepo', '')
    repo = kwargs.get('repo', '')

    version = kwargs.get('version')
    if version:
        if pkgs is None and sources is None:
            # Allow "version" to work for single package target
            pkg_params = {name: version}
        else:
            log.warning('"version" parameter will be ignored for muliple '
                        'package targets')

    # Support old "repo" argument
    if not fromrepo and repo:
        fromrepo = repo

    try:
        if fromrepo:
            log.info('Restricting install to repo \'{0}\''.format(fromrepo))
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
        log.error(e)
        return {}

    try:
        for target in pkg_params:
            if pkg_type == 'file':
                log.info(
                    'Selecting "{0}" for local installation'.format(target)
                )
                installed = yumbase.installLocal(target)
                # if yum didn't install anything, maybe its a downgrade?
                log.debug('Added {0} transactions'.format(len(installed)))
                if len(installed) == 0 and target not in old.keys():
                    log.info('Upgrade failed, trying local downgrade')
                    yumbase.downgradeLocal(target)
            else:
                version = pkg_params[target]
                if version is not None:
                    target = '{0}-{1}'.format(target, version)
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
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
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

    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(pkgs, **kwargs):
    '''
    Removes packages with yum remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package,package,package>
    '''

    yumbase = yum.YumBase()
    setattr(yumbase.conf, 'assumeyes', True)
    pkgs = pkgs.split(',')
    old = version(*pkgs)

    # same comments as in upgrade for remove.
    for pkg in pkgs:
        yumbase.remove(name=pkg)

    log.info('Resolving dependencies')
    yumbase.resolveDeps()
    yumlogger = _YumErrorLogger()
    log.info('Processing transaction')
    yumbase.processTransaction(rpmDisplay=yumlogger)
    yumlogger.log_accumulated_errors()
    yumbase.closeRpmDB()

    new = version(*pkgs)

    return _list_removed(old, new)


def purge(pkgs, **kwargs):
    '''
    Yum does not have a purge, this function calls remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(pkgs)


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

        salt '*' pkg.groupinfo 'Perl Support'
    '''
    yumbase = yum.YumBase()
    (installed, available) = yumbase.doGroupLists()
    for group in installed + available:
        if group.name == groupname:
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


def get_repo(repo, basedir='/etc/yum.repos.d'):
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


def del_repo(repo, basedir='/etc/yum.repos.d'):
    '''
    Delete a repo from <basedir> (default basedir: /etc/yum.repos.d).

    If the .repo file that the repo exists in does not contain any other repo
    configuration, the file itself will be deleted.

    CLI Examples::

        salt '*' pkg.del_repo myrepo
        salt '*' pkg.del_repo myrepo basedir=/path/to/dir
    '''
    repos = list_repos(basedir)

    if not repo in repos.keys():
        return 'Error: the {0} repo does not exist in {1}'.format(repo, basedir)

    # Find out what file the repo lives in
    repofile = ''
    for arepo in repos.keys():
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

    return 'Repo {0} has been remooved from {1}'.format(repo, repofile)


def mod_repo(repo, basedir=None, **kwargs):
    '''
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified::

        repo (name by which the yum refers to the repo)
        name (a human-readable name for the repo)
        baseurl or mirrorlist (the url for yum to reference)

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
        if not kwargs[key]:
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
    if not repo in repos.keys():
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
                if not 'comments' in repos[repo].keys():
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

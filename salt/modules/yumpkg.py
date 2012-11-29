'''
Support for YUM

:depends:   - yum Python module
            - rpm Python module
            - rpmUtils Python module
'''
try:
    import yum
    import rpm
    from rpmUtils.arch import getBaseArch
    has_yumdeps = True
except (ImportError, AttributeError):
    has_yumdeps = False

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    if not has_yumdeps:
        return False

    # Work only on RHEL/Fedora based distros with python 2.6 or greater
    os_grain = __grains__['os']
    os_family = __grains__['os_family']
    os_major_release = int(__grains__['osrelease'].split('.')[0])

    # Fedora <= 10 used Python 2.5 and below
    if os_grain == 'Fedora' and os_major_release >= 11:
        return 'pkg'
    elif os_grain == 'Amazon':
        return 'pkg'
    else:
        if os_family == 'RedHat' and os_grain != 'Fedora':
            if os_major_release >= 6:
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
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)

    return pkgs


def list_upgrades(*args):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    pkgs = list_pkgs()

    yb = yum.YumBase()
    versions_list = {}
    for pkgtype in ['updates']:
        pl = yb.doPackageLists(pkgtype)
        for pkg in pkgs:
            exactmatch, matched, unmatched = yum.packages.parsePackages(
                pl, [pkg]
            )
            for pkg in exactmatch:
                if pkg.arch == getBaseArch() or pkg.arch == 'noarch':
                    versions_list[pkg['name']] = '-'.join(
                        [pkg['version'], pkg['release']]
                    )
    return versions_list


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    yb = yum.YumBase()
    # look for available packages only, if package is already installed with
    # latest version it will not show up here.  If we want to use wildcards
    # here we can, but for now its exact match only.
    versions_list = []
    for pkgtype in ['available', 'updates']:

        pl = yb.doPackageLists(pkgtype)
        exactmatch, matched, unmatched = yum.packages.parsePackages(pl, [name])
        # build a list of available packages from either available or updates
        # this will result in a double match for a package that is already
        # installed.  Maybe we should just return the value if we get a hit
        # on available, and only iterate though updates if we don't..
        for pkg in exactmatch:
            if pkg.arch == getBaseArch() or pkg.arch == 'noarch':
                versions_list.append('-'.join([pkg.version, pkg.release]))

    if len(versions_list) == 0:
        # if versions_list is empty return empty string.  It may make sense
        # to also check if a package is installed and on latest version
        # already and return a message saying 'up to date' or something along
        # those lines.
        return ''
    # remove the duplicate items from the list and return the first one
    return list(set(versions_list))[0]


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return available_version(name)


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    # since list_pkgs is used to support matching complex versions
    # we can search for a digit in the name and if one doesn't exist
    # then just use the dbMatch function, which is 1000 times quicker
    m = re.search("[0-9]", name)
    if m:
        pkgs = list_pkgs(name)
    else:
        ts = rpm.TransactionSet()
        mi = ts.dbMatch('name', name)
        pkgs = {}
        for h in mi:
            pkgs[h['name']] = "-".join([h['version'], h['release']])
    if name in pkgs:
        return pkgs[name]
    else:
        return ''


def list_pkgs(*args):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    ts = rpm.TransactionSet()
    pkgs = {}
    # In order to support specific package versions, we are going to use the
    # yum libraries to handle pattern matching
    yb = yum.YumBase()
    setattr(yb.conf, 'assumeyes', True)

    # if no args are passed in get all packages
    if len(args) == 0:
        for h in ts.dbMatch():
            pkgs[h['name']] = '-'.join([h['version'], h['release']])
    else:
        # get package version for each package in *args
        for arg in args:
            # Make yum do the pattern matching
            a = yb.pkgSack.returnPackages(patterns=[arg], ignore_case=False)
            # make sure there is an a
            if len(a) > 0:
                arg = a[0].name
            # use the name from yum to do an rpm lookup
            for h in ts.dbMatch('name', arg):
                pkgs[h['name']] = '-'.join([h['version'], h['release']])

    return pkgs


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    yb = yum.YumBase()
    yb.cleanMetadata()
    return True


def clean_metadata():
    '''
    Cleans local yum metadata.

    CLI Example::

        salt '*' pkg.clean_metadata
    '''
    return refresh_db()


def install(name=None, refresh=False, repo='', skip_verify=False, pkgs=None,
            sources=None, **kwargs):
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
        Whether or not to clean the yum database before executing.

    repo
        Specify a package repository to install from.
        (e.g., ``yum --enablerepo=somerepo``)

    skip_verify
        Skip the GPG verification check. (e.g., ``--nogpgcheck``)


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example::
            salt '*' pkg.install pkgs='["foo","bar"]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::
            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"},{"bar": "salt://bar.rpm"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>']}
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or refresh == 'True':
        refresh_db()

    pkg_params,pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                 pkgs,
                                                                 sources)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    old = list_pkgs()

    yb = yum.YumBase()
    setattr(yb.conf, 'assumeyes', True)
    setattr(yb.conf, 'gpgcheck', not skip_verify)

    if repo:
        log.info('Enabling repo \'{0}\''.format(repo))
        yb.repos.enableRepo(repo)

    for target in pkg_params:
        try:
            if pkg_type == 'file':
                log.info(
                    'Selecting "{0}" for local installation'.format(target)
                )
                a = yb.installLocal(target)
                # if yum didn't install anything, maybe its a downgrade?
                log.debug('Added {0} transactions'.format(len(a)))
                if len(a) == 0 and target not in old.keys():
                    log.info('Upgrade failed, trying local downgrade')
                    a = yb.downgradeLocal(target)
            else:
                log.info('Selecting "{0}" for installation'.format(target))
                # Changed to pattern to allow specific package versions
                a = yb.install(pattern=target)
                # if yum didn't install anything, maybe its a downgrade?
                log.debug('Added {0} transactions'.format(len(a)))
                if len(a) == 0 and target not in old.keys():
                    log.info('Upgrade failed, trying downgrade')
                    a = yb.downgrade(pattern=target)
        except Exception:
            log.exception('Package "{0}" failed to install'.format(target))
    # Resolve Deps before attempting install.  This needs to be improved by
    # also tracking any deps that may get upgraded/installed during this
    # process. For now only the version of the package(s) you request be
    # installed is tracked.
    log.info('Resolving dependencies')
    yb.resolveDeps()
    log.info('Processing transaction')
    yumlogger = _YumErrorLogger()
    yb.processTransaction(rpmDisplay=yumlogger)
    yumlogger.log_accumulated_errors()

    yb.closeRpmDB()

    new = list_pkgs()

    return __salt__['pkg_resource.find_changes'](old,new)


def upgrade():
    '''
    Run a full system upgrade, a yum upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''

    yb = yum.YumBase()
    setattr(yb.conf, 'assumeyes', True)

    old = list_pkgs()

    # ideally we would look in the yum transaction and get info on all the
    # packages that are going to be upgraded and only look up old/new version
    # info on those packages.
    yb.update()
    log.info('Resolving dependencies')
    yb.resolveDeps()
    yumlogger = _YumErrorLogger()
    log.info('Processing transaction')
    yb.processTransaction(rpmDisplay=yumlogger)
    yumlogger.log_accumulated_errors()
    yb.closeRpmDB()

    new = list_pkgs()
    return _compare_versions(old, new)


def remove(pkgs):
    '''
    Removes packages with yum remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package,package,package>
    '''

    yb = yum.YumBase()
    setattr(yb.conf, 'assumeyes', True)
    pkgs = pkgs.split(',')
    old = list_pkgs(*pkgs)

    # same comments as in upgrade for remove.
    for pkg in pkgs:
        yb.remove(name=pkg)

    log.info('Resolving dependencies')
    yb.resolveDeps()
    yumlogger = _YumErrorLogger()
    log.info('Processing transaction')
    yb.processTransaction(rpmDisplay=yumlogger)
    yumlogger.log_accumulated_errors()
    yb.closeRpmDB()

    new = list_pkgs(*pkgs)

    return _list_removed(old, new)


def purge(pkgs):
    '''
    Yum does not have a purge, this function calls remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(pkgs)


def verify():
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    CLI Example::

        salt '*' pkg.verify
    '''
    ftypes = {'c': 'config',
              'd': 'doc',
              'g': 'ghost',
              'l': 'license',
              'r': 'readme'}
    ret = {}
    cmd = 'rpm -Va'
    for line in __salt__['cmd.run'](cmd).split('\n'):
        fdict = {'mismatch': []}
        if 'missing' in line:
            line = ' ' + line
            fdict['missing'] = True
            del(fdict['mismatch'])
        fname = line[13:]
        if line[11:12] in ftypes:
            fdict['type'] = ftypes[line[11:12]]
        if line[0:1] == 'S':
            fdict['mismatch'].append('size')
        if line[1:2] == 'M':
            fdict['mismatch'].append('mode')
        if line[2:3] == '5':
            fdict['mismatch'].append('md5sum')
        if line[3:4] == 'D':
            fdict['mismatch'].append('device major/minor number')
        if line[4:5] == 'L':
            fdict['mismatch'].append('readlink path')
        if line[5:6] == 'U':
            fdict['mismatch'].append('user')
        if line[6:7] == 'G':
            fdict['mismatch'].append('group')
        if line[7:8] == 'T':
            fdict['mismatch'].append('mtime')
        if line[8:9] == 'P':
            fdict['mismatch'].append('capabilities')
        ret[fname] = fdict
    return ret


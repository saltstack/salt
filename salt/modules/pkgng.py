# -*- coding: utf-8 -*-
'''
Support for pkgng
'''

# Import python libs
import os

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Pkgng module load on FreeBSD only.
    '''
    if __grains__['os'] == 'FreeBSD':
        return 'pkgng'
    else:
        return False


def parse_config(file_name='/usr/local/etc/pkg.conf'):
    '''
    Return dict of uncommented global variables.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.parse_config

    ``NOTE:`` not working properly right now
    '''
    ret = {}
    if not os.path.isfile(file_name):
        return 'Unable to find {0} on file system'.format(file_name)

    with salt.utils.fopen(file_name) as ifile:
        for line in ifile:
            if line.startswith('#') or line.startswith('\n'):
                pass
            else:
                key, value = line.split('\t')
                ret[key] = value
    ret['config_file'] = file_name
    return ret


def version():
    '''
    Displays the current version of pkg

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.version
    '''

    cmd = 'pkg -v'
    return __salt__['cmd.run'](cmd)


def latest_version(pkg_name, **kwargs):
    '''
    The available version of the package in the repository

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.latest_version <package name>
    '''

    kwargs.pop('refresh', True)

    cmd = 'pkg info {0}'.format(pkg_name)
    out = __salt__['cmd.run'](cmd).split()
    return out[0]

# available_version is being deprecated
available_version = latest_version


def update_package_site(new_url):
    '''
    Updates remote package repo URL, PACKAGESITE var to be exact.

    Must be using http://, ftp://, or https// protos

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.update_package_site http://127.0.0.1/
    '''
    config_file = parse_config()['config_file']
    __salt__['file.sed'](
        config_file, 'PACKAGESITE.*', 'PACKAGESITE\t : {0}'.format(new_url)
    )

    # add change return later
    return True


def stats(local=False, remote=False):
    '''
    Return pkgng stats.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.stats

    local
        Display stats only for the local package database.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.stats local=True

    remote
        Display stats only for the remote package database(s).

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.stats remote=True
    '''

    opts = ''
    if local:
        opts += 'l'
    if remote:
        opts += 'r'
    if opts:
        opts = '-' + opts

    cmd = 'pkg stats {0}'.format(opts)
    res = __salt__['cmd.run'](cmd)
    res = [x.strip("\t") for x in res.split("\n")]
    return res


def backup(file_name):
    '''
    Export installed packages into yaml+mtree file

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.backup /tmp/pkg
    '''
    cmd = 'pkg backup -d {0}'.format(file_name)
    res = __salt__['cmd.run'](cmd)
    return res.split('...')[1]


def restore(file_name):
    '''
    Reads archive created by pkg backup -d and recreates the database.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.restore /tmp/pkg
    '''
    cmd = 'pkg backup -r {0}'.format(file_name)
    res = __salt__['cmd.run'](cmd)
    return res


def add(pkg_path):
    '''
    Install a package from either a local source or remote one

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.add /tmp/package.txz
    '''
    if not os.path.isfile(pkg_path) or pkg_path.split(".")[1] != "txz":
        return '{0} could not be found or is not  a *.txz \
            format'.format(pkg_path)
    cmd = 'pkg add {0}'.format(pkg_path)
    res = __salt__['cmd.run'](cmd)
    return res


def audit():
    '''
    Audits installed packages against known vulnerabilities

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.audit
    '''

    cmd = 'pkg audit -F'
    return __salt__['cmd.run'](cmd)


def install(pkg_name,
            orphan=False,
            force=False,
            glob=False,
            local=False,
            dryrun=False,
            quiet=False,
            require=False,
            reponame=None,
            regex=False,
            pcre=False):
    '''
    Install package from repositories

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.install <package name>

    orphan
        Mark the installed package as orphan. Will be automatically removed
        if no other packages depend on them. For more information please
        refer to pkg-autoremove(8).

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> orphan=True

    force
        Force the reinstallation of the package if already installed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> force=True

    glob
        Treat the package names as shell glob patterns.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> glob=True

    local
        Skip updating the repository catalogues with pkg-update(8). Use the
        locally cached copies only.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> local=True

    dryrun
        Dru-run mode. The list of changes to packages is always printed,
        but no changes are actually made.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> dryrun=True

    quiet
        Force quiet output, except when dryrun is used, where pkg install
        will always show packages to be installed, upgraded or deleted.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> quiet=True

    require
        When used with force, reinstalls any packages that require the
        given package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> require=True force=True

    reponame
        In multi-repo mode, override the pkg.conf ordering and only attempt
        to download packages from the named repository.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <package name> reponame=repo

    regex
        Treat the package names as a regular expression

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <regular expression> regex=True

    pcre
        Treat the package names as extended regular expressions.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.install <extended regular expression> pcre=True
    '''

    opts = ''
    repo_opts = ''
    if orphan:
        opts += 'A'
    if force:
        opts += 'f'
    if glob:
        opts += 'g'
    if local:
        opts += 'l'
    if dryrun:
        opts += 'n'
    if not dryrun:
        opts += 'y'
    if quiet:
        opts += 'q'
    if require:
        opts += 'R'
    if reponame:
        repo_opts += 'r {0}'.format(reponame)
    if regex:
        opts += 'x'
    if pcre:
        opts += 'X'
    if opts:
        opts = '-' + opts
    if repo_opts:
        repo_opts = '-' + repo_opts

    cmd = 'pkg install {0} {1} {2}'.format(repo_opts, opts, pkg_name)
    return __salt__['cmd.run'](cmd)


def delete(pkg_name,
           all_installed=False,
           force=False,
           glob=False,
           dryrun=False,
           recurse=False,
           regex=False,
           pcre=False):
    '''
    Delete a package from the database and system

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.delete <package name>

    all_installed
        Deletes all installed packages from the system and empties the
        database. USE WITH CAUTION!

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.delete all all_installed=True force=True

    force
        Forces packages to be removed despite leaving unresolved
        dependencies.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.delete <package name> force=True

    glob
        Treat the package names as shell glob patterns.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.delete <package name> glob=True

    dryrun
        Dry run mode. The list of packages to delete is always printed, but
        no packages are actually deleted.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.delete <package name> dryrun=True

    recurse
        Delete all packages that require the listed package as well.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.delete <package name> recurse=True

    regex
        Treat the package names as regular expressions.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.delete <regular expression> regex=True

    pcre
        Treat the package names as extended regular expressions.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.delete <extended regular expression> pcre=True
    '''

    opts = ''
    if all_installed:
        opts += 'a'
    if force:
        opts += 'f'
    if glob:
        opts += 'g'
    if dryrun:
        opts += 'n'
    if not dryrun:
        opts += 'y'
    if recurse:
        opts += 'R'
    if regex:
        opts += 'x'
    if pcre:
        opts += 'X'
    if opts:
        opts = '-' + opts

    cmd = 'pkg delete {0} {1}'.format(opts, pkg_name)
    return __salt__['cmd.run'](cmd)


def info(pkg_name=None):
    '''
    Returns info on packages installed on system

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.info
        salt '*' pkgng.info sudo
    '''
    if pkg_name:
        cmd = 'pkg info {0}'.format(pkg_name)
    else:
        cmd = 'pkg info'

    res = __salt__['cmd.run'](cmd)

    if not pkg_name:
        res = res.splitlines()

    return res


def update(force=False):
    '''
    Refresh PACKAGESITE contents

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.update

    force
        Force a full download of the repository catalogue without regard to the
        respective ages of the local and remote copies of the catalogue.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.update force=True
    '''
    opts = ''
    if force:
        opts += 'f'
    if opts:
        opts = '-' + opts

    cmd = 'pkg update {0}'.format(opts)
    return __salt__['cmd.run'](cmd)


def upgrade(force=False, local=False, dryrun=False):
    '''
    Upgrade all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.upgrade

    force
        Force reinstalling/upgrading the whole set of packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.upgrade force=True

    local
        Skip updating the repository catalogues with ``pkg-update(8)``. Use the
        local cache only.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.update local=True

    dryrun
        Dry-run mode: show what packages have updates available, but do not
        perform any upgrades. Repository catalogues will be updated as usual
        unless the local option is also given.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.update dryrun=True
    '''
    opts = ''
    if force:
        opts += 'f'
    if local:
        opts += 'L'
    if dryrun:
        opts += 'n'
    if not dryrun:
        opts += 'y'
    if opts:
        opts = '-' + opts

    cmd = 'pkg upgrade {0}'.format(opts)
    return __salt__['cmd.run'](cmd)


def clean():
    '''
    Cleans the local cache of fetched remote packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.clean
    '''

    cmd = 'pkg clean'
    return __salt__['cmd.run'](cmd)


def autoremove(dryrun=False):
    '''
    Delete packages which were automatically installed as dependencies and are
    not required anymore.

    dryrun
        Dry-run mode. The list of changes to packages is always printed,
        but no changes are actually made.

    CLI Example:

    .. code-block:: bash

         salt '*' pkgng.autoremove
         salt '*' pkgng.autoremove dryrun=True
    '''

    opts = ''
    if dryrun:
        opts += 'n'
    else:
        opts += 'y'
    if opts:
        opts = '-' + opts

    cmd = 'pkg autoremove {0}'.format(opts)
    return __salt__['cmd.run'](cmd)


def check(depends=False, recompute=False, checksum=False):
    '''
    Sanity checks installed packages

        depends
            Check for and install missing dependencies.

            CLI Example:

            .. code-block:: bash

                salt '*' pkgng.check recompute=True

        recompute
            Recompute sizes and checksums of installed packages.

            CLI Example:

            .. code-block:: bash

                salt '*' pkgng.check depends=True

        checksum
            Find invalid checksums for installed packages.

            CLI Example:

            .. code-block:: bash

                salt '*' pkgng.check checksum=True
    '''

    opts = ''
    if depends:
        opts += 'dy'
    if recompute:
        opts += 'r'
    if checksum:
        opts += 's'
    if opts:
        opts = '-' + opts

    cmd = 'pkg check {0}'.format(opts)
    return __salt__['cmd.run'](cmd)


def which(file_name, origin=False, quiet=False):
    '''
    Displays which package installed a specific file

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.which <file name>

    origin
        Shows the origin of the package instead of name-version.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.which <file name> origin=True

    quiet
        Quiet output.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.which <file name> quiet=True
    '''

    opts = ''
    if quiet:
        opts += 'q'
    if origin:
        opts += 'o'
    if opts:
        opts = '-' + opts

    cmd = 'pkg which {0} {1}'.format(opts, file_name)
    return __salt__['cmd.run'](cmd)


def search(pkg_name,
           exact=False,
           glob=False,
           regex=False,
           pcre=False,
           comment=False,
           desc=False,
           full=False,
           depends=False,
           size=False,
           quiet=False,
           origin=False,
           prefix=False):
    '''
    Searches in remote package repositories

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.search pattern

    exact
        Treat pattern as exact pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern exact=True

    glob
        Treat pattern as a shell glob pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern glob=True

    regex
        Treat pattern as a regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern regex=True

    pcre
        Treat pattern as an extended regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern pcre=True

    comment
        Search for pattern in the package comment one-line description.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern comment=True

    desc
        Search for pattern in the package description.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern desc=True

    full
        Displays full information about the matching packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern full=True

    depends
        Displays the dependencies of pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern depends=True

    size
        Displays the size of the package

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern size=True

    quiet
        Be quiet. Prints only the requested information without displaying
        many hints.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern quiet=True

    origin
        Displays pattern origin.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern origin=True

    prefix
        Displays the installation prefix for each package matching pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.search pattern prefix=True
    '''

    opts = ''
    if exact:
        opts += 'e'
    if glob:
        opts += 'g'
    if regex:
        opts += 'x'
    if pcre:
        opts += 'X'
    if comment:
        opts += 'c'
    if desc:
        opts += 'D'
    if full:
        opts += 'f'
    if depends:
        opts += 'd'
    if size:
        opts += 's'
    if quiet:
        opts += 'q'
    if origin:
        opts += 'o'
    if prefix:
        opts += 'p'
    if opts:
        opts = '-' + opts

    cmd = 'pkg search {0} {1}'.format(opts, pkg_name)
    return __salt__['cmd.run'](cmd)


def fetch(pkg_name,
          all=False,
          quiet=False,
          reponame=None,
          glob=True,
          regex=False,
          pcre=False,
          local=False,
          depends=False):
    '''
    Fetches remote packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.fetch <package name>

    all
        Fetch all packages.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <package name> all=True

    quiet
        Quiet mode. Show less output.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <package name> quiet=True

    reponame
        Fetches packages from the given reponame if multiple repo support
        is enabled. See pkg.conf(5).

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <package name> reponame=repo

    glob
        Treat pkg_name as a shell glob pattern.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <package name> glob=True

    regex
        Treat pkg_name as a regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <regular expression> regex=True

    pcre
        Treat pkg_name is an extended regular expression.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <extended regular expression> pcre=True

    local
        Skip updating the repository catalogues with pkg-update(8). Use the
        local cache only.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <package name> local=True

    depends
        Fetch the package and its dependencies as well.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.fetch <package name> depends=True
    '''

    opts = ''
    repo_opts = ''
    if all:
        opts += 'a'
    if quiet:
        opts += 'q'
    if reponame:
        repo_opts += 'r {0}'.format(reponame)
    if glob:
        opts += 'g'
    if regex:
        opts += 'x'
    if pcre:
        opts += 'X'
    if local:
        opts += 'L'
    if depends:
        opts += 'd'
    if opts:
        opts = '-' + opts
    if repo_opts:
        opts = '-' + repo_opts

    cmd = 'pkg fetch -y {0} {1} {2}'.format(repo_opts, opts, pkg_name)
    return __salt__['cmd.run'](cmd)


def updating(pkg_name, filedate=None, filename=None):
    ''''
    Displays UPDATING entries of software packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkgng.updating foo

    filedate
        Only entries newer than date are shown. Use a YYYYMMDD date format.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.updating foo filedate=20130101

    filename
        Defines an alternative location of the UPDATING file.

        CLI Example:

        .. code-block:: bash

            salt '*' pkgng.updating foo filename=/tmp/UPDATING
    '''

    opts = ''
    if filedate:
        opts += 'd {0}'.format(filedate)
    if filename:
        opts += 'f {0}'.format(filename)
    if opts:
        opts = '-' + opts

    cmd = 'pkg updating {0} {1}'.format(opts, pkg_name)
    return __salt__['cmd.run'](cmd)

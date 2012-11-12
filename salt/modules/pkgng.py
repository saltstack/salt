'''
Support for pkgng
'''

import os 

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

    CLI Example::

        salt '*' pkgng.parse_config
        *NOTE* not working right
    '''
    ret = {}
    l = []
    if not os.path.isfile(file_name):
        return 'Unable to find {0} on file system'.format(file_name)

    with open(file_name) as f:
        for line in f.readlines():
            if line.startswith("#") or line.startswith("\n"):
                pass
            else:
                k, v = line.split('\t')
                ret[k] = v
                l.append(line)
    ret['config_file'] = file_name
    return ret


def version():
    '''
    Displays the current version of pkg
    
    CLI Example::
        salt '*' pkgng.version
    '''

    cmd = 'pkg -v'
    return __salt__['cmd.run'](cmd)


def update_package_site(new_url):
    '''
    Updates remote package repo url, PACKAGESITE var to be exact.

    Must be using http://, ftp://, or https// protos

    CLI Example::
        salt '*' pkgng.update_package_site http://127.0.0.1/
    '''
    config_file = parse_config()['config_file']
    __salt__['file.sed'](config_file,'PACKAGESITE.*', \
        'PACKAGESITE\t : {0}'.format(new_url))

    # add change return later
    return True


def stats():
    '''
    Return pkgng stats.

    CLI Example::
        salt '*' pkgng.stats
    '''

    cmd = 'pkg stats'
    res = __salt__['cmd.run'](cmd)
    res = [ x.strip("\t") for x in res.split("\n") ]
    return res


def backup(file_name):
    '''
    Export installed packages into yaml+mtree file

    CLI Example::
        salt '*' pkgng.backup /tmp/pkg
    '''
    cmd = 'pkg backup -d {0}'.format(file_name)
    res = __salt__['cmd.run'](cmd)
    return res.split('...')[1]


def restore(file_name):
    '''
    Reads archive created by pkg backup -d and recreates the database.
    '''
    cmd = 'pkg backup -r {0}'.format(file_name)
    res = __salt__['cmd.run'](cmd)
    return res


def add(pkg_path):
    '''
    Install a package from either a local source or remote one

    CLI Example::
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
    
    CLI Example::
        salt '*' pkgng.audit
    '''

    cmd = 'pkg audit -F'
    return __salt__['cmd.run'](cmd)


def install(pkg_name):
    '''
    Install package from repositories
    
    CLI Example::
        salt '*' pkgng.install bash
    '''

    cmd = 'pkg install -y {0}'.format(pkg_name)
    return __salt__['cmd.run'](cm)


def delete(pkg_name):
    '''
    Delete a package from the database and system
    
    CLI Example::
        salt '*' pkgng.delete bash
    '''

    cmd = 'pkg delete -y {0}'.format(pkg_name)
    return __salt__['cmd.run'](cmd)


def info(pkg=None):
    '''
    Returns info on packages installed on system

    CLI Example::
        salt '*' pkgng.info

        For individual info

        salt '*' pkgng.info sudo
    '''
    if pkg:
        cmd = 'pkg info {0}'.format(pkg)
    else:
        cmd = 'pkg info'

    res = __salt__['cmd.run'](cmd)

    if not pkg:
        res = res.splitlines()

    return res


def update():
    '''
    Refresh PACKAGESITE contents

    CLI Example::
        salt '*' pkgng.update
    '''

    cmd = 'pkg update'
    return __salt__['cmd.run'](cmd)


def upgrade():
    '''
    Upgrade all packages
    
    CLI Example::
        salt '*' pkgng.upgrade
    '''

    cmd = 'pkg upgrade -y'
    return __salt__['cmd.run'](cmd)

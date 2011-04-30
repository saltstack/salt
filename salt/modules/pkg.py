'''
Top level package command wrapper, used to translate the os detected by the
grains to the correct package manager
'''
import salt.modules.pacman
import salt.modules.yum
#import salt.modules.apt

grainmap = {
           'Archlinux': 'pacman',
           'Fedora': 'yum',
           'RedHat': 'yum',
           #'Debian': 'apt',
           #'Ubuntu': 'apt',
          }

def _map_cmd(cmd, args=[]):
    '''
    Map the passed data to the correct function
    '''
    if args:
        args = [args]
    pro = grainmap[__grains__['os']]
    return getattr(getattr(salt.modules, pro), cmd)(*args)

def list_pkgs():
    '''
    List installed packages

    CLI Example:
    salt '*' pkg.list_pkgs
    '''
    return _map_cmd('list_pkgs')

def refresh_db():
    '''
    Refresh the package database

    CLI Example:
    salt '*' pkg.refresh_db
    '''
    return _map_cmd('refresh_db')

def install(pkg_name):
    '''
    Install the desired package

    CLI Example:
    salt '*' pkg.install <package name>
    '''
    return _map_cmd('install', pkg_name)

def upgrade():
    '''
    Upgrade the entire system

    CLI Example:
    salt '*' pkg.upgrade
    '''
    return _map_cmd('upgrade')

def remove(pkg_name):
    '''
    Remove the desired package

    CLI Example:
    salt '*' pkg.remove <package name>
    '''
    return _map_cmd('remove', pkg_name)

def purge(pkg_name):
    '''
    Purge the desired package

    CLI Example:
    salt '*' pkg.purge <package name>
    '''
    return _map_cmd('purge', pkg_name)

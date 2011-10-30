'''
Support for apt
'''

import subprocess

def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    
    return 'pkg' if __grains__['os'] == 'Debian' else False

def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example:
    salt '*' pkg.available_version <package name>
    '''
    version = ''
    cmd = 'apt-cache show ' + name + ' | grep Version'
    
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]
    
    version_list = out.split()
    if len(version_list) >= 2:
        version = version_list[1]
    
    return version

def version(name):
    '''
    Returns a string representing the package version or an empty string if not
    installed

    CLI Example:
    salt '*' pkg.version <package name>
    '''
    pkgs = list_pkgs(name)
    if pkgs.has_key(name):
        return pkgs[name]
    else:
        return ''

def refresh_db():
    '''
    Updates the apt database to latest packages based upon repositories
    
    Returns a dict: {'<database name>': Bool}
    
    CLI Example:
    salt '*' pkg.refresh_db    
    '''
    cmd = 'apt-get update'
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    
    servers = {}
    for line in out:
        cols = line.split()
        if not len(cols):
            continue
        ident = " ".join(cols[1:4])
        if cols[0].count('Get'):
            servers[ident] = True
        else:
            servers[ident]  = False
    
    return servers
    
def install(pkg, refresh=False):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    if(refresh):
        refresh_db()
    
    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'apt-get -y install ' + pkg
    subprocess.call(cmd, shell=True)
    new_pkgs = list_pkgs()
    
    for pkg in new_pkgs:
        if old_pkgs.has_key(pkg):
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
    Remove a single package via apt-get remove
    
    Return a list containing the names of the removed packages:
    
    CLI Example:
    salt '*' pkg.remove <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()
    
    cmd = 'apt-get -y remove ' + pkg
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    
    for pkg in old_pkgs:
        if not new_pkgs.has_key(pkg):
            ret_pkgs.append(pkg)
    
    return ret_pkgs

def purge(pkg):
    '''
    Remove a package via apt-get along with all configuration files and
    unused dependencies as determined by apt-get autoremove
    
    Returns a list containing the names of the removed packages
    
    CLI Example:
    salt '*' pkg.purge <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()
    
    # Remove inital package
    purge_cmd = 'apt-get -y purge ' + pkg
    subprocess.call(purge_cmd, shell=True)
    
    # Remove any dependencies that are no longer needed
    autoremove_cmd = 'apt-get -y autoremove'
    subprocess.call(purge_cmd, shell=True)
    
    new = list_pkgs()
    
    for pkg in old_pkgs:
        if not new_pkgs.has_key(pkg):
            ret_pkgs.append(pkg)
    
    return ret_pkgs
    

def upgrade(refresh=True):
    '''
    Upgrades all packages via apt-get dist-upgrade

    Returns a list of dicts containing the package names, and the new and old
    versions::

        [
            {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>']
            }',
            ...
        ]

    CLI Example::

        salt '*' pkg.upgrade
    '''
    
    if(update_repos):
        refresh_db()
    
    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'apt-get -y dist-upgrade'
    subprocess.call(cmd, shell=True)
    new_pkgs = list_pkgs()
    
    for pkg in new_pkgs:
        if old_pkgs.has_key(pkg):
            if old_pkgs[pkg] == new_pkgs[pkg]:
                continue
            else:
                ret_pkgs[pkg] = {'old': old_pkgs[pkg],
                             'new': new_pkgs[pkg]}
        else:
            ret_pkgs[pkg] = {'old': '',
                         'new': new_pkgs[pkg]}
    
    return ret_pkgs


def list_pkgs(regex_string=""):
    '''
    List the packages currently installed in a dict:
    {'<package_name>': '<version>'}

    CLI Example:
    salt '*' pkg.list_pkgs
    '''
    ret = {}
    cmd = 'dpkg --list ' + regex_string
    
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    
    for line in out:
        cols = line.split()
        if len(cols) and cols[0].count('ii'):
            ret[cols[1]] = cols[2]
    
    return ret

'''
Support for apt
'''

import subprocess

def __virtual__():
    '''
    Confine this module is on a Debian based system
    '''
    
    return 'pkg' if __grains__['os'] == 'Debian' else False

def update():
    '''
    Updates the apt database to latest packages based upon repositories
    
    Returns True/False based upon successful completion of update
    '''
    cmd = 'apt-get update'
    result = subprocess.call(cmd, shell=True)
    
    return result == 0
    

def install(pkg, update_repos=False):
    '''
    Install the passed package
    
    Return a dict containing the new package names and versions:
    {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}
    '''
    if(update_repos):
        update()
    
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

def dist_upgrade(update_repos=False):
    '''
    Upgrades all packages via apt-get dist-upgrade
    
    Returns a list of dicts containing the package names, and the new and old versions:
    [
        {'<package>':  {'old': '<old-version>',
                      'new': '<new-version>']
        }',
        ...
    ]
    '''
    
    if(update_repos):
        update()
    
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


def list_pkgs():
    '''
    List the packages currently installed in a dict:
    {'<package_name>': '<version>'}

    CLI Example:
    salt '*' pkg.list_pkgs
    '''
    ret = {}
    cmd = 'dpkg --list'
    
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    
    for line in out:
        cols = line.split()
        if len(cols) and cols[0].count('ii'):
            ret[cols[1]] = cols[2]
    
    return ret

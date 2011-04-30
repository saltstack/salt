'''
Support for YUM
'''

import subprocess

def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    # We don't need to support pre-yum OSes because they don't support python 2.6
    dists = 'CentOS Scientific RedHat Fedora'
    return 'pkg' if dists.count(__grains__['os']) else False

def _list_removed(old, new):
    '''
    List the pachages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if not new.has_key(pkg):
            pkgs.append(pkg)
    return pkgs

def list_pkgs():
    '''
    List the packages currently installed in a dict:
    {'<package_name>': '<version>'}

    CLI Example:
    salt '*' pkg.list_pkgs
    '''
    cmd = "rpm -qa --qf '%{NAME}\\t%{VERSION}-%{RELEASE}\\n'"
    ret = {}
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        comps = line.split()
        ret[comps[0]] = comps[1]
    return ret

def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example:
    salt '*' pkg.refresh_db
    '''
    cmd = 'yum clean dbcache'
    subprocess.call(cmd, shell=True)
    return True

def install(pkg, refresh=False):
    '''
    Install the passed package, add refresh=True to clean out the yum database
    before executing

    Return a dict containing the new package names and versions:
    {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example:
    salt '*' pkg.install <package name>
    '''
    old = list_pkgs()
    cmd = 'yum -y install ' + pkg
    if refresh:
        refresh_db()
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    pkgs = {}
    for npkg in new:
        if old.has_key(npkg):
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    return pkgs

def upgrade():
    '''
    Run a full system upgrade, a yum upgrade

    Return a dict containing the new package names and versions:
    {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example:
    salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    cmd = 'yum -y upgrade'
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    pkgs = {}
    for npkg in new:
        if old.has_key(npkg):
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    return pkgs
    
def remove(pkg):
    '''
    Remove a single package with yum remove

    Return a list containing the removed packages:
    
    CLI Example:
    salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'yum -y remove ' + pkg
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    return _list_removed(old, new)

def purge(pkg):
    '''
    Yum does not have a purge, this function calls remove

    Return a list containing the removed packages:
    
    CLI Example:
    salt '*' pkg.purge <package name>

    '''
    return remove(pkg)

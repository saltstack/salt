'''
Support for Portage
'''

try:
    import subprocess
    import portage
except ImportError:
    None

def __virtual__():
    '''
    Confirm this module is on a Gentoo based system
    '''
    return 'pkg' if __grains__['os'] == 'Gentoo' else False

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
    return str(cpv[len(_cpv_to_name(cpv)+'-'):])

def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example:
    salt '*' pkg.available_version <package name>
    '''
    return _cpv_to_version(_porttree().dep_bestmatch(name))

def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example:
    salt '*' pkg.version <package name>
    '''
    return _cpv_to_version(_vartree().dep_bestmatch(name))

def list_pkgs():
    '''
    List the packages currently installed in a dict:
    {'<package_name>': '<version>'}

    CLI Example:
    salt '*' pkg.list_pkgs
    '''
    ret = {}
    pkgs = _vartree().dbapi.cpv_all()
    for cpv in pkgs:
        ret[_cpv_to_name(cpv)] = _cpv_to_version(cpv)
    return ret

def refresh_db():
    '''
    Updates the portage tree (emerge --sync)

    CLI Example:
    salt '*' pkg.refresh_db
    '''
    if subprocess.call('emerge --sync --quiet', shell=True):
        return False
    else:
        return True

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
    cmd = 'emerge --quiet ' + pkg
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

def update(pkg, refresh=False):
    '''
    Updates the passed package (emerge --update package)

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.update <package name>
    '''
    if(refresh):
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'emerge --update --quiet ' + pkg
    subprocess.call(cmd, shell=True)
#    emerge_main(['--quiet', '--update', pkg])
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

def upgrade(refresh=False):
    '''
    Run a full system upgrade (emerge --update world)

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    if(refresh):
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    subprocess.call('emerge --update --quiet world', shell=True)
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
    Remove a single package via emerge --unmerge
    
    Return a list containing the names of the removed packages:
    
    CLI Example:
    salt '*' pkg.remove <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()
    
    cmd = 'emerge --unmerge --quiet --quiet-unmerge-warn ' + pkg
    subprocess.call(cmd, shell=True)
    new_pkgs = list_pkgs()
    
    for pkg in old_pkgs:
        if not new_pkgs.has_key(pkg):
            ret_pkgs.append(pkg)
    
    return ret_pkgs

def purge(pkg):
    '''
    Portage does not have a purge, this function calls remove

    Return a list containing the removed packages:

    CLI Example:
    salt '*' pkg.purge <package name>

    '''
    return remove(pkg)

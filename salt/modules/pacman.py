'''
A module to wrap pacman calls, since Arch is the best :)
'''
import subprocess

def list_pkgs():
    '''
    List the packages currently installed in a dict:
    {'<package_name>': '<version>'}
    '''
    cmd = 'pacman -Q'
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
    Just run a pacman -Sy, return a dict:
    {'<database name>': Bool}
    '''
    cmd = 'pacman -Sy'
    ret = {}
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if line.strip().startswith('::'):
            continue
        if not line:
            continue
        key = line.strip().split()[0]
        if line.count('is up to date'):
            ret[key] = False
        elif line.count('downloading'):
            ret[key] = True
    return ret

def install(pkg, refresh=False):
    '''
    Install the passed package, add refresh=True to install with an -Sy

    Return a dict containing the new package names and versions:
    {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}
    '''
    old = list_pkgs()
    cmd = 'pacman -S --noprogressbar --noconfirm ' + pkg
    if refresh:
        cmd = 'pacman -Sy --noprogressbar --noconfirm ' + pkg
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
    Run a full system upgrade, a pacman -Syu

    Return a dict containing the new package names and versions:
    {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}
    '''
    old = list_pkgs()
    cmd = 'pacman -Syu --noprogressbar --noconfirm '
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
    
    

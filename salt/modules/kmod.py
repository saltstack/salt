'''
Module to manage Linux kernel modules
'''

# Import python libs
import os

def __virtual__():
    '''
    Only runs on Linux systems
    '''
    return 'kmod' if __grains__['kernel'] == 'Linux' else False

def _new_mods(pre_mods, post_mods):
    '''
    Return a list of the new modules, pass an lsmod dict before running
    modprobe and one after modprobe has run
    '''
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod['module'])
    for mod in post_mods:
        post.add(mod['module'])
    return list(post.difference(pre))

def _rm_mods(pre_mods, post_mods):
    '''
    Return a list of the new modules, pass an lsmod dict before running
    modprobe and one after modprobe has run
    '''
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod['module'])
    for mod in post_mods:
        post.add(mod['module'])
    return list(pre.difference(post))

def available():
    '''
    Return a list of all available kernel modules

    CLI Example:
    salt '*' kmod.available
    '''
    ret = []
    for path in __salt__['cmd.run']('modprobe -l').split('\n'):
        bpath = os.path.basename(path)
        comps = bpath.split('.')
        if comps.count('ko'):
            # This is a kernel module, return it without the .ko extension
            ret.append('.'.join(comps[:comps.index('ko')]))
    return ret

def check_available(mod):
    '''
    Check to see if the speciified kernel module is available

    CLI Example:
    salt '*' kmod.check_available kvm
    '''
    if available().count(mod):
        # the module is available, return True
        return True
    return False

def lsmod():
    '''
    Return a dict containing information about currently loaded modules

    CLI Example:
    salt '*' kmod.lsmod
    '''
    ret = []
    for line in __salt__['cmd.run']('lsmod').split('\n'):
        comps = line.split()
        if not len(comps) > 2:
            continue
        if comps[0] == 'Module':
            continue
        mdat = {}
        mdat['module'] = comps[0]
        mdat['size'] = comps[1]
        mdat['depcount'] = comps[2]
        if len(comps) > 3:
            mdat['deps'] = comps[3].split(',')
        else:
            mdat['deps'] = []
        ret.append(mdat)
    return ret

def load(mod):
    '''
    Load the specified kernel module

    CLI Example:
    salt '*' kmod.load kvm
    '''
    pre_mods = lsmod()
    data = __salt__['cmd.run_all']('modprobe {0}'.format(mod))
    post_mods = lsmod()
    return _new_mods(pre_mods, post_mods)

def remove(mod):
    '''
    Remove the specified kernel module

    CLI Example:
    salt '*' kmod.remove kvm
    '''
    pre_mods = lsmod()
    data = __salt__['cmd.run_all']('modprobe -r {0}'.format(mod))
    post_mods = lsmod()
    return _rm_mods(pre_mods, post_mods)

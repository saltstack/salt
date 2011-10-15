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
    ret = {}
    for line in __salt__['cmd.run']('lsmod').split('\n'):
        comps = line.split()
        ret['module'] = comps[0]
        ret['size'] = comps[1]
        ret['depcount'] = comps[2]
        ret['deps'] = comps[3].split(',')
    return ret

def load(mod):
    '''
    Load the specified kernel module

    CLI Example:
    salt '*' kmod.load kvm
    '''
    data = __salt__['cmd.run_all']('modprobe {0}'.format(mod))
    if data['retcode']:
        # Failed to load, return False
        return False
    return True

def remove(mod):
    '''
    Load the specified kernel module

    CLI Example:
    salt '*' kmod.remove kvm
    '''
    data = __salt__['cmd.run_all']('modprobe -r {0}'.format(mod))
    if data['retcode']:
        # Failed to load, return False
        return False
    return True

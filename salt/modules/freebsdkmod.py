# -*- coding: utf-8 -*-
'''
Module to manage FreeBSD kernel modules
'''

# Import python libs
import os

# Define the module's virtual name
__virtualname__ = 'kmod'


def __virtual__():
    '''
    Only runs on FreeBSD systems
    '''
    return __virtualname__ if __grains__['kernel'] == 'FreeBSD' else False


def _new_mods(pre_mods, post_mods):
    '''
    Return a list of the new modules, pass an kldstat dict before running
    modprobe and one after modprobe has run
    '''
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod['module'])
    for mod in post_mods:
        post.add(mod['module'])
    return list(post - pre)


def _rm_mods(pre_mods, post_mods):
    '''
    Return a list of the new modules, pass an kldstat dict before running
    modprobe and one after modprobe has run
    '''
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod['module'])
    for mod in post_mods:
        post.add(mod['module'])
    return list(pre - post)


def available():
    '''
    Return a list of all available kernel modules

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.available
    '''
    ret = []
    for path in __salt__['cmd.run']('ls /boot/kernel | grep .ko$').splitlines():
        bpath = os.path.basename(path)
        comps = bpath.split('.')
        if 'ko' in comps:
            # This is a kernel module, return it without the .ko extension
            ret.append('.'.join(comps[:comps.index('ko')]))
    return ret


def check_available(mod):
    '''
    Check to see if the specified kernel module is available

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.check_available kvm
    '''
    return mod in available()


def lsmod():
    '''
    Return a dict containing information about currently loaded modules

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.lsmod
    '''
    ret = []
    for line in __salt__['cmd.run']('kldstat').splitlines():
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

    .. code-block:: bash

        salt '*' kmod.load kvm
    '''
    pre_mods = lsmod()
    __salt__['cmd.run_all']('kldload {0}'.format(mod))
    post_mods = lsmod()
    return _new_mods(pre_mods, post_mods)


def remove(mod):
    '''
    Remove the specified kernel module

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.remove kvm
    '''
    pre_mods = lsmod()
    __salt__['cmd.run_all']('kldunload {0}'.format(mod))
    post_mods = lsmod()
    return _rm_mods(pre_mods, post_mods)

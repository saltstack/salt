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


def _get_persistent_modules():
    mods = set()
    for mod in __salt__['cmd.run']('sysrc -ni kld_list').split():
        mods.add(mod)
    return mods


def _set_persistent_module(mod):
    '''
    Add a module to sysrc to make it persistent.
    '''
    if not mod_name or mod_name in mod_list(True) or mod_name not in \
            available():
        return set()
    mods = _get_persistent_modules().add(mod)
    __salt__['cmd.run']('sysrc kld_list="{0}"'.format(mods))
    return set([mod])


def _remove_persistent_module(mod):
    '''
    Remove module from sysrc.
    '''
    if not mod_name or mod_name not in mod_list(True):
        return set()
    mods = _get_persistent_modules().remove(mod)
    __salt__['cmd.run']('sysrc kld_list="{0}"'.format(mods))
    return set([mod])


def available():
    '''
    Return a list of all available kernel modules

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.available
    '''
    ret = []
    for path in __salt__['file.find']('/boot/kernel', name='*.ko$'):
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

        salt '*' kmod.check_available vmm
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
        if comps[0] == 'Id':
            continue
        if comps[4] == 'kernel':
            continue
        mdat = {}
        mdat['module'] = comps[4][:-3]
        mdat['size'] = comps[3]
        mdat['depcount'] = comps[1]
        ret.append(mdat)
    return ret


def mod_list(only_persist=False):
    '''
    Return a list of the loaded module names

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.mod_list
    '''
    mods = set()
    if only_persist:
        for mod in _get_persistent_modules():
            mods.add(mod)
    else for mod in lsmod():
        mods.add(mod['module'])
    return sorted(list(mods))


def load(mod, persist=False):
    '''
    Load the specified kernel module

    mod
        Name of the module to add

    persist
        Write the module to sysrc kld_modules to make it load on system reboot

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.load bhyve
    '''
    pre_mods = lsmod()
    __salt__['cmd.run_all']('kldload {0}'.format(mod))
    post_mods = lsmod()
    mods = _new_mods(pre_mods, post_mods)
    persist_mods = set()
    if persist:
        persist_mods = _set_persistent_module(mod)
    return sorted(list(mods | persist_mods))


def is_loaded(mod):
    '''
    Check to see if the specified kernel module is loaded

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.is_loaded vmm
    '''
    return mod in mod_list()


def remove(mod, persist=False):
    '''
    Remove the specified kernel module

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.remove vmm
    '''
    pre_mods = lsmod()
    __salt__['cmd.run_all']('kldunload {0}'.format(mod))
    post_mods = lsmod()
    mods = _rm_mods(pre_mods, post_mods)
    persist_mods = set()
    if persist:
        persist_mods = _remove_persistent_module(mod)
    return sorted(list(mods | persist_mods))

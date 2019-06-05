# -*- coding: utf-8 -*-
'''
Module to manage FreeBSD kernel modules
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import os
import re

# Import salt libs
import salt.utils.files

# Define the module's virtual name
__virtualname__ = 'kmod'


_LOAD_MODULE = '{0}_load="YES"'
_LOADER_CONF = '/boot/loader.conf'
_MODULE_RE = '^{0}_load="YES"'
_MODULES_RE = r'^(\w+)_load="YES"'


def __virtual__():
    '''
    Only runs on FreeBSD systems
    '''
    if __grains__['kernel'] == 'FreeBSD':
        return __virtualname__
    return (False, 'The freebsdkmod execution module cannot be loaded: only available on FreeBSD systems.')


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
    return post - pre


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
    return pre - post


def _get_module_name(line):
    match = re.search(_MODULES_RE, line)
    if match:
        return match.group(1)
    return None


def _get_persistent_modules():
    '''
    Returns a list of modules in loader.conf that load on boot.
    '''
    mods = set()
    with salt.utils.files.fopen(_LOADER_CONF, 'r') as loader_conf:
        for line in loader_conf:
            line = salt.utils.stringutils.to_unicode(line)
            line = line.strip()
            mod_name = _get_module_name(line)
            if mod_name:
                mods.add(mod_name)
    return mods


def _set_persistent_module(mod):
    '''
    Add a module to loader.conf to make it persistent.
    '''
    if not mod or mod in mod_list(True) or mod not in \
            available():
        return set()
    __salt__['file.append'](_LOADER_CONF, _LOAD_MODULE.format(mod))
    return set([mod])


def _remove_persistent_module(mod):
    '''
    Remove module from loader.conf.
    '''
    if not mod or mod not in mod_list(True):
        return set()
    __salt__['file.sed'](_LOADER_CONF, _MODULE_RE.format(mod), '')
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
        ret.append({
            'module': comps[4][:-3],
            'size': comps[3],
            'depcount': comps[1]
        })
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
        if not _get_persistent_modules():
            return mods
        for mod in _get_persistent_modules():
            mods.add(mod)
    else:
        for mod in lsmod():
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
    response = __salt__['cmd.run_all']('kldload {0}'.format(mod),
                                       python_shell=False)
    if response['retcode'] == 0:
        post_mods = lsmod()
        mods = _new_mods(pre_mods, post_mods)
        persist_mods = set()
        if persist:
            persist_mods = _set_persistent_module(mod)
        return sorted(list(mods | persist_mods))
    elif 'module already loaded or in kernel' in response['stderr']:
        if persist and mod not in _get_persistent_modules():
            persist_mods = _set_persistent_module(mod)
            return sorted(list(persist_mods))
        else:
            # It's compiled into the kernel
            return [None]
    else:
        return 'Module {0} not found'.format(mod)


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
    __salt__['cmd.run_all']('kldunload {0}'.format(mod),
                            python_shell=False)
    post_mods = lsmod()
    mods = _rm_mods(pre_mods, post_mods)
    persist_mods = set()
    if persist:
        persist_mods = _remove_persistent_module(mod)
    return sorted(list(mods | persist_mods))

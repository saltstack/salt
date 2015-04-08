# -*- coding: utf-8 -*-
'''
Wrap the cp module allowing for managed ssh file transfers
'''
from __future__ import absolute_import

# Import salt libs
import salt.client.ssh


def get_file(path, dest, saltenv='base'):
    '''
    Send a file from the master to the location in specified
    '''
    src = __context__['fileclient'].cache_file(path, saltenv)
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt__.kwargs)
    ret = single.shell.send(src, dest)
    return not ret[2]


def get_dir(path, dest, saltenv='base'):
    '''
    Transfer a directory down
    '''
    src = __context__['fileclient'].cache_dir(path, saltenv)
    src = ' '.join(src)
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt__.kwargs)
    ret = single.shell.send(src, dest)
    return not ret[2]


def get_url(path, dest, saltenv='base'):
    '''
    retrive a URL
    '''
    src = __context__['fileclient'].get_url(path, saltenv)
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt__.kwargs)
    ret = single.shell.send(src, dest)
    return not ret[2]


def list_states(saltenv='base'):
    '''
    List all the available state modules in an environment
    '''
    return __context__['fileclient'].list_states(saltenv)


def list_master(saltenv='base', prefix=''):
    '''
    List all of the files stored on the master
    '''
    return __context__['fileclient'].file_list(saltenv, prefix)


def list_master_dirs(saltenv='base', prefix=''):
    '''
    List all of the directories stored on the master
    '''
    return __context__['fileclient'].dir_list(saltenv, prefix)


def list_master_symlinks(saltenv='base', prefix=''):
    '''
    List all of the symlinks stored on the master
    '''
    return __context__['fileclient'].symlink_list(saltenv, prefix)

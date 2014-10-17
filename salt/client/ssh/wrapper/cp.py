# -*- coding: utf-8 -*-
'''
Wrap the cp module allowing for managed ssh file transfers
'''

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
            **__salt_.kwargs)
    single.send(src, dest)
    return dest


def get_dir(path, dest, saltenv='base'):
    '''
    Transfer a directory down
    '''
    src = __context__['fileclient'].cache_dir(path, saltenv)
    src = ' '.join(src)
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt_.kwargs)
    single.send(src, dest)
    return dest


def get_url(path, dest, saltenv='base'):
    '''
    retrive a URL
    '''
    src = __context__['fileclient'].get_url(path, saltenv)
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt_.kwargs)
    single.send(src, dest)
    return dest

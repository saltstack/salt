'''
Module for managing NFS.
'''

# Import python libs
import logging

import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on these platorms, specific service modules exist:
    disable = [
        'Windows',
        ]
    if not salt.utils.which('showmount'):
        return False
    return 'nfs'


def list_exports(exports='/etc/exports'):
    '''
    List configured exports

    CLI Example::

        salt '*' nfs.list_exports
    '''
    ret = {}
    f = open(exports, 'r')
    for line in f.read().splitlines():
        if not line:
            continue
        if line.startswith('#'):
            continue
        comps = line.split()
        ret[comps[0]] = []
        for perm in comps[1:]:
            permcomps = perm.split('(')
            permcomps[1] = permcomps[1].replace(')', '')
            hosts = permcomps[0].split(',')
            options = permcomps[1].split(',')
            ret[comps[0]].append({'hosts': hosts, 'options': options})
    f.close()
    return ret

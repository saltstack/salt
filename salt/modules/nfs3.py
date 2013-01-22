'''
Module for managing NFS version 3.
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
    return 'nfs3'


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
        newshares = []
        for perm in comps[1:]:
            if perm.startswith('/'):
                newshares.append(perm)
                continue
            permcomps = perm.split('(')
            permcomps[1] = permcomps[1].replace(')', '')
            hosts = permcomps[0].split(',')
            options = permcomps[1].split(',')
            ret[comps[0]].append({'hosts': hosts, 'options': options})
        for share in newshares:
            ret[share] = ret[comps[0]]
    f.close()
    return ret


def del_export(exports='/etc/exports', path=None):
    '''
    Remove an export

    CLI Example::

        salt '*' nfs.del_export /media/storage
    '''
    edict = list_exports(exports)
    del edict[path]
    _write_exports(exports, edict)
    return edict


def _write_exports(exports, edict):
    '''
    Write an exports file to disk

    If multiple shares were initially configured per line, like:

        /media/storage /media/data *(ro,sync,no_subtree_check)

    ...then they will be saved to disk with only one share per line:

        /media/storage *(ro,sync,no_subtree_check)
        /media/data *(ro,sync,no_subtree_check)
    '''
    f = open(exports, 'w')
    for export in edict:
        line = export
        for perms in edict[export]:
            hosts = ','.join(perms['hosts'])
            options = ','.join(perms['options'])
            line += ' {0}({1})'.format(hosts, options)
        f.write('{0}\n'.format(line))
    f.close()

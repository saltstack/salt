# -*- coding: utf-8 -*-
'''
Operations with Rsync.
'''

import salt.utils


def __virtual__():
    '''
    Only if Rsync is available.

    :return:
    '''
    return salt.utils.which('rsync') and 'rsync' or False


def synchronized(name, source, delete=False, force=False, update=False,
                 passwordfile=None, exclude=None, excludefrom=None):
    '''
    Synchronizing directories:

    .. code-block:: yaml

        /opt/user-backups:
          rsync.synchronized:
            - source: /home
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    result = __salt__['rsync.rsync'](source, name, delete=delete, force=force, update=update,
                                     passwordfile=passwordfile, exclude=exclude, excludefrom=excludefrom)

    return ret

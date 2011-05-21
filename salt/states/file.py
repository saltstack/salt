'''
Manage file states
'''

import os
import hashlib
import difflib

def _makedirs(path):
    '''
    Ensure that the directory containing this path is available.
    '''
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

def managed(name,
        source,
        user=None,
        group=None,
        mode=None,
        template=None,
        makedirs=False):
    '''
    Manage a given file
    '''
    # if the file exists:
    #   Get the sums
    #   get user, group, mode
    # else:
    #   throw down the file
    changes = {}
    if os.path.isfile(name):
        source_sum = __salt__['cp.hash_file'](source)
        name_sum = getattr(hashlib, source_sum['hash_type'])(open(path,
            'rb').read()).hexdigest()
        if not source_sum:
            return {'name': name,
                    'changes': changes,
                    'result': False,
                    'comment': 'File not found on server'}
        if os.path.isfile(name):
            luser = __salt__['file.get_user'](name)
            lgroup = __salt__['file.get_group'](name)
            lmode = __salt__['file.get_mode'][name]
        if source_sum['hsum'] != name_sum:

        if user:
            if user != luser:
                changes['user'] = user
                luser = user
            if group != lgroup:
                changes['group'] = group
                lgroup = group
            if changes.has_key('user') or changes.has_key('group'):
                __salt__['file.chown'](name, luser, lgroup)
            if mode != lmode:
                changes['mode'] = mode
                __salt__['file.set_mode'](name, mode)


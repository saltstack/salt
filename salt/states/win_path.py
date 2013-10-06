# -*- coding: utf-8 -*-
'''
Manage the Windows System PATH
'''

# Python Libs
import re


def __virtual__():
    '''
    Load this state if the win_path module exists
    '''
    return 'win_path' if 'win_path.rehash' in __salt__ else False


def _normalize_dir(string):
    '''
    Normalize the directory to make comparison possible
    '''
    return re.sub(r'\\$', '', string.lower())


def absent(name):
    '''
    Remove the directory from the SYSTEM path

    index: where the directory should be placed in the PATH (default: 0)

    Example::

        'C:\\sysinternals':
          win_path.absent
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if __salt__['win_path.exists'](name):
        ret['changes']['removed'] = name
    else:
        ret['comment'] = '{0} is not in the PATH'.format(name)

    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['result'] = __salt__['win_path.remove'](name)
    if not ret['result']:
        ret['comment'] = 'could not remove {0} from the PATH'.format(name)
    return ret


def exists(name, index=0):
    '''
    Add the directory to the system PATH at index location

    index: where the directory should be placed in the PATH (default: 0)

    Example::

        'C:\\python27':
          win_path.exists

        'C:\\sysinternals':
          win_path.exists:
            index: 0
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # determine what to do
    sysPath = __salt__['win_path.get_path']()
    path = _normalize_dir(name)

    index = int(index)
    if index < 0:
        index = len(sysPath) + index
    if index > len(sysPath) - 1:
        index = len(sysPath) - 1

    try:
        currIndex = sysPath.index(path)
        if currIndex != index:
            sysPath.pop(currIndex)
            ret['changes']['removed'] = '{0} was removed from index {1}'.format(name, currIndex)
        else:
            ret['comment'] = '{0} is already present in the PATH at the right location'.format(name)
            return ret
    except ValueError:
        pass

    ret['changes']['added'] = '{0} will be added at index {1}'.format(name, index)
    if __opts__['test']:
        ret['result'] = None
        return ret

    # Add it
    ret['result'] = __salt__['win_path.add'](path, index)
    if not ret['result']:
        ret['comment'] = 'could not add {0} to the PATH'.format(name)
    else:
        ret['changes']['added'] = '{0} was added at index {1}'.format(name, index)
    return ret

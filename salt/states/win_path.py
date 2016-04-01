# -*- coding: utf-8 -*-
'''
Manage the Windows System PATH
'''
from __future__ import absolute_import

# Python Libs
import re
import os


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

    Example:

    .. code-block:: yaml

        'C:\\sysinternals':
          win_path.absent
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    localPath = os.environ["PATH"].split(os.pathsep)
    if name in localPath:
        localPath.remove(name)
        os.environ["PATH"] = os.pathsep.join(localPath)

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


def exists(name, index=None):
    '''
    Add the directory to the system PATH at index location

    index: where the directory should be placed in the PATH (default: None)
    [Note:  Providing no index will append directory to PATH and
    will not enforce its location within the PATH.]

    Example:

    .. code-block:: yaml

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

    localPath = os.environ["PATH"].split(os.pathsep)
    if path not in localPath:
        localPath.append(path)
        os.environ["PATH"] = os.pathsep.join(localPath)

    try:
        currIndex = sysPath.index(path)
        if index:
            index = int(index)
            if index < 0:
                index = len(sysPath) + index + 1
            if index > len(sysPath):
                index = len(sysPath)
            # check placement within PATH
            if currIndex != index:
                sysPath.pop(currIndex)
                ret['changes']['removed'] = '{0} was removed from index {1}'.format(name, currIndex)
            else:
                ret['comment'] = '{0} is already present in the PATH at the right location'.format(name)
                return ret
        else:  # path is in system PATH; don't care where
            ret['comment'] = '{0} is already present in the PATH at the right location'.format(name)
            return ret
    except ValueError:
        pass

    if not index:
        index = len(sysPath)    # put it at the end
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

# -*- coding: utf-8 -*-
'''
Manage the Windows System PATH
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six


def __virtual__():
    '''
    Load this state if the win_path module exists
    '''
    return 'win_path' if 'win_path.rehash' in __salt__ else False


def _format_comments(ret, comments):
    ret['comment'] = ' '.join(comments)
    return ret


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

    if not __salt__['win_path.exists'](name):
        ret['comment'] = '{0} is not in the PATH'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = '{0} would be removed from the PATH'.format(name)
        ret['result'] = None
        return ret

    __salt__['win_path.remove'](name)

    if __salt__['win_path.exists'](name):
        ret['comment'] = 'Failed to remove {0} from the PATH'.format(name)
        ret['result'] = False
    else:
        ret['comment'] = 'Removed {0} from the PATH'.format(name)
        ret['changes']['removed'] = name

    return ret


def exists(name, index=None):
    '''
    Add the directory to the system PATH at index location

    index: where the directory should be placed in the PATH (default: None).
    This is 0-indexed, so 0 means to prepend at the very start of the PATH.
    [Note:  Providing no index will append directory to PATH and
    will not enforce its location within the PATH.]

    Example:

    .. code-block:: yaml

        'C:\\python27':
          win_path.exists

        'C:\\sysinternals':
          win_path.exists:
            - index: 0
    '''
    name = salt.utils.stringutils.to_unicode(name)

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if index is not None and not isinstance(index, six.integer_types):
        ret['comment'] = 'Index must be an integer'
        ret['result'] = False
        return ret

    def _index():
        try:
            return __salt__['win_path.get_path']().index(name)
        except ValueError:
            return None

    def _changes(old, new):
        return {'index': {'old': old, 'new': new}}

    old_index = _index()
    comments = []
    failed = False

    if index is not None and old_index is not None:
        if index == old_index:
            comments.append(
                '{0} already exists in the PATH at index {1}.'.format(
                    name, index
                )
            )
            return _format_comments(ret, comments)
        else:
            if __opts__['test']:
                ret['result'] = None
                comments.append(
                    '{0} would be moved from index {1} to {2}.'.format(
                        name, old_index, index
                    )
                )
                ret['changes'] = _changes(old_index, index)
                return _format_comments(ret, comments)

            try:
                __salt__['win_path.remove'](name)
            except Exception as exc:
                comments.append('Encountered error: {0}.'.format(exc))
                failed = True

    if not failed:
        if index is None:
            if old_index is not None:
                comments.append('{0} already exists in the PATH.'.format(name))
                return _format_comments(ret, comments)
            else:
                if __opts__['test']:
                    ret['result'] = None
                    comments.append(
                        '{0} would be added to the PATH.'.format(name)
                    )
                    ret['changes'] = _changes(old_index, index)
                    return _format_comments(ret, comments)

        try:
            __salt__['win_path.add'](name, index)
        except Exception as exc:
            if index is not None and old_index is not None:
                comments.append(
                    'Successfully removed {0} from the PATH at index {1}, but '
                    'failed to add it back at index {2}.'.format(
                        name, old_index, index
                    )
                )
            comments.append('Encountered error: {0}.'.format(exc))

    new_index = _index()

    ret['result'] = new_index is not None \
        if index is None \
        else index == new_index

    if index is not None and old_index is not None:
        comments.append(
            '{0} {1} from index {2} to {3}.'.format(
                'Moved' if ret['result'] else 'Failed to move',
                name,
                old_index,
                index
            )
        )
    else:
        comments.append(
            '{0} {1} to the PATH{2}.'.format(
                'Added' if ret['result'] else 'Failed to add',
                name,
                ' at index {0}'.format(index) if index else ''
            )
        )

    if old_index != new_index:
        ret['changes'] = _changes(old_index, new_index)

    return _format_comments(ret, comments)

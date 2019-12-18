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

    index
        Position where the directory should be placed in the PATH. This is
        0-indexed, so 0 means to prepend at the very start of the PATH.

        .. note::
            If the index is not specified, and the directory needs to be added
            to the PATH, then the directory will be appended to the PATH, and
            this state will not enforce its location within the PATH.

    Examples:

    .. code-block:: yaml

        'C:\\python27':
          win_path.exists

        'C:\\sysinternals':
          win_path.exists:
            - index: 0

        'C:\\mystuff':
          win_path.exists:
            - index: -1
    '''
    try:
        name = salt.utils.stringutils.to_unicode(name)
    except TypeError:
        name = six.text_type(name)

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if index is not None and not isinstance(index, six.integer_types):
        ret['comment'] = 'Index must be an integer'
        ret['result'] = False
        return ret

    def _get_path_lowercase():
        return [x.lower() for x in __salt__['win_path.get_path']()]

    def _index(path=None):
        if path is None:
            path = _get_path_lowercase()
        try:
            pos = path.index(name.lower())
        except ValueError:
            return None
        else:
            if index is not None and index < 0:
                # Since a negative index was used, convert the index to a
                # negative index to make the changes dict easier to read, as
                # well as making comparisons manageable.
                return -(len(path) - pos)
            else:
                return pos

    def _changes(old, new):
        return {'index': {'old': old, 'new': new}}

    pre_path = _get_path_lowercase()
    num_dirs = len(pre_path)

    if index is not None:
        if index > num_dirs:
            ret.setdefault('warnings', []).append(
                'There are only {0} directories in the PATH, using an index '
                'of {0} instead of {1}.'.format(num_dirs, index)
            )
            index = num_dirs
        elif index <= -num_dirs:
            ret.setdefault('warnings', []).append(
                'There are only {0} directories in the PATH, using an index '
                'of 0 instead of {1}.'.format(num_dirs, index)
            )
            index = 0

    old_index = _index(pre_path)
    comments = []

    if old_index is not None:
        # Directory exists in PATH

        if index is None:
            # We're not enforcing the index, and the directory is in the PATH.
            # There's nothing to do here.
            comments.append('{0} already exists in the PATH.'.format(name))
            return _format_comments(ret, comments)
        else:
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

    else:
        # Directory does not exist in PATH
        if __opts__['test']:
            ret['result'] = None
            comments.append(
                '{0} would be added to the PATH{1}.'.format(
                    name,
                    ' at index {0}'.format(index) if index is not None else ''
                )
            )
            ret['changes'] = _changes(old_index, index)
            return _format_comments(ret, comments)

    try:
        ret['result'] = __salt__['win_path.add'](name, index=index, rehash=False)
    except Exception as exc:
        comments.append('Encountered error: {0}.'.format(exc))
        ret['result'] = False

    if ret['result']:
        ret['result'] = __salt__['win_path.rehash']()
        if not ret['result']:
            comments.append(
                'Updated registry with new PATH, but failed to rehash.'
            )

    new_index = _index()

    if ret['result']:
        # If we have not already determined a False result based on the return
        # from either win_path.add or win_path.rehash, check the new_index.
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

# -*- coding: utf-8 -*-
'''
Linux File Access Control Lists

The Linux ACL state module requires the `getfacl` and `setfacl` binaries.

Ensure a Linux ACL is present

.. code-block:: yaml

     root:
       acl.present:
         - name: /root
         - acl_type: user
         - acl_name: damian
         - perms: rwx

Ensure a Linux ACL does not exist

.. code-block:: yaml

     root:
       acl.absent:
         - name: /root
         - acl_type: user
         - acl_name: damian
         - perms: rwx
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import salt libs
from salt.ext import six
from salt.exceptions import CommandExecutionError
import salt.utils.path

log = logging.getLogger(__name__)

__virtualname__ = 'acl'


def __virtual__():
    '''
    Ensure getfacl & setfacl exist
    '''
    if salt.utils.path.which('getfacl') and salt.utils.path.which('setfacl'):
        return __virtualname__

    return False, 'The linux_acl state cannot be loaded: the getfacl or setfacl binary is not in the path.'


def present(name, acl_type, acl_name='', perms='', recurse=False):
    '''
    Ensure a Linux ACL is present
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    _octal = {'r': 4, 'w': 2, 'x': 1, '-': 0}
    _octal_lookup = {0: '-', 1: 'r', 2: 'w', 4: 'x'}

    if not os.path.exists(name):
        ret['comment'] = '{0} does not exist'.format(name)
        ret['result'] = False
        return ret

    __current_perms = __salt__['acl.getfacl'](name, recursive=recurse)

    if acl_type.startswith(('d:', 'default:')):
        _acl_type = ':'.join(acl_type.split(':')[1:])
        _current_perms = __current_perms[name].get('defaults', {})
        _default = True
    else:
        _acl_type = acl_type
        _current_perms = __current_perms[name]
        _default = False

    # The getfacl execution module lists default with empty names as being
    # applied to the user/group that owns the file, e.g.,
    # default:group::rwx would be listed as default:group:root:rwx
    # In this case, if acl_name is empty, we really want to search for root
    # but still uses '' for other

    # We search through the dictionary getfacl returns for the owner of the
    # file if acl_name is empty.
    if acl_name == '':
        _search_name = __current_perms[name].get('comment').get(_acl_type, '')
    else:
        _search_name = acl_name

    if _current_perms.get(_acl_type, None) or _default:
        try:
            user = [i for i in _current_perms[_acl_type] if next(six.iterkeys(i)) == _search_name].pop()
        except (AttributeError, IndexError, StopIteration, KeyError):
            user = None

        if user:
            octal_sum = sum([_octal.get(i, i) for i in perms])
            need_refresh = False
            for path in __current_perms:
                acl_found = False
                for user_acl in __current_perms[path].get(_acl_type, []):
                    if _search_name in user_acl and user_acl[_search_name]['octal'] == octal_sum:
                        acl_found = True
                        break
                if not acl_found:
                    need_refresh = True
                    break
            if not need_refresh:
                ret['comment'] = 'Permissions are in the desired state'
            else:
                _num = user[_search_name]['octal']
                new_perms = '{}{}{}'.format(_octal_lookup[_num & 1],
                                            _octal_lookup[_num & 2],
                                            _octal_lookup[_num & 4])
                changes = {'new': {'acl_name': acl_name,
                                   'acl_type': acl_type,
                                   'perms': perms},
                           'old': {'acl_name': acl_name,
                                   'acl_type': acl_type,
                                   'perms': new_perms}}

                if __opts__['test']:
                    ret.update({'comment': 'Updated permissions will be applied for '
                                '{0}: {1} -> {2}'.format(
                                    acl_name,
                                    new_perms,
                                    perms),
                                'result': None, 'changes': changes})
                    return ret
                try:
                    __salt__['acl.modfacl'](acl_type, acl_name, perms, name,
                                            recursive=recurse, raise_err=True)
                    ret.update({'comment': 'Updated permissions for '
                                '{0}'.format(acl_name),
                                'result': True, 'changes': changes})
                except CommandExecutionError as exc:
                    ret.update({'comment': 'Error updating permissions for '
                                '{0}: {1}'.format(acl_name, exc.strerror),
                                'result': False})
        else:
            changes = {'new': {'acl_name': acl_name,
                               'acl_type': acl_type,
                               'perms': perms}}

            if __opts__['test']:
                ret.update({'comment': 'New permissions will be applied for '
                                       '{0}: {1}'.format(acl_name, perms),
                            'result': None, 'changes': changes})
                ret['result'] = None
                return ret

            try:
                __salt__['acl.modfacl'](acl_type, acl_name, perms, name,
                                        recursive=recurse, raise_err=True)
                ret.update({'comment': 'Applied new permissions for '
                            '{0}'.format(acl_name),
                            'result': True, 'changes': changes})
            except CommandExecutionError as exc:
                ret.update({'comment': 'Error updating permissions for {0}: '
                            '{1}'.format(acl_name, exc.strerror),
                            'result': False})

    else:
        ret['comment'] = 'ACL Type does not exist'
        ret['result'] = False

    return ret


def absent(name, acl_type, acl_name='', perms='', recurse=False):
    '''
    Ensure a Linux ACL does not exist
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if not os.path.exists(name):
        ret['comment'] = '{0} does not exist'.format(name)
        ret['result'] = False
        return ret

    __current_perms = __salt__['acl.getfacl'](name, recursive=recurse)

    if acl_type.startswith(('d:', 'default:')):
        _acl_type = ':'.join(acl_type.split(':')[1:])
        _current_perms = __current_perms[name].get('defaults', {})
        _default = True
    else:
        _acl_type = acl_type
        _current_perms = __current_perms[name]
        _default = False

    # The getfacl execution module lists default with empty names as being
    # applied to the user/group that owns the file, e.g.,
    # default:group::rwx would be listed as default:group:root:rwx
    # In this case, if acl_name is empty, we really want to search for root
    # but still uses '' for other

    # We search through the dictionary getfacl returns for the owner of the
    # file if acl_name is empty.
    if acl_name == '':
        _search_name = __current_perms[name].get('comment').get(_acl_type, '')
    else:
        _search_name = acl_name

    if _current_perms.get(_acl_type, None) or _default:
        try:
            user = [i for i in _current_perms[_acl_type] if next(six.iterkeys(i)) == _search_name].pop()
        except (AttributeError, IndexError, StopIteration, KeyError):
            user = None

        need_refresh = False
        for path in __current_perms:
            acl_found = False
            for user_acl in __current_perms[path].get(_acl_type, []):
                if _search_name in user_acl:
                    acl_found = True
                    break
            if acl_found:
                need_refresh = True
                break

        if user or need_refresh:
            ret['comment'] = 'Removing permissions'

            if __opts__['test']:
                ret['result'] = None
                return ret

            __salt__['acl.delfacl'](acl_type, acl_name, perms, name, recursive=recurse)
        else:
            ret['comment'] = 'Permissions are in the desired state'

    else:
        ret['comment'] = 'ACL Type does not exist'
        ret['result'] = False

    return ret

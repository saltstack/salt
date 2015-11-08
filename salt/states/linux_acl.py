# -*- coding: utf-8 -*-
'''
Linux File Access Control Lists

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
from __future__ import absolute_import

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six

__virtualname__ = 'acl'


def __virtual__():
    '''
    Ensure getfacl & setfacl exist
    '''
    if salt.utils.which('getfacl') and salt.utils.which('setfacl'):
        return __virtualname__

    return False


def present(name, acl_type, acl_name='', perms='', recurse=False):
    '''
    Ensure a Linux ACL is present
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    _octal = {'r': 4, 'w': 2, 'x': 1}
    _current_perms = __salt__['acl.getfacl'](name)

    if acl_type.startswith(('d:', 'default:')):
        if acl_type.startswith('default'):
            _acl_type = acl_type.replace('default:', '')
        else:
            _acl_type = acl_type.replace('d:', '')
    else:
        _acl_type = acl_type

    try:
        if acl_type.startswith(('d:', 'default:')):
            if 'defaults' in _current_perms[name]:
                if _acl_type in ('other', 'mask'):
                    user = {_acl_type: _current_perms[name]['defaults'][_acl_type]}
                else:
                    if acl_name == '':
                        acl_name = 'owner'

                    user = [i for i in _current_perms[name]['defaults'][_acl_type] if next(six.iterkeys(i)) == acl_name].pop()
            else:
                user = None
        else:
            if _acl_type in ('other', 'mask'):
                user = {_acl_type: _current_perms[name][_acl_type]}
            else:
                if acl_name == '':
                    acl_name = 'owner'

                user = [i for i in _current_perms[name][_acl_type] if next(six.iterkeys(i)) == acl_name].pop()

    except (AttributeError, IndexError, StopIteration):
        user = None

    if user:
        if _acl_type in ('other', 'mask'):
            octal = user[_acl_type]['octal']
        else:
            octal = user[acl_name]['octal']

        if octal == sum([_octal.get(i, i) for i in perms]):
            ret['comment'] = 'Permissions are in the desired state'
        else:
            ret['changes']['perm changes'] = "from %s to %s" %  (octal, sum([_octal.get(i, i) for i in perms]))
            ret['comment'] = 'Permissions have been updated'

            if __opts__['test']:
                ret['result'] = None
                return ret

            if acl_name == 'owner':
                acl_name = ''

            if recurse:
                __salt__['acl.modfacl'](acl_type, acl_name, perms, name, recursive=True)
            else:
                __salt__['acl.modfacl'](acl_type, acl_name, perms, name)
    else:
        ret['comment'] = 'Permissions will be applied'
        ret['changes']['type added'] = "add %s:%s, the mode is %s" %  (acl_type, acl_name, sum([_octal.get(i, i) for i in perms]))

        if __opts__['test']:
            ret['result'] = None
            return ret

        if acl_name == 'owner':
            acl_name = ''

        if recurse:
            __salt__['acl.modfacl'](acl_type, acl_name, perms, name, recursive=True)
        else:
            __salt__['acl.modfacl'](acl_type, acl_name, perms, name)

    return ret


def absent(name, acl_type, acl_name='', perms='', recurse=False):
    '''
    Ensure a Linux ACL does not exist
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    _current_perms = __salt__['acl.getfacl'](name)

    if _current_perms[name].get(acl_type, None):
        try:
            user = [i for i in _current_perms[name][acl_type] if next(six.iterkeys(i)) == acl_name].pop()
        except IndexError:
            user = None

        if user:
            ret['comment'] = 'Removing permissions'

            if __opts__['test']:
                ret['result'] = None
                return ret

            if recurse:
                __salt__['acl.delfacl'](acl_type, acl_name, perms, name, recursive=True)
            else:
                __salt__['acl.delfacl'](acl_type, acl_name, perms, name)
        else:
            ret['comment'] = 'Permissions are in the desired state'

    else:
        ret['comment'] = 'ACL Type does not exist'
        ret['result'] = False

    return ret

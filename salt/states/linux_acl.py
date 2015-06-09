# -*- coding: utf-8 -*-
'''
Linux File Access Control Lists

Ensure a Linux ACL is present

.. code-block:: yaml

     root:
       acl.present:
         - name: /root
         - acl_type: users
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

# Import salt libs
import salt.utils

__virtualname__ = 'acl'


def __virtual__():
    '''
    Ensure getfacl & setfacl exist
    '''
    if salt.utils.which('getfacl') and salt.utils.which('setfacl'):
        return __virtualname__

    return False


def present(name, acl_type, acl_name, perms, recurse=False):
    '''
    Ensure a Linux ACL is present
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    _octal = {'r': 4, 'w': 2, 'x': 1}
    _current_perms = __salt__['acl.getfacl'](name)

    if _current_perms[name].get(acl_type, None):
        try:
            user = [i for i in _current_perms[name][acl_type] if i.keys()[0] == acl_name].pop()
        except IndexError:
            user = None

        if user:
            if user[acl_name]['octal'] == sum([_octal.get(i, i) for i in perms]):
                ret['comment'] = 'Permissions are in the desired state'
            else:
                ret['comment'] = 'Permissions have been updated'

                if __opts__['test']:
                    ret['result'] = None
                    return ret

                if recurse:
                    __salt__['acl.modfacl'](acl_type, acl_name, perms, name, recursive=True)
                else:
                    __salt__['acl.modfacl'](acl_type, acl_name, perms, name)
        else:
            ret['comment'] = 'Permissions will be applied'

            if __opts__['test']:
                ret['result'] = None
                return ret

            if recurse:
                __salt__['acl.modfacl'](acl_type, acl_name, perms, name, recursive=True)
            else:
                __salt__['acl.modfacl'](acl_type, acl_name, perms, name)
    else:
        ret['comment'] = 'ACL Type does not exist'
        ret['result'] = False

    return ret


def absent(name, acl_type, acl_name, perms, recurse=False):
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
            user = [i for i in _current_perms[name][acl_type] if i.keys()[0] == acl_name].pop()
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

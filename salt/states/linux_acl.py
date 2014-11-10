# -*- coding: utf-8 -*-
'''
Linux File Access Control Lists
'''

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

__virtualname__ = 'acl'

def __virtual__():
    '''
    Ensure getfacl & setfacl exist
    '''
    if salt.utils.which('getfacl') and salt.utils.which('setfacl'):
        return __virtualname__

    return False


def present(name, acl_type, acl_name, perms, recursive=False):
    '''
    Ensure a Linux ACL is present
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    _octal = {'r': 4, 'w': 2, 'x': 1}

    if __opts__['test']:
        _current_perms = __salt__['acl.getfacl'](name)

        if _current_perms[name].get(acl_type, None):
            try:
                user = [i for i in _current_perms[name][acl_type] if i.keys()[0] == acl_name].pop()
            except IndexError:
                pass

            if user:
                if user[acl_name]['octal'] == sum([_octal.get(i, i) for i in perms]):
                    ret['comment'] = '{0} has the desired permissions'.format(name)
                else:
                    ret['comment'] = '{0} permissions will be set'.format(perms)
            else:
                ret['comment'] = '{0} permissions will be set'.format(perms)
                ret['changes'] = {acl_name: 'will be set'}
        else:
            ret['comment'] = 'ACL Type does not exist'
            ret['result'] = False

        return ret
    #__salt__['acl.modfacl'](acl_type, acl_name, perms, name)
    pass


def absent(name, obj, acl, recurse=False):
    '''
    Ensure a Linux ACL does not exist
    '''
    pass

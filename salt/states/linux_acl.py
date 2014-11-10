# -*- coding: utf-8 -*-

'''
Linux File Access Control Lists
'''

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError


def __virtual__():
    '''
    Ensure getfacl & setfacl exist
    '''
    if salt.utils.which('getfacl') and salt.utils.which('setfacl'):
        return True

    return False


def present(name, obj, acl):
    '''
    Ensure a Linux ACL is present
    '''
    pass


def absent(name, obj, acl):
    '''
    Ensure a Linux ACL does not exist
    '''
    pass


def absolute(name, obj, acl):
    '''
    Ensure a Linux ACL exists and deletes any existing ones
    '''

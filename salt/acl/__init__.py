# -*- coding: utf-8 -*-
'''
The acl module handles client_acl operations

Additional information on client_acl can be
found by reading the salt documentation:

    http://docs.saltstack.com/en/latest/ref/clientacl.html
'''

# Import python libraries
from __future__ import absolute_import
import re


class ClientACL(object):
    '''
    Represents the client ACL and provides methods
    to query the ACL for given operations
    '''
    def __init__(self, blacklist):
        self.blacklist = blacklist

    def user_is_blacklisted(self, user):
        '''
        Takes a username as a string and returns a boolean. True indicates that
        the provided user has been blacklisted
        '''
        for blacklisted_user in self.blacklist.get('users', []):
            if re.match(blacklisted_user, user):
                return True
        return False

    def cmd_is_blacklisted(self, cmd):
        for blacklisted_module in self.blacklist.get('modules', []):
            # If this is a regular command, it is a single function
            if isinstance(cmd, str):
                funs_to_check = [cmd]
            # If this is a compound function
            else:
                funs_to_check = cmd
            for fun in funs_to_check:
                if re.match(blacklisted_module, fun):
                    return True
        return False

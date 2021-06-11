# -*- coding: utf-8 -*-
"""
The acl module handles publisher_acl operations

Additional information on publisher_acl can be
found by reading the salt documentation:

    http://docs.saltstack.com/en/latest/ref/publisheracl.html
"""

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six


class PublisherACL(object):
    """
    Represents the publisher ACL and provides methods
    to query the ACL for given operations
    """

    def __init__(self, blacklist):
        self.blacklist = blacklist

    def user_is_blacklisted(self, user):
        """
        Takes a username as a string and returns a boolean. True indicates that
        the provided user has been blacklisted
        """
        return not salt.utils.stringutils.check_whitelist_blacklist(
            user, blacklist=self.blacklist.get("users", [])
        )

    def cmd_is_blacklisted(self, cmd):
        # If this is a regular command, it is a single function
        if isinstance(cmd, six.string_types):
            cmd = [cmd]
        for fun in cmd:
            if not salt.utils.stringutils.check_whitelist_blacklist(
                fun, blacklist=self.blacklist.get("modules", [])
            ):
                return True
        return False

    def user_is_whitelisted(self, user):
        return salt.utils.stringutils.check_whitelist_blacklist(
            user, whitelist=self.blacklist.get("users", [])
        )

    def cmd_is_whitelisted(self, cmd):
        # If this is a regular command, it is a single function
        if isinstance(cmd, str):
            cmd = [cmd]
        for fun in cmd:
            if salt.utils.stringutils.check_whitelist_blacklist(
                fun, whitelist=self.blacklist.get("modules", [])
            ):
                return True
        return False

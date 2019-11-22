# -*- coding: utf-8 -*-
'''
Functions for querying and modifying a group account.
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import os

# Import Salt libs
import salt.utils.user
from salt.utils.decorators.jinja import jinja_filter

# Import 3rd-party libs

# Conditional imports
try:
    import grp
    HAS_GRP = True
except ImportError:
    HAS_GRP = False

log = logging.getLogger(__name__)


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system.
    :param gid: [Integer] group id to convert to a group name.
    :return: gid if the group name is not find, else the group name.
    '''
    ret = ''
    if HAS_GRP:
        if isinstance(gid, str):
            log.info("{} is not an integer, maybe it's already the group name ?".format(gid))
            gid = group_to_gid(gid)

        try:
            ret = grp.getgrgid(gid).gr_name
        except (KeyError, NameError):
            log.info("Group name is not present, fall back to the gid {}.".format(gid))
    else:
        log.error('Required external library (grp) not installed')
    return ret


def group_to_gid(group):
    '''
    Convert the group name to the group id on this system.
    :param group: [String] group name to convert to a group id.
    :return: group if the group name is not find, else the group name.
    '''
    ret = group
    if HAS_GRP:
        if isinstance(group, int):
            log.info("{} is not an string, maybe it's already the group id ?".format(group))
            group = gid_to_group(group)

        try:
            ret = grp.getgrnam(group).gr_gid
        except (KeyError, NameError):
            log.info("Group id is not present, fall back to the group {}.".format(group))
            ret = -1
    else:
        log.error('Required external library (grp) not installed')
    return ret


@jinja_filter('get_gname')
def get_group(gid=None):
    '''
    Get the current group name.
    :param gid: The group id to managed. If None, get the current group id.
    :return: None if not find, else the current group name.
    '''
    ret = None
    if HAS_GRP:
        if gid is None:
            ret = gid_to_group(get_gid())
        else:
            ret = gid_to_group(gid)
    else:
        log.error('Required external library (grp) not installed')
    return ret


@jinja_filter('get_gid')
def get_gid(group=None):
    '''
    Get the current group id.
    :param group: The group name to managed. If None, get the current group name.
    :return: None if not find, else the current group id.
    '''
    ret = None
    if HAS_GRP:
        if group is None:
            try:
                ret = os.getegid()
            except OSError:
                pass
        else:
            ret = group_to_gid(group)
    else:
        log.error('Required external library (grp) not installed')
    return ret


def get_all_group_name():
    '''
    Get all groups on the current system.
    :return: [] if not find, else all groups by name.
    '''
    ret = []
    if HAS_GRP:
        try:
            for group_values in grp.getgrall():
                ret.append(group_values.gr_name)
        except OSError:
            pass
    else:
        log.error('Required external library (grp) not installed')
    return sorted(ret)


def get_user_list(group):
    '''
    Get all user name attached to the group.
    :param group: The group name to managed.
    :return: [] if no users are attached to the group name, else the list of users name.
    '''
    ret = []
    if HAS_GRP:
        try:
            ret = grp.getgrnam(get_group(group)).gr_mem
        except OSError:
            pass
    else:
        log.error('Required external library (grp) not installed')
    return sorted(ret)


def get_uid_list(group):
    '''
    Get all user id attached to the group.
    :param group: The group name to managed.
    :return: [] if no users are attached to the group name, else the list of users id.
    '''
    ret = []
    if HAS_GRP:
        for user in get_user_list(group):
            ret.append(salt.utils.user.get_uid(user))
    else:
        log.error('Required external library (grp) not installed')
    return sorted(ret)


def get_user_dict(group):
    '''
    Get all user name and id attached to the group.
    :param group: The group name to managed.
    :return: {} if no users are attached to the group name, else the dict of users name and id.
    '''
    ret = {}
    if HAS_GRP:
        for user in get_user_list(group):
            ret.update({user: salt.utils.user.get_uid(user)})
    else:
        log.error('Required external library (grp) not installed')
    return ret

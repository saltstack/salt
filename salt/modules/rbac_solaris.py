# -*- coding: utf-8 -*-
'''
Module for Solaris' Role-Based Access Control

.. note::
    Solaris' RBAC system is very complex, for now
    this module will only focus on profiles.

'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'rbac'


def __virtual__():
    '''
    Provides rbac if we are running on a solaris like system
    '''
    if __grains__['kernel'] == 'SunOS' and salt.utils.which('profiles'):
        return __virtualname__
    return (
        False,
        '{0} module can only be loaded on a solaris like system'.format(
            __virtualname__
        )
    )


def profile_list(default_only=False):
    '''
    List all available profiles

    default_only : boolean
        return only default profile

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.profile_list
    '''
    profiles = {}
    default_profiles = ['All']

    ## lookup default profile(s)
    with salt.utils.fopen('/etc/security/policy.conf', 'r') as policy_conf:
        for policy in policy_conf:
            policy = policy.split('=')
            if policy[0].strip() == 'PROFS_GRANTED':
                default_profiles.extend(policy[1].strip().split(','))

    ## read prof_attr file (profname:res1:res2:desc:attr)
    with salt.utils.fopen('/etc/security/prof_attr', 'r') as prof_attr:
        for profile in prof_attr:
            profile = profile.split(':')

            # skip comments and non complaint lines
            if len(profile) != 5:
                continue

            # add profile info to dict
            profiles[profile[0]] = {
                'description': profile[3],
                'default':     profile[0] in default_profiles,
            }

    ## filtered profiles
    if default_only:
        for p in profiles.keys():
            if not profiles[p]['default']:
                del profiles[p]

    return profiles


def profile_get(user, default_hidden=True):
    '''
    List profiles for user

    user : string
        username
    default_hidden : boolean
        hide default profiles

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.profile_get leo
        salt '*' rbac.profile_get leo default_hidden=False
    '''
    user_profiles = []

    ## retrieve profiles
    res = __salt__['cmd.run_all']('profiles {0}'.format(user))
    if res['retcode'] == 0:
        for profile in res['stdout'].splitlines()[1:]:
            user_profiles.append(profile.strip())

    ## remove default profiles
    if default_hidden:
        for profile in profile_list(default_only=True):
            if profile in user_profiles:
                user_profiles.remove(profile)

    return user_profiles


def profile_add(user, profile):
    '''
    Add profile to user

    user : string
        username
    profile : string
        profile name

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.profile_add martine 'Primary Administrator'
        salt '*' rbac.profile_add martine 'User Management,User Security'
    '''
    ret = {}

    ## validate profiles
    profiles = profile.split(',')
    known_profiles = profile_list().keys()
    valid_profiles = [p for p in profiles if p in known_profiles]
    log.debug(
        'rbac.profile_add - profiles={0}, known_profiles={1}, valid_profiles={2}'.format(
            profiles,
            known_profiles,
            valid_profiles,
        )
    )

    ## update user profiles
    if len(valid_profiles) > 0:
        res = __salt__['cmd.run_all']('usermod -P "{profiles}" {login}'.format(
            login=user,
            profiles=','.join(set(profile_get(user) + valid_profiles)),
        ))
        if res['retcode'] > 0:
            ret['Error'] = {
                'retcode': res['retcode'],
                'message': res['stderr'] if 'stderr' in res else res['stdout']
            }
            return ret

    ## update return value
    active_profiles = profile_get(user, False)
    for p in profiles:
        if p not in valid_profiles:
            ret[p] = 'Unknown'
        elif p in active_profiles:
            ret[p] = 'Added'
        else:
            ret[p] = 'Failed'

    return ret


def profile_rm(user, profile):
    '''
    Remove profile from user

    user : string
        username
    profile : string
        profile name

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.profile_rm jorge 'Primary Administrator'
        salt '*' rbac.profile_rm jorge 'User Management,User Security'
    '''
    ret = {}

    ## validate profiles
    profiles = profile.split(',')
    known_profiles = profile_list().keys()
    valid_profiles = [p for p in profiles if p in known_profiles]
    log.debug(
        'rbac.profile_rm - profiles={0}, known_profiles={1}, valid_profiles={2}'.format(
            profiles,
            known_profiles,
            valid_profiles,
        )
    )

    ## update user profiles
    if len(valid_profiles) > 0:
        res = __salt__['cmd.run_all']('usermod -P "{profiles}" {login}'.format(
            login=user,
            profiles=','.join([p for p in profile_get(user) if p not in valid_profiles]),
        ))
        if res['retcode'] > 0:
            ret['Error'] = {
                'retcode': res['retcode'],
                'message': res['stderr'] if 'stderr' in res else res['stdout']
            }
            return ret

    ## update return value
    active_profiles = profile_get(user, False)
    for p in profiles:
        if p not in valid_profiles:
            ret[p] = 'Unknown'
        elif p in active_profiles:
            ret[p] = 'Failed'
        else:
            ret[p] = 'Remove'

    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

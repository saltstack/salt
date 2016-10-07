# -*- coding: utf-8 -*-
'''
Module for Solaris' Role-Based Access Control

.. note::
    Solaris' RBAC system is very complex, for now
    this module will only focus on profiles and roles.

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


def role_list():
    '''
    List all available roles

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.role_list
    '''
    roles = {}

    ## read user_attr file (user:qualifier:res1:res2:attr)
    with salt.utils.fopen('/etc/user_attr', 'r') as user_attr:
        for role in user_attr:
            role = role.split(':')

            # skip comments and non complaint lines
            if len(role) != 5:
                continue

            # parse attr
            attrs = {}
            for attr in role[4].split(';'):
                attr_key, attr_val = attr.split('=')
                if attr_key in ['auths', 'profiles', 'roles']:
                    attrs[attr_key] = attr_val.split(',')
                else:
                    attrs[attr_key] = attr_val
            role[4] = attrs

            # add role info to dict
            if 'type' in role[4] and role[4]['type'] == 'role':
                del role[4]['type']
                roles[role[0]] = role[4]

    return roles


def role_get(user):
    '''
    List roles for user

    user : string
        username

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.role_get leo
    '''
    user_roles = []

    ## retrieve profiles
    res = __salt__['cmd.run_all']('roles {0}'.format(user))
    if res['retcode'] == 0:
        for role in res['stdout'].splitlines():
            if ',' in role:
                user_roles.extend(role.strip().split(','))
            else:
                user_roles.append(role.strip())

    return user_roles


def role_add(user, role):
    '''
    Add role to user

    user : string
        username
    role : string
        role name

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.role_add martine netcfg
        salt '*' rbac.role_add martine netcfg,zfssnap
    '''
    ret = {}

    ## validate roles
    roles = role.split(',')
    known_roles = role_list().keys()
    valid_roles = [r for r in roles if r in known_roles]
    log.debug(
        'rbac.role_add - roles={0}, known_roles={1}, valid_roles={2}'.format(
            roles,
            known_roles,
            valid_roles,
        )
    )

    ## update user roles
    if len(valid_roles) > 0:
        res = __salt__['cmd.run_all']('usermod -R "{roles}" {login}'.format(
            login=user,
            roles=','.join(set(role_get(user) + valid_roles)),
        ))
        if res['retcode'] > 0:
            ret['Error'] = {
                'retcode': res['retcode'],
                'message': res['stderr'] if 'stderr' in res else res['stdout']
            }
            return ret

    ## update return value
    active_roles = role_get(user)
    for r in roles:
        if r not in valid_roles:
            ret[r] = 'Unknown'
        elif r in active_roles:
            ret[r] = 'Added'
        else:
            ret[r] = 'Failed'

    return ret


def role_rm(user, role):
    '''
    Remove role from user

    user : string
        username
    role : string
        role name

    CLI Example:

    .. code-block:: bash

        salt '*' rbac.role_rm jorge netcfg
        salt '*' rbac.role_rm jorge netcfg,zfssnap
    '''
    ret = {}

    ## validate roles
    roles = role.split(',')
    known_roles = role_list().keys()
    valid_roles = [r for r in roles if r in known_roles]
    log.debug(
        'rbac.roles_rm - roles={0}, known_roles={1}, valid_roles={2}'.format(
            roles,
            known_roles,
            valid_roles,
        )
    )

    ## update user roles
    if len(valid_roles) > 0:
        res = __salt__['cmd.run_all']('usermod -R "{roles}" {login}'.format(
            login=user,
            roles=','.join([r for r in role_get(user) if r not in valid_roles]),
        ))
        if res['retcode'] > 0:
            ret['Error'] = {
                'retcode': res['retcode'],
                'message': res['stderr'] if 'stderr' in res else res['stdout']
            }
            return ret

    ## update return value
    active_roles = role_get(user)
    for r in roles:
        if r not in valid_roles:
            ret[r] = 'Unknown'
        elif r in active_roles:
            ret[r] = 'Failed'
        else:
            ret[r] = 'Remove'

    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

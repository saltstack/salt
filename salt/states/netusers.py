# -*- coding: utf-8 -*-
'''
Network Users
=============

Manage the users configuration on network devices via the NAPALM proxy.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`
- :mod:`Users configuration management module <salt.modules.napalm_users>`

.. versionadded:: 2016.11.0
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)

# Python std lib
from copy import deepcopy
from json import loads, dumps

# salt lib
from salt.ext import six

# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    return 'netusers'

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _retrieve_users():

    '''Retrieves configured users'''

    return __salt__['users.config']()


def _ordered_dict_to_dict(probes):

    '''.'''

    return loads(dumps(probes))


def _expand_users(device_users, common_users):

    '''Creates a longer list of accepted users on the device.'''

    expected_users = deepcopy(common_users)
    expected_users.update(device_users)

    return expected_users


def _check_users(users):

    '''Checks if the input dictionary of users is valid.'''

    messg = ''
    valid = True

    for user, user_details in six.iteritems(users):
        if not user_details:
            valid = False
            messg += 'Please provide details for username {user}.\n'.format(user=user)
            continue
        if not (isinstance(user_details.get('level'), int) or 0 <= user_details.get('level') <= 15):
            # warn!
            messg += 'Level must be a integer between 0 and 15 for username {user}. Will assume 0.\n'.format(user=user)

    return valid, messg


def _compute_diff(configured, expected):

    '''Computes the differences between the actual config and the expected config'''

    diff = {
        'add': {},
        'update': {},
        'remove': {}
    }

    configured_users = set(configured.keys())
    expected_users = set(expected.keys())

    add_usernames = expected_users - configured_users
    remove_usernames = configured_users - expected_users
    common_usernames = expected_users & configured_users

    add = dict((username, expected.get(username)) for username in add_usernames)
    remove = dict((username, configured.get(username)) for username in remove_usernames)
    update = {}

    for username in common_usernames:
        user_configuration = configured.get(username)
        user_expected = expected.get(username)
        if user_configuration == user_expected:
            continue
        update[username] = {}
        for field, field_value in six.iteritems(user_expected):
            if user_configuration.get(field) != field_value:
                update[username][field] = field_value

    diff.update({
        'add': add,
        'update': update,
        'remove': remove
    })

    return diff


def _set_users(users):

    '''Calls users.set_users.'''

    return __salt__['users.set_users'](users, commit=False)


def _update_users(users):

    '''Calls users.set_users.'''

    return __salt__['users.set_users'](users, commit=False)


def _delete_users(users):

    '''Calls users.delete_users.'''

    return __salt__['users.delete_users'](users, commit=False)

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def managed(name, users=None, defaults=None):

    '''
    Manages the configuration of the users on the device, as specified in the state SLS file. Users not defined in that
    file will be remove whilst users not configured on the device, will be added.

    SLS Example:

    .. code-block:: yaml

        netusers_example:
            netusers.managed:
                 - users:
                    admin:
                        level: 15
                        password: $1$knmhgPPv$g8745biu4rb.Zf.IT.F/U1
                        sshkeys: []
                    restricted:
                        level: 1
                        password: $1$j34j5k4b$4d5SVjTiz1l.Zf.IT.F/K7
                    martin:
                        level: 15
                        password: ''
                        sshkeys:
                            - ssh-dss AAAAB3NzaC1kc3MAAACBAK9dP3KariMlM/JmFW9rTSm5cXs4nR0+o6fTHP9o+bOLXMBTP8R4vwWHh0w
                                JPjQmJYafAqZTnlgi0srGjyifFwPtODppDWLCgLe2M4LXnu3OMqknr54w344zPHP3iFwWxHrBrZKtCjO8LhbWCa+
                                X528+i87t6r5e4ersdfxgchvjbknlio87t6r5drcfhgjhbknio8976tycv7t86ftyiu87Oz1nKsKuNzm2csoUQlJ
                                trmRfpjsOPNookmOz5wG0YxhwDmKeo6fWK+ATk1OiP+QT39fn4G77j8o+e4WAwxM570s35Of/vV0zoOccj753sXn
                                pvJenvwpM2H6o3a9ALvehAJKWodAgZT7X8+iu786r5drtycghvjbiu78t+wAAAIBURwSPZVElXe+9a43sF6M4ysT
                                7Xv+6wTsa8q86E3+RYyu8O2ObI2kwNLC3/HTgFniE/YqRG+WJac81/VHWQNP822gns8RVrWKjqBktmQoEm7z5yy0
                                bkjui78675dytcghvjkoi9y7t867ftcuvhbuu9t78gy/v+zvMmv8KvQgHg
                    jonathan:
                        level: 15
                        password: ''
                        sshkeys:
                            - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDcgxE6HZF/xjFtIt0thEDKPjFJxW9BpZtTVstYbDgGR9zPkHG
                                ZJT/j345jk345jk453jk43545j35nl3kln34n5kl4ghv3/JzWt/0Js5KZp/51KRNCs9O4t07qaoqwpLB15GwLfEX
                                Bx9dW26zc4O+hi6754trxcfghvjbo98765drt/LYIEg0KSQPWyJEK1g31gacbxN7Ab006xeHh7rv7HtXF6zH3WId
                                Uhq9rtdUag6kYnv6qvjG7sbCyHGYu5vZB7GytnNuVNbZuI+RdFvmHSnErV9HCu9xZBq6DBb+sESMS4s7nFcsruMo
                                edb+BAc3aww0naeWpogjSt+We7y2N

    CLI Example:

        salt 'edge01.kix01' state.sls router.users

    Output example (raw python - can be reused in other modules):

    .. code-block:: python

        {
            'netusers_|-netusers_example_|-netusers_example_|-managed': {
                'comment': 'Configuration updated!',
                'name': 'netusers_example',
                'start_time': '10:57:08.678811',
                '__id__': 'netusers_example',
                'duration': 1620.982,
                '__run_num__': 0,
                'changes': {
                    'updated': {
                        'admin': {
                            'level': 15
                        },
                        'restricted': {
                            'level': 1
                        },
                        'martin': {
                            'sshkeys': [
                                'ssh-dss AAAAB3NzaC1kc3MAAACBAK9dP3KariMlM/JmFW9rTSm5cXs4nR0+o6fTHP9o+bOLXMBTP8R4vwWHh0w
                                JPjQmJYafAqZTnlgi0srGjyifFwPtODppDWLCgLe2M4LXnu3OMqknr54w344zPHP3iFwWxHrBrZKtCjO8LhbWCa+
                                X528+i87t6r5e4ersdfxgchvjbknlio87t6r5drcfhgjhbknio8976tycv7t86ftyiu87Oz1nKsKuNzm2csoUQlJ
                                trmRfpjsOPNookmOz5wG0YxhwDmKeo6fWK+ATk1OiP+QT39fn4G77j8o+e4WAwxM570s35Of/vV0zoOccj753sXn
                                pvJenvwpM2H6o3a9ALvehAJKWodAgZT7X8+iu786r5drtycghvjbiu78t+wAAAIBURwSPZVElXe+9a43sF6M4ysT
                                7Xv+6wTsa8q86E3+RYyu8O2ObI2kwNLC3/HTgFniE/YqRG+WJac81/VHWQNP822gns8RVrWKjqBktmQoEm7z5yy0
                                bkjui78675dytcghvjkoi9y7t867ftcuvhbuu9t78gy/v+zvMmv8KvQgHg'
                            ]
                        }
                    },
                    'added': {
                        'jonathan': {
                            'password': '',
                            'sshkeys': [
                                'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDcgxE6HZF/xjFtIt0thEDKPjFJxW9BpZtTVstYbDgGR9zPkHG
                                ZJT/j345jk345jk453jk43545j35nl3kln34n5kl4ghv3/JzWt/0Js5KZp/51KRNCs9O4t07qaoqwpLB15GwLfEX
                                Bx9dW26zc4O+hi6754trxcfghvjbo98765drt/LYIEg0KSQPWyJEK1g31gacbxN7Ab006xeHh7rv7HtXF6zH3WId
                                Uhq9rtdUag6kYnv6qvjG7sbCyHGYu5vZB7GytnNuVNbZuI+RdFvmHSnErV9HCu9xZBq6DBb+sESMS4s7nFcsruMo
                                edb+BAc3aww0naeWpogjSt+We7y2N'
                            ],
                            'level': 15
                        }
                    },
                    'removed': {
                    }
                },
                'result': True
            }
        }

    CLI Output:

    .. code-block:: bash

        edge01.kix01:
            ----------
                      ID: netusers_example
                Function: netusers.managed
                  Result: True
                 Comment: Configuration updated!
                 Started: 11:03:31.957725
                Duration: 1220.435 ms
                 Changes:
                          ----------
                          added:
                              ----------
                              jonathan:
                                  ----------
                                  level:
                                      15
                                  password:
                                  sshkeys:
                                      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDcgxE6HZF/xjFtIt0thEDKPjFJxW9BpZtTVstYbDgG
                                      R9zPkHGZJT/j345jk345jk453jk43545j35nl3kln34n5kl4ghv3/JzWt/0Js5KZp/51KRNCs9O4t07qao
                                      qwpLB15GwLfEXBx9dW26zc4O+hi6754trxcfghvjbo98765drt/LYIEg0KSQPWyJEK1g31gacbxN7Ab006
                                      xeHh7rv7HtXF6zH3WIdUhq9rtdUag6kYnv6qvjG7sbCyHGYu5vZB7GytnNuVNbZuI+RdFvmHSnErV9HCu9
                                      xZBq6DBb+sESMS4s7nFcsruMoedb+BAc3aww0naeWpogjSt+We7y2N
                          removed:
                              ----------
                          updated:
                              ----------
                              martin:
                                  ----------
                                  sshkeys:
                                      - ssh-dss AAAAB3NzaC1kc3MAAACBAK9dP3KariMlM/JmFW9rTSm5cXs4nR0+o6fTHP9o+bOLXMBTP8R4
                                      vwWHh0wJPjQmJYafAqZTnlgi0srGjyifFwPtODppDWLCgLe2M4LXnu3OMqknr54w344zPHP3iFwWxHrBrZ
                                      KtCjO8LhbWCa+X528+i87t6r5e4ersdfxgchvjbknlio87t6r5drcfhgjhbknio8976tycv7t86ftyiu87
                                      Oz1nKsKuNzm2csoUQlJtrmRfpjsOPNookmOz5wG0YxhwDmKeo6fWK+ATk1OiP+QT39fn4G77j8o+e4WAwx
                                      M570s35Of/vV0zoOccj753sXnpvJenvwpM2H6o3a9ALvehAJKWodAgZT7X8+iu786r5drtycghvjbiu78t
                                      +wAAAIBURwSPZVElXe+9a43sF6M4ysT7Xv+6wTsa8q86E3+RYyu8O2ObI2kwNLC3/HTgFniE/YqRG+WJac
                                      81/VHWQNP822gns8RVrWKjqBktmQoEm7z5yy0bkjui78675dytcghvjkoi9y7t867ftcuvhbuu9t78gy/v
                                      +zvMmv8KvQgHg
                              admin:
                                  ----------
                                  level:
                                      15
                              restricted:
                                  ----------
                                  level:
                                      1
            Summary for edge01.kix01
            ------------
            Succeeded: 1 (changed=1)
            Failed:    0
            ------------
            Total states run:     1
            Total run time:   1.220 s
    '''

    result = False
    comment = ''
    changes = {}

    ret = {
        'name': name,
        'changes': changes,
        'result': result,
        'comment': comment
    }

    users = _ordered_dict_to_dict(users)
    defaults = _ordered_dict_to_dict(defaults)

    expected_users = _expand_users(users, defaults)
    valid, message = _check_users(expected_users)

    if not valid:  # check and clean
        ret['comment'] = 'Please provide a valid configuration: {error}'.format(error=message)
        return ret

    # ----- Retrieve existing users configuration and determine differences ------------------------------------------->

    users_output = _retrieve_users()
    if not users_output.get('result'):
        ret['comment'] = 'Cannot retrieve users from the device: {reason}'.format(
            reason=users_output.get('comment')
        )
        return ret

    configured_users = users_output.get('out', {})

    if configured_users == expected_users:
        ret.update({
            'comment': 'Users already configured as needed.',
            'result': True
        })
        return ret

    diff = _compute_diff(configured_users, expected_users)

    users_to_add = diff.get('add', {})
    users_to_update = diff.get('update', {})
    users_to_remove = diff.get('remove', {})

    changes = {
        'added': users_to_add,
        'updated': users_to_update,
        'removed': users_to_remove
    }

    ret.update({
        'changes': changes
    })

    if __opts__['test'] is True:
        ret.update({
            'result': None,
            'comment': 'Testing mode: configuration was not changed!'
        })
        return ret

    # <---- Retrieve existing NTP peers and determine peers to be added/removed --------------------------------------->

    # ----- Call _set_users and _delete_users as needed --------------------------------------------------------------->

    expected_config_change = False
    successfully_changed = True

    if users_to_add:
        _set = _set_users(users_to_add)
        if _set.get('result'):
            expected_config_change = True
        else:  # something went wrong...
            successfully_changed = False
            comment += 'Cannot configure new users: {reason}'.format(
                reason=_set.get('comment')
            )

    if users_to_update:
        _update = _update_users(users_to_update)
        if _update.get('result'):
            expected_config_change = True
        else:  # something went wrong...
            successfully_changed = False
            comment += 'Cannot update the users configuration: {reason}'.format(
                reason=_update.get('comment')
            )

    if users_to_remove:
        _delete = _delete_users(users_to_remove)
        if _delete.get('result'):
            expected_config_change = True
        else:  # something went wrong...
            successfully_changed = False
            comment += 'Cannot remove users: {reason}'.format(
                reason=_delete.get('comment')
            )

    # <---- Call _set_users and _delete_users as needed ----------------------------------------------------------------

    # ----- Try to commit changes ------------------------------------------------------------------------------------->

    if expected_config_change and successfully_changed:
        config_result, config_comment = __salt__['net.config_control']()
        result = config_result
        comment += config_comment

    # <---- Try to commit changes --------------------------------------------------------------------------------------

    if expected_config_change and result and not comment:
        comment = 'Configuration updated!'

    ret.update({
        'result': result,
        'comment': comment
    })

    return ret

# -*- coding: utf-8 -*-
'''
NAPALM Users
============

Manages the configuration of the users on network devices.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`

.. seealso::
    :mod:`Users management state <salt.states.netusers>`

.. versionadded:: 2016.11.0
'''

from __future__ import absolute_import, unicode_literals, print_function

import logging
log = logging.getLogger(__file__)

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'users'
__proxyenabled__ = ['napalm']
__virtual_aliases__ = ('napalm_users',)
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def config(**kwargs):  # pylint: disable=unused-argument

    '''
    Returns the configuration of the users on the device

    CLI Example:

    .. code-block:: bash

        salt '*' users.config

    Output example:

    .. code-block:: python

        {
            'mircea': {
                'level': 15,
                'password': '$1$0P70xKPa$4jt5/10cBTckk6I/w/',
                'sshkeys': [
                    'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC4pFn+shPwTb2yELO4L7NtQrKOJXNeCl1je\
                    l9STXVaGnRAnuc2PXl35vnWmcUq6YbUEcgUTRzzXfmelJKuVJTJIlMXii7h2xkbQp0YZIEs4P\
                    8ipwnRBAxFfk/ZcDsN3mjep4/yjN56ejk345jhk345jk345jk341p3A/9LIL7l6YewLBCwJj6\
                    D+fWSJ0/YW+7oH17Fk2HH+tw0L5PcWLHkwA4t60iXn16qDbIk/ze6jv2hDGdCdz7oYQeCE55C\
                    CHOHMJWYfN3jcL4s0qv8/u6Ka1FVkV7iMmro7ChThoV/5snI4Ljf2wKqgHH7TfNaCfpU0WvHA\
                    nTs8zhOrGScSrtb mircea@master-roshi'
                ]
            }
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_users',
        **{
        }
    )


@proxy_napalm_wrap
def set_users(users, test=False, commit=True, **kwargs):  # pylint: disable=unused-argument

    '''
    Configures users on network devices.

    :param users: Dictionary formatted as the output of the function config()

    :param test: Dry run? If set as True, will apply the config, discard and
        return the changes. Default: False

    :param commit: Commit? (default: True) Sometimes it is not needed to commit
        the config immediately after loading the changes. E.g.: a state loads a
        couple of parts (add / remove / update) and would not be optimal to
        commit after each operation.  Also, from the CLI when the user needs to
        apply the similar changes before committing, can specify commit=False
        and will not discard the config.

    :raise MergeConfigException: If there is an error on the configuration sent.
    :return a dictionary having the following keys:

    - result (bool): if the config was applied successfully. It is `False` only
      in case of failure. In case there are no changes to be applied and
      successfully performs all operations it is still `True` and so will be
      the `already_configured` flag (example below)
    - comment (str): a message for the user
    - already_configured (bool): flag to check if there were no changes applied
    - diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt '*' users.set_users "{'mircea': {}}"
    '''

    return __salt__['net.load_template']('set_users',
                                         users=users,
                                         test=test,
                                         commit=commit,
                                         inherit_napalm_device=napalm_device)  # pylint: disable=undefined-variable


@proxy_napalm_wrap
def delete_users(users, test=False, commit=True, **kwargs):  # pylint: disable=unused-argument

    '''
    Removes users from the configuration of network devices.

    :param users: Dictionary formatted as the output of the function config()
    :param test: Dry run? If set as True, will apply the config, discard and return the changes. Default: False
    :param commit: Commit? (default: True) Sometimes it is not needed to commit the config immediately
        after loading the changes. E.g.: a state loads a couple of parts (add / remove / update)
        and would not be optimal to commit after each operation.
        Also, from the CLI when the user needs to apply the similar changes before committing,
        can specify commit=False and will not discard the config.
    :raise MergeConfigException: If there is an error on the configuration sent.
    :return a dictionary having the following keys:
        - result (bool): if the config was applied successfully. It is `False`
          only in case of failure. In case there are no changes to be applied
          and successfully performs all operations it is still `True` and so
          will be the `already_configured` flag (example below)
        - comment (str): a message for the user
        - already_configured (bool): flag to check if there were no changes applied
        - diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt '*' users.delete_users "{'mircea': {}}"
    '''

    return __salt__['net.load_template']('delete_users',
                                         users=users,
                                         test=test,
                                         commit=commit,
                                         inherit_napalm_device=napalm_device)  # pylint: disable=undefined-variable

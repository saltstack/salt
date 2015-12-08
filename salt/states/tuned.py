# -*- coding: utf-8 -*-
'''
Interface to Red Hat tuned-adm module

:maintainer:    Syed Ali <alicsyed@gmail.com>
:maturity:      new
:depends:       cmd.run
:platform:      Linux
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.exceptions


def profile(name):
    '''
    This state module allows you to modify system tuned parameters

    Example tuned.sls file to set profile to virtual-guest

    tuned:
      tuned:
        - profile
        - name: virtual-guest

    name
        tuned profile name to set the system to

    To see a valid list of states call execution module:
        :py:func:`tuned.list <salt.modules.tuned.list_>`
    '''

    # create data-structure to return with default value
    ret = {'name': '', 'changes': {}, 'result': False, 'comment': ''}

    ret[name] = name
    profile = name

    # get the current state of tuned-adm
    current_state = __salt__['tuned.active']()

    valid_profiles = __salt__['tuned.list']()

    # check valid profiles, and return error if profile name is not valid
    if profile not in valid_profiles:
        raise salt.exceptions.SaltInvocationError('Invalid Profile Name')

    # if current state is same as requested state, return without doing much
    if profile in current_state:
        ret['result'] = True
        ret['comment'] = 'System already in the correct state'
        return ret

    # test mode
    if __opts__['test'] is True:
        ret['comment'] = 'The state of "{0}" will be changed.'.format(
            current_state)
        ret['changes'] = {
            'old': current_state,
            'new': 'Profile will be set to {0}'.format(profile),
        }

        # return None when testing
        ret['result'] = None
        return ret

    # we come to this stage if current state is different that requested state
    # we there have to set the new state request
    new_state = __salt__['tuned.profile'](profile)

    # create the comment data structure
    ret['comment'] = 'The state of "{0}" was changed!'.format(profile)

    # fill in the ret data structure
    ret['changes'] = {
        'old': current_state,
        'new': new_state,
    }

    ret['result'] = True

    # return with the dictionary data structure
    return ret


def off(name=None):
    '''

    Turns 'tuned' off.
    Example tuned.sls file for turning tuned off:

    tuned:
      tuned.off: []


    To see a valid list of states call execution module:
        :py:func:`tuned.list <salt.modules.tuned.list_>`
    '''

    # create data-structure to return with default value
    ret = {'name': 'off', 'changes': {}, 'result': False, 'comment': 'off'}

    # check the current state of tuned
    current_state = __salt__['tuned.active']()

    # if profile is already off, then don't do anything
    if current_state == 'off':
        ret['result'] = True
        ret['comment'] = 'System already in the correct state'
        return ret

    # test mode
    if __opts__['test'] is True:
        ret['comment'] = 'The state of "{0}" will be changed.'.format(
            current_state)
        ret['changes'] = {
            'old': current_state,
            'new': 'Profile will be set to off',
        }

        # return None when testing
        ret['result'] = None
        return ret

    # actually execute the off statement
    if __salt__['tuned.off']():
        ret['result'] = True
        ret['changes'] = {
            'old': current_state,
            'new': 'off',
        }
        return ret

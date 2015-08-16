# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import 3rd-party libs
import salt.ext.six as six

# define the module's virtual name
__virtualname__ = 'sysrc'


def __virtual__():
    '''
    Only load if sysrc executable exists
    '''
    return __salt__['cmd.has_exec']('sysrc')


def managed(name, value, **kwargs):
    '''
    Ensure a sysrc variable is set to a specific value.

    name
        The variable name to set
    value
        Value to set the variable to
    file
        (optional) The rc file to add the variable to.
    jail
        (option) the name or JID of the jail to set the value in.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Check the current state
    current_state = __salt__['sysrc.get'](name=name, **kwargs)
    if current_state is not None:
        for rcname, rcdict in six.iteritems(current_state):
            if rcdict[name] == value:
                ret['result'] = True
                ret['comment'] = '{0} is already set to the desired value.'.format(name)
                return ret

    if __opts__['test'] is True:
        ret['comment'] = 'The value of "{0}" will be changed!'.format(name)
        ret['changes'] = {
            'old': current_state,
            'new': name+' = '+value+' will be set.'
        }

        # When test=true return none
        ret['result'] = None

        return ret

    new_state = __salt__['sysrc.set'](name=name, value=value, **kwargs)

    ret['comment'] = 'The value of "{0}" was changed!'.format(name)

    ret['changes'] = {
        'old': current_state,
        'new': new_state
    }

    ret['result'] = True

    return ret


def absent(name, **kwargs):
    '''
    Ensure a sysrc variable is absent.

    name
        The variable name to set
    file
        (optional) The rc file to add the variable to.
    jail
        (option) the name or JID of the jail to set the value in.
    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Check the current state
    current_state = __salt__['sysrc.get'](name=name, **kwargs)
    if current_state is None:
        ret['result'] = True
        ret['comment'] = '"{0}" is already absent.'.format(name)
        return ret

    if __opts__['test'] is True:
        ret['comment'] = '"{0}" will be removed!'.format(name)
        ret['changes'] = {
            'old': current_state,
            'new': '"{0}" will be removed.'.format(name)
        }

        # When test=true return none
        ret['result'] = None

        return ret

    new_state = __salt__['sysrc.remove'](name=name, **kwargs)

    ret['comment'] = '"{0}" was removed!'.format(name)

    ret['changes'] = {
        'old': current_state,
        'new': new_state
    }

    ret['result'] = True

    return ret

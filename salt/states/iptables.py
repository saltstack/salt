# -*- coding: utf-8 -*-
'''
Management of iptables
======================

This is an iptables-specific module designed to manage Linux firewalls. It is
expected that this state module, and other system-specific firewall states, may
at some point be deprecated in favor of a more generic `firewall` state.

.. code-block:: yaml

    httpd:
      iptables.append:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True
'''


def __virtual__():
    '''
    Only load if the locale module is available in __salt__
    '''
    return 'iptables' if 'iptables.version' in __salt__ else False


def append(name, **kwargs):
    '''
    Append a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    All other arguments are passed in with the same name as the long option
    that would normally be used for iptables, with one exception: `--state` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    for ignore in "__env__",  "__sls__", "order":
        if ignore in kwargs:
            del kwargs[ignore]
    rule = __salt__['iptables.build_rule'](**kwargs)
    command = __salt__['iptables.build_rule'](full=True, command='A', **kwargs)
    if __salt__['iptables.check'](kwargs['table'], kwargs['chain'], rule) is True:
        ret['result'] = True
        ret['comment'] = 'iptables rule for {0} already set ({1})'.format(
            name,
            command.strip())
        return ret
    if __opts__['test']:
        ret['comment'] = 'iptables rule for {0} needs to be set ({1})'.format(
            name,
            command.strip())
        return ret
    if not __salt__['iptables.append'](kwargs['table'], kwargs['chain'], rule):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set iptables rule for {0} to: {1}'.format(
            name,
            command.strip())
        if 'save' in kwargs:
            if kwargs['save']:
                out = __salt__['iptables.save'](filename=None)
                ret['comment'] = ('Set and Saved iptables rule for {0} to: '
                                  '{1}'.format(name, command.strip()))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set iptables rule for {0}'.format(name)
        return ret


def set_policy(name, **kwargs):
    '''
    Sets policy for iptables firewall tables
    '''
    ret = {'name': name,
        'changes': {},
        'result': None,
        'comment': ''}

    for ignore in "__env__",  "__sls__", "order":
        if ignore in kwargs:
            del kwargs[ignore]

    if __salt__['iptables.get_policy'](
            kwargs['table'],
            kwargs['chain']) == kwargs['policy']:
        ret['result'] = True
        ret['comment'] = 'iptables default policy for {0} already set to {1}'.format(kwargs['table'], kwargs['policy'])
        return ret

    if not __salt__['iptables.set_policy'](
            kwargs['table'],
            kwargs['chain'],
            kwargs['policy']):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set default policy for {0} to {1}'.format(kwargs['chain'], kwargs['policy'])
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set iptables default policy'
        return ret


def flush(name, **kwargs):
    '''
    Flush current iptables state
    '''
    ret = {'name': name,
        'changes': {},
        'result': None,
        'comment': ''}

    for ignore in "__env__",  "__sls__", "order":
        if ignore in kwargs:
            del kwargs[ignore]

    if not __salt__['iptables.flush'](kwargs['table']):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Flush iptables rules in {0}'.format(kwargs['table'])
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush iptables rules'
        return ret

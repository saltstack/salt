# -*- coding: utf-8 -*-
'''
Management of ip6tables
======================

This is an ip6tables-specific module designed to manage Linux firewalls. It is
expected that this state module, and other system-specific firewall states, may
at some point be deprecated in favor of a more generic `firewall` state.

.. code-block:: yaml

    httpd:
      ip6tables.append:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      ip6tables.insert:
        - position: 1
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      ip6tables.delete:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      ip6tables.delete:
        - position: 1
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

# Import salt libs
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS


def __virtual__():
    '''
    Only load if the locale module is available in __salt__
    '''
    return 'ip6tables' if 'ip6tables.version' in __salt__ else False


def chain_present(name, table='filter'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Verify the chain is exist.

    name
        A user-defined chain name.

    table
        The table to own the chain.
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    chain_check = __salt__['ip6tables.check_chain'](table, name)
    if chain_check is True:
        ret['result'] = True
        ret['comment'] = ('ip6tables {0} chain is already exist in {1} table'
                          .format(name, table))
        return ret

    command = __salt__['ip6tables.new_chain'](table, name)
    if command is True:
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = ('ip6tables {0} chain in {1} table create success'
                          .format(name, table))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to create {0} chain in {1} table: {2}'.format(
            name,
            table,
            command.strip(),
        )
        return ret


def chain_absent(name, table='filter'):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Verify the chain is absent.
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    chain_check = __salt__['ip6tables.check_chain'](table, name)
    if not chain_check:
        ret['result'] = True
        ret['comment'] = ('ip6tables {0} chain is already absent in {1} table'
                          .format(name, table))
        return ret

    flush_chain = __salt__['ip6tables.flush'](table, name)
    if not flush_chain:
        command = __salt__['ip6tables.delete_chain'](table, name)
        if command is True:
            ret['changes'] = {'locale': name}
            ret['result'] = True
            ret['comment'] = ('ip6tables {0} chain in {1} table delete success'
                              .format(name, table))
        else:
            ret['result'] = False
            ret['comment'] = ('Failed to delete {0} chain in {1} table: {2}'
                              .format(name, table, command.strip()))
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush {0} chain in {1} table: {2}'.format(
            name,
            table,
            flush_chain.strip(),
        )
    return ret


def append(name, **kwargs):
    '''
    .. versionadded:: 0.17.0

    Append a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    All other arguments are passed in with the same name as the long option
    that would normally be used for ip6tables, with one exception: `--state` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    rule = __salt__['ip6tables.build_rule'](**kwargs)
    command = __salt__['ip6tables.build_rule'](full=True, command='A', **kwargs)
    if __salt__['ip6tables.check'](kwargs['table'],
                                  kwargs['chain'],
                                  rule) is True:
        ret['result'] = True
        ret['comment'] = 'ip6tables rule for {0} already set ({1})'.format(
            name,
            command.strip())
        return ret
    if __opts__['test']:
        ret['comment'] = 'ip6tables rule for {0} needs to be set ({1})'.format(
            name,
            command.strip())
        return ret
    if __salt__['ip6tables.append'](kwargs['table'], kwargs['chain'], rule):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set ip6tables rule for {0} to: {1}'.format(
            name,
            command.strip())
        if 'save' in kwargs:
            if kwargs['save']:
                __salt__['ip6tables.save'](filename=None)
                ret['comment'] = ('Set and Saved ip6tables rule for {0} to: '
                                  '{1}'.format(name, command.strip()))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to set ip6tables rule for {0}.\n'
                          'Attempted rule was {1}').format(
                              name,
                              command.strip())
        return ret


def insert(name, **kwargs):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Insert a rule into a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    All other arguments are passed in with the same name as the long option
    that would normally be used for ip6tables, with one exception: `--state` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    rule = __salt__['ip6tables.build_rule'](**kwargs)
    command = __salt__['ip6tables.build_rule'](full=True, command='I', **kwargs)
    if __salt__['ip6tables.check'](kwargs['table'],
                                  kwargs['chain'],
                                  rule) is True:
        ret['result'] = True
        ret['comment'] = 'ip6tables rule for {0} already set ({1})'.format(
            name,
            command.strip())
        return ret
    if __opts__['test']:
        ret['comment'] = 'ip6tables rule for {0} needs to be set ({1})'.format(
            name,
            command.strip())
        return ret
    if not __salt__['ip6tables.insert'](kwargs['table'], kwargs['chain'], kwargs['position'], rule):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set ip6tables rule for {0} to: {1}'.format(
            name,
            command.strip())
        if 'save' in kwargs:
            if kwargs['save']:
                __salt__['ip6tables.save'](filename=None)
                ret['comment'] = ('Set and Saved ip6tables rule for {0} to: '
                                  '{1}'.format(name, command.strip()))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to set ip6tables rule for {0}.\n'
                          'Attempted rule was {1}').format(
                              name,
                              command.strip())
        return ret


def delete(name, **kwargs):
    '''
    .. versionadded:: 0.17.0

    Delete a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    All other arguments are passed in with the same name as the long option
    that would normally be used for ip6tables, with one exception: `--state` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    rule = __salt__['ip6tables.build_rule'](**kwargs)
    command = __salt__['ip6tables.build_rule'](full=True, command='D', **kwargs)
    if not __salt__['ip6tables.check'](kwargs['table'],
                                  kwargs['chain'],
                                  rule) is True:
        ret['result'] = True
        ret['comment'] = 'ip6tables rule for {0} already absent ({1})'.format(
            name,
            command.strip())
        return ret
    if __opts__['test']:
        ret['comment'] = 'ip6tables rule for {0} needs to be deleted ({1})'.format(
            name,
            command.strip())
        return ret

    if 'position' in kwargs:
        result = __salt__['ip6tables.delete'](
                kwargs['table'],
                kwargs['chain'],
                position=kwargs['position'])
    else:
        result = __salt__['ip6tables.delete'](
                kwargs['table'],
                kwargs['chain'],
                rule=rule)

    if not result:
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Delete ip6tables rule for {1} {1}'.format(
            name,
            command.strip())
        if 'save' in kwargs:
            if kwargs['save']:
                __salt__['ip6tables.save'](filename=None)
                ret['comment'] = ('Deleted and Saved ip6tables rule for {0} '
                                  '{1}'.format(name, command.strip()))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to delete ip6tables rule for {0}.\n'
                          'Attempted rule was {1}').format(
                              name,
                              command.strip())
        return ret


def set_policy(name, **kwargs):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Sets the default policy for ip6tables firewall tables
    '''
    ret = {'name': name,
        'changes': {},
        'result': None,
        'comment': ''}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]

    if __salt__['ip6tables.get_policy'](
            kwargs['table'],
            kwargs['chain']) == kwargs['policy']:
        ret['result'] = True
        ret['comment'] = ('ip6tables default policy for {0} already set to {1}'
                          .format(kwargs['table'], kwargs['policy']))
        return ret

    if not __salt__['ip6tables.set_policy'](
            kwargs['table'],
            kwargs['chain'],
            kwargs['policy']):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set default policy for {0} to {1}'.format(
            kwargs['chain'],
            kwargs['policy'],
        )
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set ip6tables default policy'
        return ret


def flush(name, **kwargs):
    '''
    .. versionadded:: 2014.1.0 (Hydrogen)

    Flush current ip6tables state
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]

    if not 'chain' in kwargs:
        kwargs['chain'] = ''

    if not __salt__['ip6tables.flush'](kwargs['table'], kwargs['chain']):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Flush ip6tables rules in {0} table {1} chain'.format(
            kwargs['table'],
            kwargs['chain'],
        )
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush ip6tables rules'
        return ret

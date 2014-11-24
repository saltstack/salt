# -*- coding: utf-8 -*-
'''
Management of nftables
======================

This is an nftables-specific module designed to manage Linux firewalls. It is
expected that this state module, and other system-specific firewall states, may
at some point be deprecated in favor of a more generic `firewall` state.

.. code-block:: yaml

    httpd:
      nftables.append:
        - table: filter
        - chain: input
        - jump: accept
        - match: state
        - connstate: new
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.append:
        - table: filter
        - family: ipv6
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.insert:
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
      nftables.insert:
        - position: 1
        - table: filter
        - family: ipv6
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      nftables.delete:
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
      nftables.delete:
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
      nftables.delete:
        - table: filter
        - family: ipv6
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True


'''
from __future__ import absolute_import

# Import salt libs
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS


def __virtual__():
    '''
    Only load if the locale module is available in __salt__
    '''
    return 'nftables' if 'nftables.version' in __salt__ else False


def chain_present(name, table='filter', table_type=None, hook=None, priority=None, family='ipv4'):
    '''
    .. versionadded:: 2014.7.0

    Verify the chain is exist.

    name
        A user-defined chain name.

    table
        The table to own the chain.

    family
        Networking family, either ipv4 or ipv6
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    chain_check = __salt__['nftables.check_chain'](table, name, family=family)
    if chain_check is True:
        ret['result'] = True
        ret['comment'] = ('nftables {0} chain is already exist in {1} table for {2}'
                          .format(name, table, family))
        return ret

    command = __salt__['nftables.new_chain'](
            table,
            name,
            table_type=table_type,
            hook=hook,
            priority=priority,
            family=family
    )

    if command is True:
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = ('nftables {0} chain in {1} table create success for {2}'
                          .format(name, table, family))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to create {0} chain in {1} table: {2} for {3}'.format(
            name,
            table,
            command.strip(),
            family
        )
        return ret


def chain_absent(name, table='filter', family='ipv4'):
    '''
    .. versionadded:: 2014.7.0

    Verify the chain is absent.

    family
        Networking family, either ipv4 or ipv6
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    chain_check = __salt__['nftables.check_chain'](table, name, family)
    if not chain_check:
        ret['result'] = True
        ret['comment'] = ('nftables {0} chain is already absent in {1} table for {2}'
                          .format(name, table, family))
        return ret

    flush_chain = __salt__['nftables.flush'](table, name, family)
    if flush_chain:
        command = __salt__['nftables.delete_chain'](table, name, family)
        if command is True:
            ret['changes'] = {'locale': name}
            ret['result'] = True
            ret['comment'] = ('nftables {0} chain in {1} table delete success for {2}'
                              .format(name, table, family))
        else:
            ret['result'] = False
            ret['comment'] = ('Failed to delete {0} chain in {1} table: {2} for {3}'
                              .format(name, table, command.strip(), family))
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush {0} chain in {1} table: {2} for {3}'.format(
            name,
            table,
            flush_chain.strip(),
            family
        )
    return ret


def append(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: 0.17.0

    Append a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    family
        Network family, ipv4 or ipv6.

    All other arguments are passed in with the same name as the long option
    that would normally be used for nftables, with one exception: `--state` is
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
    rule = __salt__['nftables.build_rule'](family=family, **kwargs)
    command = __salt__['nftables.build_rule'](full=True, family=family, command='add', **kwargs)

    if __salt__['nftables.check'](kwargs['table'],
                                  kwargs['chain'],
                                  rule,
                                  family) is True:
        ret['result'] = True
        ret['comment'] = 'nftables rule for {0} already set ({1}) for {2}'.format(
            name,
            command.strip(),
            family)
        return ret
    if __opts__['test']:
        ret['comment'] = 'nftables rule for {0} needs to be set ({1}) for {2}'.format(
            name,
            command.strip(),
            family)
        return ret
    if __salt__['nftables.append'](kwargs['table'], kwargs['chain'], rule, family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set nftables rule for {0} to: {1} for {2}'.format(
            name,
            command.strip(),
            family)
        if 'save' in kwargs:
            if kwargs['save']:
                __salt__['nftables.save'](filename=None, family=family)
                ret['comment'] = ('Set and Saved nftables rule for {0} to: '
                                  '{1} for {2}'.format(name, command.strip(), family))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to set nftables rule for {0}.\n'
                          'Attempted rule was {1} for {2}').format(
                                  name,
                                  command.strip(), family)
        return ret


def insert(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Insert a rule into a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    family
        Networking family, either ipv4 or ipv6

    All other arguments are passed in with the same name as the long option
    that would normally be used for nftables, with one exception: `--state` is
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
    rule = __salt__['nftables.build_rule'](family=family, **kwargs)
    command = __salt__['nftables.build_rule'](full=True, family=family, command='insert', **kwargs)
    if __salt__['nftables.check'](kwargs['table'],
                                  kwargs['chain'],
                                  rule,
                                  family) is True:
        ret['result'] = True
        ret['comment'] = 'nftables rule for {0} already set for {1} ({2})'.format(
            name,
            family,
            command.strip())
        return ret
    if __opts__['test']:
        ret['comment'] = 'nftables rule for {0} needs to be set for {1} ({2})'.format(
            name,
            family,
            command.strip())
        return ret
    if __salt__['nftables.insert'](kwargs['table'], kwargs['chain'], kwargs['position'], rule, family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set nftables rule for {0} to: {1} for {2}'.format(
            name,
            command.strip(),
            family)
        if 'save' in kwargs:
            if kwargs['save']:
                __salt__['nftables.save'](filename=None, family=family)
                ret['comment'] = ('Set and Saved nftables rule for {0} to: '
                                  '{1} for {2}'.format(name, command.strip(), family))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to set nftables rule for {0}.\n'
                          'Attempted rule was {1}').format(
                              name,
                              command.strip())
        return ret


def delete(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Delete a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    family
        Networking family, either ipv4 or ipv6

    All other arguments are passed in with the same name as the long option
    that would normally be used for nftables, with one exception: `--state` is
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
    rule = __salt__['nftables.build_rule'](family=family, **kwargs)
    command = __salt__['nftables.build_rule'](full=True, family=family, command='D', **kwargs)
    if not __salt__['nftables.check'](kwargs['table'],
                                  kwargs['chain'],
                                  rule,
                                  family) is True:
        ret['result'] = True
        ret['comment'] = 'nftables rule for {0} already absent for {1} ({2})'.format(
            name,
            family,
            command.strip())
        return ret
    if __opts__['test']:
        ret['comment'] = 'nftables rule for {0} needs to be deleted for {1} ({2})'.format(
            name,
            family,
            command.strip())
        return ret

    if 'position' in kwargs:
        result = __salt__['nftables.delete'](
                kwargs['table'],
                kwargs['chain'],
                family=family,
                position=kwargs['position'])
    else:
        result = __salt__['nftables.delete'](
                kwargs['table'],
                kwargs['chain'],
                family=family,
                rule=rule)

    if result:
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Delete nftables rule for {0} {1}'.format(
            name,
            command.strip())
        if 'save' in kwargs:
            if kwargs['save']:
                __salt__['nftables.save'](filename=None, family=family)
                ret['comment'] = ('Deleted and Saved nftables rule for {0} for {1}'
                                  '{2}'.format(name, command.strip(), family))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to delete nftables rule for {0}.\n'
                          'Attempted rule was {1}').format(
                              name,
                              command.strip())
        return ret


def flush(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Flush current nftables state

    family
        Networking family, either ipv4 or ipv6

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]

    if 'table' not in kwargs:
        kwargs['table'] = 'filter'

    if not __salt__['nftables.check_table'](kwargs['table'], family=family):
        ret['result'] = False
        ret['comment'] = 'Failed to flush table {0} in family {1}, table does not exist.'.format(
            kwargs['table'],
            family
        )
        return ret

    if 'chain' not in kwargs:
        kwargs['chain'] = ''
    else:
        if not __salt__['nftables.check_chain'](kwargs['table'], kwargs['chain'], family=family):
            ret['result'] = False
            ret['comment'] = 'Failed to flush chain {0} in table {1} in family {2}, chain does not exist.'.format(
                kwargs['chain'],
                kwargs['table'],
                family
            )
            return ret

    if __salt__['nftables.flush'](kwargs['table'], kwargs['chain'], family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Flush nftables rules in {0} table {1} chain {2} family'.format(
            kwargs['table'],
            kwargs['chain'],
            family
        )
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush nftables rules'
        return ret

# -*- coding: utf-8 -*-
'''
Management of iptables
======================

This is an iptables-specific module designed to manage Linux firewalls. It is
expected that this state module, and other system-specific firewall states, may
at some point be deprecated in favor of a more generic ``firewall`` state.

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

    httpd:
      iptables.append:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match:
            - state
            - comment
        - comment: "Allow HTTP"
        - connstate: NEW
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      iptables.append:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match:
            - state
            - comment
        - comment: "Allow HTTP"
        - connstate: NEW
        - source: '127.0.0.1'
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    .. Invert Rule
    httpd:
      iptables.append:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match:
            - state
            - comment
        - comment: "Allow HTTP"
        - connstate: NEW
        - source: '! 127.0.0.1'
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      iptables.append:
        - table: filter
        - chain: INPUT
        - jump: ACCEPT
        - match:
            - state
            - comment
        - comment: "Allow HTTP"
        - connstate: NEW
        - source: 'not 127.0.0.1'
        - dport: 80
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      iptables.append:
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
      iptables.append:
        - table: filter
        - family: ipv4
        - chain: INPUT
        - jump: ACCEPT
        - match: state
        - connstate: NEW
        - dports:
            - 80
            - 443
        - proto: tcp
        - sport: 1025:65535
        - save: True

    httpd:
      iptables.insert:
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
      iptables.insert:
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
      iptables.delete:
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
      iptables.delete:
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
      iptables.delete:
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

    default to accept:
      iptables.set_policy:
        - chain: INPUT
        - policy: ACCEPT

.. note::

    Various functions of the ``iptables`` module use the ``--check`` option. If
    the version of ``iptables`` on the target system does not include this
    option, an alternate version of this check will be performed using the
    output of iptables-save. This may have unintended consequences on legacy
    releases of ``iptables``.
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import salt libs
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS


def __virtual__():
    '''
    Only load if the locale module is available in __salt__
    '''
    return 'iptables.version' in __salt__


def chain_present(name, table='filter', family='ipv4'):
    '''
    .. versionadded:: 2014.1.0

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

    chain_check = __salt__['iptables.check_chain'](table, name, family)
    if chain_check is True:
        ret['result'] = True
        ret['comment'] = ('iptables {0} chain is already exist in {1} table for {2}'
                          .format(name, table, family))
        return ret

    if __opts__['test']:
        ret['comment'] = 'iptables {0} chain in {1} table needs to be set for {2}'.format(
            name,
            table,
            family)
        return ret
    command = __salt__['iptables.new_chain'](table, name, family)
    if command is True:
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = ('iptables {0} chain in {1} table create success for {2}'
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
    .. versionadded:: 2014.1.0

    Verify the chain is absent.

    table
        The table to remove the chain from

    family
        Networking family, either ipv4 or ipv6
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    chain_check = __salt__['iptables.check_chain'](table, name, family)
    if not chain_check:
        ret['result'] = True
        ret['comment'] = ('iptables {0} chain is already absent in {1} table for {2}'
                          .format(name, table, family))
        return ret
    if __opts__['test']:
        ret['comment'] = 'iptables {0} chain in {1} table needs to be removed {2}'.format(
            name,
            table,
            family)
        return ret
    flush_chain = __salt__['iptables.flush'](table, name, family)
    if not flush_chain:
        command = __salt__['iptables.delete_chain'](table, name, family)
        if command is True:
            ret['changes'] = {'locale': name}
            ret['result'] = True
            ret['comment'] = ('iptables {0} chain in {1} table delete success for {2}'
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


def append(name, table='filter', family='ipv4', **kwargs):
    '''
    .. versionadded:: 0.17.0

    Add a rule to the end of the specified chain.

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    table
        The table that owns the chain which should be modified

    family
        Network family, ipv4 or ipv6.

    All other arguments are passed in with the same name as the long option
    that would normally be used for iptables, with one exception: ``--state`` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).

    Jump options that doesn't take arguments should be passed in with an empty
    string.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if 'rules' in kwargs:
        ret['changes']['locale'] = []
        comments = []
        save = False
        for rule in kwargs['rules']:
            if 'rules' in rule:
                del rule['rules']
            if '__agg__' in rule:
                del rule['__agg__']
            if 'save' in rule and rule['save']:
                save = True
                if rule['save'] is not True:
                    save_file = rule['save']
                else:
                    save_file = True
                rule['save'] = False
            _ret = append(**rule)
            if 'locale' in _ret['changes']:
                ret['changes']['locale'].append(_ret['changes']['locale'])
            comments.append(_ret['comment'])
            ret['result'] = _ret['result']
        if save:
            if save_file is True:
                save_file = None
            __salt__['iptables.save'](save_file, family=family)
        if not ret['changes']['locale']:
            del ret['changes']['locale']
        ret['comment'] = '\n'.join(comments)
        return ret

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    kwargs['name'] = name
    kwargs['table'] = table
    rule = __salt__['iptables.build_rule'](family=family, **kwargs)
    command = __salt__['iptables.build_rule'](full='True', family=family, command='A', **kwargs)
    if __salt__['iptables.check'](table,
                                  kwargs['chain'],
                                  rule,
                                  family) is True:
        ret['result'] = True
        ret['comment'] = 'iptables rule for {0} already set ({1}) for {2}'.format(
            name,
            command.strip(),
            family)
        if 'save' in kwargs and kwargs['save']:
            if kwargs['save'] is not True:
                filename = kwargs['save']
            else:
                filename = None
            saved_rules = __salt__['iptables.get_saved_rules'](family=family)
            _rules = __salt__['iptables.get_rules'](family=family)
            __rules = []
            for table in _rules:
                for chain in _rules[table]:
                    __rules.append(_rules[table][chain].get('rules'))
            __saved_rules = []
            for table in saved_rules:
                for chain in saved_rules[table]:
                    __saved_rules.append(saved_rules[table][chain].get('rules'))
            # Only save if rules in memory are different than saved rules
            if __rules != __saved_rules:
                out = __salt__['iptables.save'](filename, family=family)
                ret['comment'] += ('\nSaved iptables rule {0} for {1}\n'
                                   '{2}\n{3}').format(name, family, command.strip(), out)
        return ret
    if __opts__['test']:
        ret['comment'] = 'iptables rule for {0} needs to be set ({1}) for {2}'.format(
            name,
            command.strip(),
            family)
        return ret
    if __salt__['iptables.append'](table, kwargs['chain'], rule, family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set iptables rule for {0} to: {1} for {2}'.format(
            name,
            command.strip(),
            family)
        if 'save' in kwargs:
            if kwargs['save']:
                if kwargs['save'] is not True:
                    filename = kwargs['save']
                else:
                    filename = None
                out = __salt__['iptables.save'](filename, family=family)
                ret['comment'] = ('Set and saved iptables rule {0} for {1}\n'
                                  '{2}\n{3}').format(name, family, command.strip(), out)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to set iptables rule for {0}.\n'
                          'Attempted rule was {1} for {2}').format(
                              name,
                              command.strip(), family)
        return ret


def insert(name, table='filter', family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.1.0

    Insert a rule into a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    table
        The table that owns the chain that should be modified

    family
        Networking family, either ipv4 or ipv6

    position
        The numerical representation of where the rule should be inserted into
        the chain. Note that ``-1`` is not a supported position value.

    All other arguments are passed in with the same name as the long option
    that would normally be used for iptables, with one exception: ``--state`` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).

    Jump options that doesn't take arguments should be passed in with an empty
    string.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if 'rules' in kwargs:
        ret['changes']['locale'] = []
        comments = []
        save = False
        for rule in kwargs['rules']:
            if 'rules' in rule:
                del rule['rules']
            if '__agg__' in rule:
                del rule['__agg__']
            if 'save' in rule and rule['save']:
                save = True
                if rule['save'] is not True:
                    save_file = rule['save']
                else:
                    save_file = True
                rule['save'] = False
            _ret = insert(**rule)
            if 'locale' in _ret['changes']:
                ret['changes']['locale'].append(_ret['changes']['locale'])
            comments.append(_ret['comment'])
            ret['result'] = _ret['result']
        if save:
            if save_file is True:
                save_file = None
            __salt__['iptables.save'](save_file, family=family)
        if not ret['changes']['locale']:
            del ret['changes']['locale']
        ret['comment'] = '\n'.join(comments)
        return ret

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    kwargs['name'] = name
    kwargs['table'] = table
    rule = __salt__['iptables.build_rule'](family=family, **kwargs)
    command = __salt__['iptables.build_rule'](full=True, family=family, command='I', **kwargs)
    if __salt__['iptables.check'](table,
                                  kwargs['chain'],
                                  rule,
                                  family) is True:
        ret['result'] = True
        ret['comment'] = 'iptables rule for {0} already set for {1} ({2})'.format(
            name,
            family,
            command.strip())
        if 'save' in kwargs and kwargs['save']:
            if kwargs['save'] is not True:
                filename = kwargs['save']
            else:
                filename = None
            saved_rules = __salt__['iptables.get_saved_rules'](family=family)
            _rules = __salt__['iptables.get_rules'](family=family)
            __rules = []
            for table in _rules:
                for chain in _rules[table]:
                    __rules.append(_rules[table][chain].get('rules'))
            __saved_rules = []
            for table in saved_rules:
                for chain in saved_rules[table]:
                    __saved_rules.append(saved_rules[table][chain].get('rules'))
            # Only save if rules in memory are different than saved rules
            if __rules != __saved_rules:
                out = __salt__['iptables.save'](filename, family=family)
                ret['comment'] += ('\nSaved iptables rule {0} for {1}\n'
                                   '{2}\n{3}').format(name, family, command.strip(), out)
        return ret
    if __opts__['test']:
        ret['comment'] = 'iptables rule for {0} needs to be set for {1} ({2})'.format(
            name,
            family,
            command.strip())
        return ret
    if not __salt__['iptables.insert'](table, kwargs['chain'], kwargs['position'], rule, family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set iptables rule for {0} to: {1} for {2}'.format(
            name,
            command.strip(),
            family)
        if 'save' in kwargs:
            if kwargs['save']:
                out = __salt__['iptables.save'](filename=None, family=family)
                ret['comment'] = ('Set and saved iptables rule {0} for {1}\n'
                                  '{2}\n{3}').format(name, family, command.strip(), out)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to set iptables rule for {0}.\n'
                          'Attempted rule was {1}').format(
                              name,
                              command.strip())
        return ret


def delete(name, table='filter', family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.1.0

    Delete a rule to a chain

    name
        A user-defined name to call this rule by in another part of a state or
        formula. This should not be an actual rule.

    table
        The table that owns the chain that should be modified

    family
        Networking family, either ipv4 or ipv6

    All other arguments are passed in with the same name as the long option
    that would normally be used for iptables, with one exception: ``--state`` is
    specified as `connstate` instead of `state` (not to be confused with
    `ctstate`).

    Jump options that doesn't take arguments should be passed in with an empty
    string.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if 'rules' in kwargs:
        ret['changes']['locale'] = []
        comments = []
        save = False
        for rule in kwargs['rules']:
            if 'rules' in rule:
                del rule['rules']
            if '__agg__' in rule:
                del rule['__agg__']
            if 'save' in rule and rule['save']:
                if rule['save'] is not True:
                    save_file = rule['save']
                else:
                    save_file = True
                rule['save'] = False
            _ret = delete(**rule)
            if 'locale' in _ret['changes']:
                ret['changes']['locale'].append(_ret['changes']['locale'])
            comments.append(_ret['comment'])
            ret['result'] = _ret['result']
        if save:
            if save_file is True:
                save_file = None
            __salt__['iptables.save'](save_file, family=family)
        if not ret['changes']['locale']:
            del ret['changes']['locale']
        ret['comment'] = '\n'.join(comments)
        return ret

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]
    kwargs['name'] = name
    kwargs['table'] = table
    rule = __salt__['iptables.build_rule'](family=family, **kwargs)
    command = __salt__['iptables.build_rule'](full=True, family=family, command='D', **kwargs)

    if not __salt__['iptables.check'](table,
                                      kwargs['chain'],
                                      rule,
                                      family) is True:
        if 'position' not in kwargs:
            ret['result'] = True
            ret['comment'] = 'iptables rule for {0} already absent for {1} ({2})'.format(
                name,
                family,
                command.strip())
            return ret
    if __opts__['test']:
        ret['comment'] = 'iptables rule for {0} needs to be deleted for {1} ({2})'.format(
            name,
            family,
            command.strip())
        return ret

    if 'position' in kwargs:
        result = __salt__['iptables.delete'](
                table,
                kwargs['chain'],
                family=family,
                position=kwargs['position'])
    else:
        result = __salt__['iptables.delete'](
                table,
                kwargs['chain'],
                family=family,
                rule=rule)

    if not result:
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Delete iptables rule for {0} {1}'.format(
            name,
            command.strip())
        if 'save' in kwargs:
            if kwargs['save']:
                out = __salt__['iptables.save'](filename=None, family=family)
                ret['comment'] = ('Deleted and saved iptables rule {0} for {1}\n'
                                  '{2}\n{3}').format(name, family, command.strip(), out)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to delete iptables rule for {0}.\n'
                          'Attempted rule was {1}').format(
                              name,
                              command.strip())
        return ret


def set_policy(name, table='filter', family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.1.0

    Sets the default policy for iptables firewall tables

    table
        The table that owns the chain that should be modified

    family
        Networking family, either ipv4 or ipv6

    policy
        The requested table policy

    '''
    ret = {'name': name,
        'changes': {},
        'result': None,
        'comment': ''}

    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in kwargs:
            del kwargs[ignore]

    if __salt__['iptables.get_policy'](
            table,
            kwargs['chain'],
            family) == kwargs['policy']:
        ret['result'] = True
        ret['comment'] = ('iptables default policy for chain {0} on table {1} for {2} already set to {3}'
                          .format(kwargs['chain'], table, family, kwargs['policy']))
        return ret
    if __opts__['test']:
        ret['comment'] = 'iptables default policy for chain {0} on table {1} for {2} needs to be set to {3}'.format(
            kwargs['chain'],
            table,
            family,
            kwargs['policy']
        )
        return ret
    if not __salt__['iptables.set_policy'](
            table,
            kwargs['chain'],
            kwargs['policy'],
            family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Set default policy for {0} to {1} family {2}'.format(
            kwargs['chain'],
            kwargs['policy'],
            family
        )
        if 'save' in kwargs:
            if kwargs['save']:
                __salt__['iptables.save'](filename=None, family=family)
                ret['comment'] = 'Set and saved default policy for {0} to {1} family {2}'.format(
                    kwargs['chain'],
                    kwargs['policy'],
                    family
                )
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set iptables default policy'
        return ret


def flush(name, table='filter', family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.1.0

    Flush current iptables state

    table
        The table that owns the chain that should be modified

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

    if 'chain' not in kwargs:
        kwargs['chain'] = ''
    if __opts__['test']:
        ret['comment'] = 'iptables rules in {0} table {1} chain {2} family needs to be flushed'.format(
            name,
            table,
            family)
        return ret
    if not __salt__['iptables.flush'](table, kwargs['chain'], family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Flush iptables rules in {0} table {1} chain {2} family'.format(
            table,
            kwargs['chain'],
            family
        )
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush iptables rules'
        return ret


def mod_aggregate(low, chunks, running):
    '''
    The mod_aggregate function which looks up all rules in the available
    low chunks and merges them into a single rules ref in the present low data
    '''
    rules = []
    agg_enabled = [
            'append',
            'insert',
    ]
    if low.get('fun') not in agg_enabled:
        return low
    for chunk in chunks:
        tag = __utils__['state.gen_tag'](chunk)
        if tag in running:
            # Already ran the iptables state, skip aggregation
            continue
        if chunk.get('state') == 'iptables':
            if '__agg__' in chunk:
                continue
            # Check for the same function
            if chunk.get('fun') != low.get('fun'):
                continue

            if chunk not in rules:
                rules.append(chunk)
                chunk['__agg__'] = True

    if rules:
        if 'rules' in low:
            low['rules'].extend(rules)
        else:
            low['rules'] = rules
    return low

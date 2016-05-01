# -*- coding: utf-8 -*-
'''
Management of ipsets
======================

This is an ipset-specific module designed to manage IPSets for use
in IPTables Firewalls.

.. code-block:: yaml

    setname:
      ipset.set_present:
        - set_type: bitmap:ip
        - range: 192.168.0.0/16
        - comment: True

    setname:
      ipset.set_absent:
        - set_type: bitmap:ip
        - range: 192.168.0.0/16
        - comment: True

    setname_entries:
      ipset.present:
        - set_name: setname
        - entry: 192.168.0.3
        - comment: Hello
        - require:
            - ipset: baz

    setname_entries:
      ipset.present:
        - set_name: setname
        - entry:
            - 192.168.0.3
            - 192.168.1.3
        - comment: Hello
        - require:
            - ipset: baz

    setname_entries:
      ipset.absent:
        - set_name: setname
        - entry:
            - 192.168.0.3
            - 192.168.1.3
        - comment: Hello
        - require:
            - ipset: baz

    setname:
      ipset.flush:

'''
from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the ipset module is available in __salt__
    '''
    return 'ipset.version' in __salt__


def set_present(name, set_type, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Verify the set exists.

    name
        A user-defined set name.

    set_type
        The type for the set.

    family
        Networking family, either ipv4 or ipv6
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    set_check = __salt__['ipset.check_set'](name)
    if set_check is True:
        ret['result'] = True
        ret['comment'] = ('ipset set {0} already exists for {1}'
                          .format(name, family))
        return ret

    if __opts__['test']:
        ret['comment'] = 'ipset set {0} would be added for {1}'.format(
            name,
            family)
        return ret
    command = __salt__['ipset.new_set'](name, set_type, family, **kwargs)
    if command is True:
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = ('ipset set {0} created successfully for {1}'
                          .format(name, family))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to create set {0} for {2}: {1}'.format(
            name,
            command.strip(),
            family
        )
        return ret


def set_absent(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Verify the set is absent.

    family
        Networking family, either ipv4 or ipv6
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    set_check = __salt__['ipset.check_set'](name, family)
    if not set_check:
        ret['result'] = True
        ret['comment'] = ('ipset set {0} for {1} is already absent'
                          .format(name, family))
        return ret
    if __opts__['test']:
        ret['comment'] = 'ipset set {0} for {1} would be removed'.format(
            name,
            family)
        return ret
    flush_set = __salt__['ipset.flush'](name, family)
    if flush_set:
        command = __salt__['ipset.delete_set'](name, family)
        if command is True:
            ret['changes'] = {'locale': name}
            ret['result'] = True
            ret['comment'] = ('ipset set {0} deleted successfully for family {1}'
                              .format(name, family))
        else:
            ret['result'] = False
            ret['comment'] = ('Failed to delete set {0} for {2}: {1}'
                              .format(name, command.strip(), family))
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush set {0} for {2}: {1}'.format(
            name,
            flush_set.strip(),
            family
        )
    return ret


def present(name, entry=None, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Append a entry to a set

    name
        A user-defined name to call this entry by in another part of a state or
        formula. This should not be an actual entry.

    entry
        A single entry to add to a set or a list of entries to add to a set

    family
        Network family, ipv4 or ipv6.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    test_flag = False

    if not entry:
        ret['result'] = False
        ret['comment'] = ('ipset entry must be specified')
        return ret

    entries = []
    if isinstance(entry, list):
        entries = entry
    else:
        entries.append(entry)

    for entry in entries:
        _entry = '{0}'.format(entry)
        if 'timeout' in kwargs:
            if 'comment' in _entry:
                _entry = '{0} timeout {1} {2} {3}'.format(entry.split()[0], kwargs['timeout'], entry.split()[1], entry.split()[2])
            else:
                _entry = '{0} timeout {1}'.format(entry.split()[0], kwargs['timeout'])

        if __salt__['ipset.check'](kwargs['set_name'],
                                   _entry,
                                   family) is True:
            if test_flag is False:
                ret['result'] = True
            ret['comment'] += 'entry for {0} already in set {1} for {2}\n'.format(
                entry,
                kwargs['set_name'],
                family)
        else:
            if __opts__['test']:
                test_flag = True
                ret['result'] = None
                ret['comment'] += 'entry {0} would be added to set {1} for family {2}\n'.format(
                    entry,
                    kwargs['set_name'],
                    family)
            else:
                command = __salt__['ipset.add'](kwargs['set_name'], entry, family, **kwargs)
                if 'Error' not in command:
                    ret['changes'] = {'locale': name}
                    ret['result'] = True
                    ret['comment'] += 'entry {0} added to set {1} for family {2}\n'.format(
                        _entry,
                        kwargs['set_name'],
                        family)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Failed to add to entry {1} to set {0} for family {2}.\n{3}'.format(
                            kwargs['set_name'],
                            _entry, family, command)
    return ret


def absent(name, entry=None, entries=None, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Remove a entry or entries from a chain

    name
        A user-defined name to call this entry by in another part of a state or
        formula. This should not be an actual entry.

    family
        Network family, ipv4 or ipv6.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if not entry:
        ret['result'] = False
        ret['comment'] = ('ipset entry must be specified')
        return ret

    entries = []
    if isinstance(entry, list):
        entries = entry
    else:
        entries.append(entry)

    for entry in entries:
        _entry = '{0}'.format(entry)

        if 'comment' in kwargs:
            _entry = '{0} comment "{1}"'.format(entry, kwargs['comment'])

        log.debug('_entry {0}'.format(_entry))
        if not __salt__['ipset.check'](kwargs['set_name'],
                                      _entry,
                                      family) is True:
            ret['result'] = True
            ret['comment'] += 'ipset entry for {0} not present in set {1} for {2}\n'.format(
                _entry,
                kwargs['set_name'],
                family)
        else:

            if __opts__['test']:
                ret['comment'] += 'ipset entry {0} would be removed from set {1} for {2}\n'.format(
                    entry,
                    kwargs['set_name'],
                    family)
            else:
                command = __salt__['ipset.delete'](kwargs['set_name'], entry, family, **kwargs)
                if 'Error' not in command:
                    ret['changes'] = {'locale': name}
                    ret['result'] = True
                    ret['comment'] += 'ipset entry {1} removed from set {0} for {2}\n'.format(
                        kwargs['set_name'],
                        _entry,
                        family)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Failed to delete ipset entry from set {0} for {2}. ' \
                                     'Attempted entry was {1}.\n' \
                                     '{3}\n'.format(kwargs['set_name'], _entry, family, command)
    return ret


def flush(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Flush current ipset set

    family
        Networking family, either ipv4 or ipv6

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    set_check = __salt__['ipset.check_set'](name)
    if set_check is False:
        ret['result'] = False
        ret['comment'] = ('ipset set {0} does not exist for {1}'
                          .format(name, family))
        return ret

    if __opts__['test']:
        ret['comment'] = 'ipset entries in set {0} for {1} would be flushed'.format(
            name,
            family)
        return ret
    if __salt__['ipset.flush'](name, family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Flushed ipset entries from set {0} for {1}'.format(
            name,
            family
        )
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush ipset entries from set {0} for {1}' \
                         ''.format(name, family)
        return ret

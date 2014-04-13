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

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the ipset module is available in __salt__
    '''
    return 'ipset.version' in __salt__


def set_present(name, set_type, family='ipv4', **kwargs):
    '''
    .. versionadded:: Helium

    Verify the chain is exist.

    name
        A user-defined set name.

    set_type
        The type for the set

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
        ret['comment'] = ('ipset set {0} already exist for {1}'
                          .format(name, family))
        return ret

    if __opts__['test']:
        ret['comment'] = 'ipset set {0} needs to added for {1}'.format(
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
        ret['comment'] = 'Failed to create {0} set: {1} for {2}'.format(
            name,
            command.strip(),
            family
        )
        return ret


def set_absent(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: Helium

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
        ret['comment'] = ('ipset set {0} is already absent for family {1}'
                          .format(name, family))
        return ret
    if __opts__['test']:
        ret['comment'] = 'ipset set {0} needs to be removed family {1}'.format(
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
            ret['comment'] = ('Failed to delete {0} set: {1} for {2}'
                              .format(name, command.strip(), family))
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush {0} set: {1} for {2}'.format(
            name,
            flush_set.strip(),
            family
        )
    return ret


def present(name, entry=None, family='ipv4', **kwargs):
    '''
    .. versionadded:: Helium

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

        if __salt__['ipset.check'](kwargs['set_name'],
                                   _entry,
                                   family) is True:
            ret['result'] = True
            ret['comment'] += 'entry for {0} already in set ({1}) for {2}\n'.format(
                entry,
                kwargs['set_name'],
                family)
        else:
            if __opts__['test']:
                ret['comment'] += 'entry {0} needs to be added to set {1} for family {2}\n'.format(
                    entry,
                    kwargs['set_name'],
                    family)
            else:
                command = __salt__['ipset.add'](kwargs['set_name'], entry, family, **kwargs)
                if not 'Error' in command:
                    ret['changes'] = {'locale': name}
                    ret['result'] = True
                    ret['comment'] += 'entry {0} added to set {1} for family {2}\n'.format(
                        kwargs['set_name'],
                        _entry,
                        family)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Failed to add to entry {1} to set {0} for family {2}.\n{3}'.format(
                            kwargs['set_name'],
                            _entry, family, command)
    return ret


def absent(name, entry=None, entries=None, family='ipv4', **kwargs):
    '''
    .. versionadded:: Helium

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
            ret['comment'] += 'ipset entry for {0} not present in set ({1}) for {2}\n'.format(
                _entry,
                kwargs['set_name'],
                family)
        else:

            if __opts__['test']:
                ret['comment'] += 'ipset entry {0} needs to removed from set {1} for family {2}\n'.format(
                    entry,
                    kwargs['set_name'],
                    family)
            else:
                command = __salt__['ipset.delete'](kwargs['set_name'], entry, family, **kwargs)
                if not 'Error' in command:
                    ret['changes'] = {'locale': name}
                    ret['result'] = True
                    ret['comment'] += 'ipset entry {1} for set {0} removed for family {2}\n'.format(
                        kwargs['set_name'],
                        _entry,
                        family)
                else:
                    ret['result'] = False
                    ret['comment'] = ('Failed to delete from ipset entry for set {0}. '
                                      'Attempted entry was {1} for {2}.\n{3}\n').format(
                                          kwargs['set_name'],
                                          _entry, family, command)
            return ret
    return ret


def flush(name, family='ipv4', **kwargs):
    '''
    .. versionadded:: Helium

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
        ret['comment'] = 'ipset entries in set {0} family {1} needs to be flushed'.format(
            name,
            family)
        return ret
    if __salt__['ipset.flush'](name, family):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Flush ipset entries in set {0} family {1}'.format(
            name,
            family
        )
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to flush ipset entries'
        return ret

# -*- coding: utf-8 -*-
'''
Management of Gentoo make.conf
==============================

A state module to manage Gentoo's ``make.conf`` file

.. code-block:: yaml

    makeopts:
      makeconf.present:
        - value: '-j3'
'''


def __virtual__():
    '''
    Only load if the makeconf module is available in __salt__
    '''
    return 'makeconf' if 'makeconf.get_var' in __salt__ else False


def _make_set(var):
    '''
    Force var to be a set
    '''
    if var is None:
        return set()
    if not isinstance(var, list):
        if isinstance(var, str):
            var = var.split()
        else:
            var = list(var)
    return set(var)


def present(name, value=None, contains=None, excludes=None):
    '''
    Verify that the variable is in the ``make.conf`` and has the provided
    settings. If value is set, contains and excludes will be ignored.

    name
        The variable name. This will automatically be converted to upper
        case since variables in ``make.conf`` are in upper case

    value
        Enforce that the value of the variable is set to the provided value

    contains
        Enforce that the value of the variable contains the provided value

    excludes
        Enforce that the value of the variable does not contain the provided
        value.
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Make name all Uppers since make.conf uses all Upper vars
    upper_name = name.upper()

    old_value = __salt__['makeconf.get_var'](upper_name)

    # If only checking if variable is present allows for setting the
    # variable outside of salt states, but the state can still ensure
    # that is exists
    if value is None and contains is None and excludes is None:
        # variable is present
        if old_value is not None:
            msg = 'Variable {0} is already present in make.conf'
            ret['comment'] = msg.format(name)
        else:
            if __opts__['test']:
                msg = 'Variable {0} is to be set in make.conf'
                ret['comment'] = msg.format(name)
                ret['result'] = None
            else:
                changes = __salt__['makeconf.set_var'](upper_name, '')

                # If failed to be set
                if changes[upper_name]['new'] is None:
                    msg = 'Variable {0} failed to be set in make.conf'
                    ret['comment'] = msg.format(name)
                    ret['result'] = False
                else:
                    msg = 'Variable {0} set in make.conf'
                    ret['comment'] = msg.format(name)

    elif value is not None:
        # variable is present and is set to value
        if old_value is not None and old_value == value:
            msg = 'Variable {0} is already "{1}" in make.conf'
            ret['comment'] = msg.format(name, value)
        else:
            if __opts__['test']:
                msg = 'Variable {0} is to be set to "{1}" in make.conf'
                ret['comment'] = msg.format(name, value)
                ret['result'] = None
            else:
                changes = __salt__['makeconf.set_var'](upper_name, value)

                # If failed to be set
                new_value = __salt__['makeconf.get_var'](upper_name)
                if new_value is None or new_value != value:
                    msg = 'Variable {0} failed to be set in make.conf'
                    ret['comment'] = msg.format(name)
                    ret['result'] = False
                else:
                    msg = 'Variable {0} is set in make.conf'
                    ret['changes'] = changes
                    ret['comment'] = msg.format(name)

    elif contains is not None or excludes is not None:
        # Make these into sets to easily compare things
        contains_set = _make_set(contains)
        excludes_set = _make_set(excludes)
        old_value_set = _make_set(old_value)
        if len(contains_set.intersection(excludes_set)) > 0:
            msg = 'Variable {0} cannot contain and exclude the same value'
            ret['comment'] = msg.format(name)
            ret['result'] = False
        else:
            to_append = set()
            to_trim = set()
            if contains is not None:
                to_append = contains_set.difference(old_value_set)
            if excludes is not None:
                to_trim = excludes_set.intersection(old_value_set)
            if len(to_append) == 0 and len(to_trim) == 0:
                msg = 'Variable {0} is correct in make.conf'
                ret['comment'] = msg.format(name)
            else:
                if __opts__['test']:
                    msg = 'Variable {0} is set to'.format(name)
                    if len(to_append) > 0:
                        msg += ' append "{0}"'.format(list(to_append))
                    if len(to_trim) > 0:
                        msg += ' trim "{0}"'.format(list(to_trim))
                    msg += ' in make.conf'
                    ret['comment'] = msg
                    ret['result'] = None
                else:
                    for value in to_append:
                        __salt__['makeconf.append_var'](upper_name, value)
                    for value in to_trim:
                        __salt__['makeconf.trim_var'](upper_name, value)
                    new_value = __salt__['makeconf.get_var'](upper_name)

                    # TODO verify appends and trims worked
                    ret['changes'] = {upper_name: {'old': old_value,
                                                  'new': new_value}}
                    msg = 'Variable {0} is correct in make.conf'
                    ret['comment'] = msg.format(name)

    # Now finally return
    return ret


def absent(name):
    '''
    Verify that the variable is not in the ``make.conf``.

    name
        The variable name. This will automatically be converted to upper
        case since variables in ``make.conf`` are in upper case
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Make name all Uppers since make.conf uses all Upper vars
    upper_name = name.upper()

    old_value = __salt__['makeconf.get_var'](upper_name)

    if old_value is None:
        msg = 'Variable {0} is already absent from make.conf'
        ret['comment'] = msg.format(name)
    else:
        if __opts__['test']:
            msg = 'Variable {0} is set to be removed from make.conf'
            ret['comment'] = msg.format(name)
            ret['result'] = None
        else:
            __salt__['makeconf.remove_var'](upper_name)

            new_value = __salt__['makeconf.get_var'](upper_name)
            if new_value is not None:
                msg = 'Variable {0} failed to be removed from make.conf'
                ret['comment'] = msg.format(name)
                ret['result'] = False
            else:
                msg = 'Variable {0} was removed from make.conf'
                ret['comment'] = msg.format(name)
                ret['result'] = True
    return ret

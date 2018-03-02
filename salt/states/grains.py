# -*- coding: utf-8 -*-
'''
Manage grains on the minion
===========================

This state allows for grains to be set.

Grains set or altered with this module are stored in the 'grains'
file on the minions, By default, this file is located at: ``/etc/salt/grains``

.. Note::

   This does **NOT** override any grains set in the minion config file.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import re

# Import Salt libs
from salt.defaults import DEFAULT_TARGET_DELIM


def exists(name, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Ensure that a grain is set

    name
        The grain name

    delimiter
        A delimiter different from the default can be provided.

    Check whether a grain exists. Does not attempt to check or set the value.
    '''
    name = re.sub(delimiter, DEFAULT_TARGET_DELIM, name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Grain exists'}
    _non_existent = object()
    existing = __salt__['grains.get'](name, _non_existent)
    if existing is _non_existent:
        ret['result'] = False
        ret['comment'] = 'Grain does not exist'
    return ret


def present(name, value, delimiter=DEFAULT_TARGET_DELIM, force=False):
    '''
    Ensure that a grain is set

    .. versionchanged:: v2015.8.2

    name
        The grain name

    value
        The value to set on the grain

    force
        If force is True, the existing grain will be overwritten
        regardless of its existing or provided value type. Defaults to False

        .. versionadded:: v2015.8.2

    delimiter
        A delimiter different from the default can be provided.

        .. versionadded:: v2015.8.2

    It is now capable to set a grain to a complex value (ie. lists and dicts)
    and supports nested grains as well.

    If the grain does not yet exist, a new grain is set to the given value. For
    a nested grain, the necessary keys are created if they don't exist. If
    a given key is an existing value, it will be converted, but an existing value
    different from the given key will fail the state.

    If the grain with the given name exists, its value is updated to the new
    value unless its existing or provided value is complex (list or dict). Use
    `force: True` to overwrite.

    .. code-block:: yaml

      cheese:
        grains.present:
          - value: edam

      nested_grain_with_complex_value:
        grains.present:
          - name: icinga:Apache SSL
          - value:
            - command: check_https
            - params: -H localhost -p 443 -S

      with,a,custom,delimiter:
        grains.present:
          - value: yay
          - delimiter: ,
    '''
    name = re.sub(delimiter, DEFAULT_TARGET_DELIM, name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    _non_existent = object()
    existing = __salt__['grains.get'](name, _non_existent)
    if existing == value:
        ret['comment'] = 'Grain is already set'
        return ret
    if __opts__['test']:
        ret['result'] = None
        if existing is _non_existent:
            ret['comment'] = 'Grain {0} is set to be added'.format(name)
            ret['changes'] = {'new': name}
        else:
            ret['comment'] = 'Grain {0} is set to be changed'.format(name)
            ret['changes'] = {'changed': {name: value}}
        return ret
    ret = __salt__['grains.set'](name, value, force=force)
    if ret['result'] is True and ret['changes'] != {}:
        ret['comment'] = 'Set grain {0} to {1}'.format(name, value)
    ret['name'] = name
    return ret


def list_present(name, value, delimiter=DEFAULT_TARGET_DELIM):
    '''
    .. versionadded:: 2014.1.0

    Ensure the value is present in the list-type grain. Note: If the grain that is
    provided in ``name`` is not present on the system, this new grain will be created
    with the corresponding provided value.

    name
        The grain name.

    value
        The value is present in the list type grain.

    delimiter
        A delimiter different from the default ``:`` can be provided.

        .. versionadded:: v2015.8.2

    The grain should be `list type <http://docs.python.org/2/tutorial/datastructures.html#data-structures>`_

    .. code-block:: yaml

        roles:
          grains.list_present:
            - value: web

    For multiple grains, the syntax looks like:

    .. code-block:: yaml

        roles:
          grains.list_present:
            - value:
              - web
              - dev
    '''
    name = re.sub(delimiter, DEFAULT_TARGET_DELIM, name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    grain = __salt__['grains.get'](name)
    if grain:
        # check whether grain is a list
        if not isinstance(grain, list):
            ret['result'] = False
            ret['comment'] = 'Grain {0} is not a valid list'.format(name)
            return ret
        if isinstance(value, list):
            if set(value).issubset(set(__salt__['grains.get'](name))):
                ret['comment'] = 'Value {1} is already in grain {0}'.format(name, value)
                return ret
            elif name in __context__.get('pending_grains', {}):
                # elements common to both
                intersection = set(value).intersection(__context__.get('pending_grains', {})[name])
                if intersection:
                    value = list(set(value).difference(__context__['pending_grains'][name]))
                    ret['comment'] = 'Removed value {0} from update due to context found in "{1}".\n'.format(value, name)
            if 'pending_grains' not in __context__:
                __context__['pending_grains'] = {}
            if name not in __context__['pending_grains']:
                __context__['pending_grains'][name] = set()
            __context__['pending_grains'][name].update(value)
        else:
            if value in grain:
                ret['comment'] = 'Value {1} is already in grain {0}'.format(name, value)
                return ret
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Value {1} is set to be appended to grain {0}'.format(name, value)
            ret['changes'] = {'new': grain}
            return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Grain {0} is set to be added'.format(name)
        ret['changes'] = {'new': grain}
        return ret
    new_grains = __salt__['grains.append'](name, value)
    if isinstance(value, list):
        if not set(value).issubset(set(__salt__['grains.get'](name))):
            ret['result'] = False
            ret['comment'] = 'Failed append value {1} to grain {0}'.format(name, value)
            return ret
    else:
        if value not in __salt__['grains.get'](name, delimiter=DEFAULT_TARGET_DELIM):
            ret['result'] = False
            ret['comment'] = 'Failed append value {1} to grain {0}'.format(name, value)
            return ret
    ret['comment'] = 'Append value {1} to grain {0}'.format(name, value)
    ret['changes'] = {'new': new_grains}
    return ret


def list_absent(name, value, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Delete a value from a grain formed as a list.

    .. versionadded:: 2014.1.0

    name
        The grain name.

    value
       The value to delete from the grain list.

    delimiter
        A delimiter different from the default ``:`` can be provided.

        .. versionadded:: v2015.8.2

    The grain should be `list type <http://docs.python.org/2/tutorial/datastructures.html#data-structures>`_

    .. code-block:: yaml

        roles:
          grains.list_absent:
            - value: db

    For multiple grains, the syntax looks like:

    .. code-block:: yaml

        roles:
          grains.list_absent:
            - value:
              - web
              - dev
    '''

    name = re.sub(delimiter, DEFAULT_TARGET_DELIM, name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    comments = []
    grain = __salt__['grains.get'](name, None)
    if grain:
        if isinstance(grain, list):
            if not isinstance(value, list):
                value = [value]
            for val in value:
                if val not in grain:
                    comments.append('Value {1} is absent from '
                                      'grain {0}'.format(name, val))
                elif __opts__['test']:
                    ret['result'] = None
                    comments.append('Value {1} in grain {0} is set '
                                     'to be deleted'.format(name, val))
                    if 'deleted' not in ret['changes'].keys():
                        ret['changes'] = {'deleted': []}
                    ret['changes']['deleted'].append(val)
                elif val in grain:
                    __salt__['grains.remove'](name, val)
                    comments.append('Value {1} was deleted from '
                                     'grain {0}'.format(name, val))
                    if 'deleted' not in ret['changes'].keys():
                        ret['changes'] = {'deleted': []}
                    ret['changes']['deleted'].append(val)
            ret['comment'] = '\n'.join(comments)
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Grain {0} is not a valid list'\
                             .format(name)
    else:
        ret['comment'] = 'Grain {0} does not exist'.format(name)
    return ret


def absent(name,
           destructive=False,
           delimiter=DEFAULT_TARGET_DELIM,
           force=False):
    '''
    .. versionadded:: 2014.7.0

    Delete a grain from the grains config file

    name
        The grain name

    destructive
        If destructive is True, delete the entire grain. If
        destructive is False, set the grain's value to None. Defaults to False.

    force
        If force is True, the existing grain will be overwritten
        regardless of its existing or provided value type. Defaults to False

        .. versionadded:: v2015.8.2

    delimiter
        A delimiter different from the default can be provided.

        .. versionadded:: v2015.8.2

    .. versionchanged:: v2015.8.2

    This state now support nested grains and complex values. It is also more
    conservative: if a grain has a value that is a list or a dict, it will
    not be removed unless the `force` parameter is True.

    .. code-block:: yaml

      grain_name:
        grains.absent: []
    '''

    _non_existent = object()

    name = re.sub(delimiter, DEFAULT_TARGET_DELIM, name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    grain = __salt__['grains.get'](name, _non_existent)
    if grain is None:
        if __opts__['test']:
            ret['result'] = None
            if destructive is True:
                ret['comment'] = 'Grain {0} is set to be deleted'.format(name)
                ret['changes'] = {'deleted': name}
            return ret
        ret = __salt__['grains.set'](name,
                                     None,
                                     destructive=destructive,
                                     force=force)
        if ret['result']:
            if destructive is True:
                ret['comment'] = 'Grain {0} was deleted'.format(name)
                ret['changes'] = {'deleted': name}
        ret['name'] = name
    elif grain is not _non_existent:
        if __opts__['test']:
            ret['result'] = None
            if destructive is True:
                ret['comment'] = 'Grain {0} is set to be deleted'.format(name)
                ret['changes'] = {'deleted': name}
            else:
                ret['comment'] = 'Value for grain {0} is set to be ' \
                                 'deleted (None)'.format(name)
                ret['changes'] = {'grain': name, 'value': None}
            return ret
        ret = __salt__['grains.set'](name,
                                     None,
                                     destructive=destructive,
                                     force=force)
        if ret['result']:
            if destructive is True:
                ret['comment'] = 'Grain {0} was deleted'.format(name)
                ret['changes'] = {'deleted': name}
            else:
                ret['comment'] = 'Value for grain {0} was set to None'.format(name)
                ret['changes'] = {'grain': name, 'value': None}
        ret['name'] = name
    else:
        ret['comment'] = 'Grain {0} does not exist'.format(name)
    return ret


def append(name, value, convert=False,
           delimiter=DEFAULT_TARGET_DELIM):
    '''
    .. versionadded:: 2014.7.0

    Append a value to a list in the grains config file. The grain that is being
    appended to (name) must exist before the new value can be added.

    name
        The grain name

    value
        The value to append

    convert
        If convert is True, convert non-list contents into a list.
        If convert is False and the grain contains non-list contents, an error
        is given. Defaults to False.

    delimiter
        A delimiter different from the default can be provided.

        .. versionadded:: v2015.8.2

    .. code-block:: yaml

      grain_name:
        grains.append:
          - value: to_be_appended
    '''
    name = re.sub(delimiter, DEFAULT_TARGET_DELIM, name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    grain = __salt__['grains.get'](name, None)

    # Check if bool(grain) is False or if the grain is specified in the minions
    # grains. Grains can be set to a None value by omitting a value in the
    # definition.
    if grain or name in __grains__:
        if isinstance(grain, list):
            if value in grain:
                ret['comment'] = 'Value {1} is already in the list ' \
                                 'for grain {0}'.format(name, value)
                return ret
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Value {1} in grain {0} is set to ' \
                                 'be added'.format(name, value)
                ret['changes'] = {'added': value}
                return ret
            __salt__['grains.append'](name, value)
            ret['comment'] = 'Value {1} was added to grain {0}'.format(name, value)
            ret['changes'] = {'added': value}
        else:
            if convert is True:
                if __opts__['test']:
                    ret['result'] = None
                    ret['comment'] = 'Grain {0} is set to be converted ' \
                                     'to list and value {1} will be ' \
                                     'added'.format(name, value)
                    ret['changes'] = {'added': value}
                    return ret
                grain = [] if grain is None else [grain]
                grain.append(value)
                __salt__['grains.setval'](name, grain)
                ret['comment'] = 'Value {1} was added to grain {0}'.format(name, value)
                ret['changes'] = {'added': value}
            else:
                ret['result'] = False
                ret['comment'] = 'Grain {0} is not a valid list'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'Grain {0} does not exist'.format(name)
    return ret

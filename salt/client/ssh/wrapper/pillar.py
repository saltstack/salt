# -*- coding: utf-8 -*-
'''
Extract the pillar data for this minion
'''
# Import salt libs
import salt.pillar
import salt.utils


def get(key, default=''):
    '''
    .. versionadded:: 0.14

    Attempt to retrieve the named value from pillar, if the named value is not
    available return the passed default. The default return is an empty string.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict in pillar looks like this::

        {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed::

        pkg:apache

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.get pkg:apache
    '''
    return salt.utils.traverse_dict_and_list(__pillar__, key, default)


def item(*args):
    '''
    .. versionadded:: 0.16.2

    Return one ore more pillar entries

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.item foo
        salt '*' pillar.item foo bar baz
    '''
    ret = {}
    for arg in args:
        try:
            ret[arg] = __pillar__[arg]
        except KeyError:
            pass
    return ret


def raw(key=None):
    '''
    Return the raw pillar data that is available in the module. This will
    show the pillar as it is loaded as the __pillar__ dict.

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.raw

    With the optional key argument, you can select a subtree of the
    pillar raw data.::

        salt '*' pillar.raw key='roles'
    '''
    if key:
        ret = __pillar__.get(key, {})
    else:
        ret = __pillar__

    return ret


# Allow pillar.data to also be used to return pillar data
items = raw
data = items

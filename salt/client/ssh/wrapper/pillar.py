# -*- coding: utf-8 -*-
'''
Extract the pillar data for this minion
'''
from __future__ import absolute_import

# Import python libs
import collections

# Import salt libs
import salt.pillar
import salt.utils
from salt.defaults import DEFAULT_TARGET_DELIM


def get(key, default='', merge=False, delimiter=DEFAULT_TARGET_DELIM):
    '''
    .. versionadded:: 0.14

    Attempt to retrieve the named value from pillar, if the named value is not
    available return the passed default. The default return is an empty string.

    If the merge parameter is set to ``True``, the default will be recursively
    merged into the returned pillar data.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict in pillar looks like this::

        {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed::

        pkg:apache

    merge
        Specify whether or not the retrieved values should be recursively
        merged into the passed default.

        .. versionadded:: 2014.7.0

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.get pkg:apache
    '''
    if merge:
        ret = salt.utils.traverse_dict_and_list(__pillar__, key, {}, delimiter)
        if isinstance(ret, collections.Mapping) and \
                isinstance(default, collections.Mapping):
            return salt.utils.dictupdate.update(default, ret)

    return salt.utils.traverse_dict_and_list(__pillar__,
                                             key,
                                             default,
                                             delimiter)


def item(*args):
    '''
    .. versionadded:: 0.16.2

    Return one or more pillar entries

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

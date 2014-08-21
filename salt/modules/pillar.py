# -*- coding: utf-8 -*-
'''
Extract the pillar data for this minion
'''

# Import python libs
import collections

# Import third party libs
import yaml

# Import salt libs
import salt.pillar
import salt.utils
from salt._compat import string_types

__proxyenabled__ = ['*']


def get(key, default='', merge=False, delimiter=':'):
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


def items(*args):
    '''
    Calls the master for a fresh pillar and generates the pillar data on the
    fly

    Contrast with :py:func:`raw` which returns the pillar data that is
    currently loaded into the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.items
    '''
    # Preserve backwards compatibility
    if args:
        return item(*args)

    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['environment'])

    return pillar.compile_pillar()

# Allow pillar.data to also be used to return pillar data
data = items


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
    pillar = items()
    for arg in args:
        try:
            ret[arg] = pillar[arg]
        except KeyError:
            pass
    return ret


def raw(key=None):
    '''
    Return the raw pillar data that is currently loaded into the minion.

    Contrast with :py:func:`items` which calls the master to fetch the most
    up-to-date Pillar.

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


def ext(external):
    '''
    Generate the pillar and apply an explicit external pillar

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.ext '{libvirt: _}'
    '''
    if isinstance(external, string_types):
        external = yaml.safe_load(external)
    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['environment'],
        external)

    ret = pillar.compile_pillar()

    return ret

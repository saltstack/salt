# -*- coding: utf-8 -*-
'''
Extract the pillar data for this minion
'''
from __future__ import absolute_import

# Import python libs
import collections

# Import third party libs
import yaml

# Import salt libs
import salt.pillar
import salt.utils
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.ext.six import string_types

__proxyenabled__ = ['*']


def get(key, default=KeyError, merge=False, delimiter=DEFAULT_TARGET_DELIM):
    '''
    .. versionadded:: 0.14

    Attempt to retrieve the named value from pillar, if the named value is not
    available return the passed default. The default return is an empty string
    except __opts__['pillar_raise_on_missing'] is set to True, in which case a
    KeyError will be raised.

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
    if not __opts__.get('pillar_raise_on_missing'):
        if default is KeyError:
            default = ''

    if merge:
        ret = salt.utils.traverse_dict_and_list(__pillar__, key, {}, delimiter)
        if isinstance(ret, collections.Mapping) and \
                isinstance(default, collections.Mapping):
            return salt.utils.dictupdate.update(default, ret)

    ret = salt.utils.traverse_dict_and_list(__pillar__,
                                            key,
                                            default,
                                            delimiter)
    if ret is KeyError:
        raise KeyError("Pillar key not found: {0}".format(key))

    return ret


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


def _obfuscate_inner(var):
    '''
    Recursive obfuscation of collection types.

    Leaf or unknown Python types get replaced by the type name
    Known collection types trigger recursion.
    In the special case of mapping types, keys are not obfuscated
    '''
    if isinstance(var, (dict, salt.utils.odict.OrderedDict)):
        return var.__class__((k, _obfuscate_inner(v))
                             for k, v in var.iteritems())
    elif isinstance(var, (list, set, tuple)):
        return type(var)(_obfuscate_inner(v) for v in var)
    else:
        return '<{0}>'.format(var.__class__.__name__)


def obfuscate(*args):
    '''
    .. versionadded:: Beryllium

    Same as :py:func:`items`, but replace pillar values with a simple type indication.

    This is useful to avoid displaying sensitive information on console or
    flooding the console with long output, such as certificates.
    For many debug or control purposes, the stakes lie more in dispatching than in
    actual values.

    In case the value is itself a collection type, obfuscation occurs within the value.
    For mapping types, keys are not obfuscated.
    Here are some examples:

    * ``'secret password'`` becomes ``'<str>'``
    * ``['secret', 1]`` becomes ``['<str>', '<int>']
    * ``{'login': 'somelogin', 'pwd': 'secret'}`` becomes
      ``{'login': '<str>', 'pwd': '<str>'}``

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.obfuscate

    '''
    return _obfuscate_inner(items(*args))


# naming chosen for consistency with grains.ls, although it breaks the short
# identifier rule.
def ls(*args):
    '''
    .. versionadded:: Beryllium

    Calls the master for a fresh pillar, generates the pillar data on the
    fly (same as :py:func:`items`), but only shows the available main keys.

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.ls
    '''

    return items(*args).keys()


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

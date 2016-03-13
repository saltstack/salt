# -*- coding: utf-8 -*-
'''
Extract the pillar data for this minion
'''
from __future__ import absolute_import

# Import python libs
import collections

# Import third party libs
import os
import yaml
import salt.ext.six as six

# Import salt libs
import salt.pillar
import salt.utils
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import CommandExecutionError

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


def items(*args, **kwargs):
    '''
    Calls the master for a fresh pillar and generates the pillar data on the
    fly

    Contrast with :py:func:`raw` which returns the pillar data that is
    currently loaded into the minion.

    pillar : none
        if specified, allows for a dictionary of pillar data to be made
        available to pillar and ext_pillar rendering. these pillar variables
        will also override any variables of the same name in pillar or
        ext_pillar.

        .. versionadded:: 2015.5.0

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
        __opts__['environment'],
        pillar=kwargs.get('pillar'))

    return pillar.compile_pillar()

# Allow pillar.data to also be used to return pillar data
data = salt.utils.alias_function(items, 'data')


def _obfuscate_inner(var):
    '''
    Recursive obfuscation of collection types.

    Leaf or unknown Python types get replaced by the type name
    Known collection types trigger recursion.
    In the special case of mapping types, keys are not obfuscated
    '''
    if isinstance(var, (dict, salt.utils.odict.OrderedDict)):
        return var.__class__((key, _obfuscate_inner(val))
                             for key, val in six.iteritems(var))
    elif isinstance(var, (list, set, tuple)):
        return type(var)(_obfuscate_inner(v) for v in var)
    else:
        return '<{0}>'.format(var.__class__.__name__)


def obfuscate(*args):
    '''
    .. versionadded:: 2015.8.0

    Same as :py:func:`items`, but replace pillar values with a simple type indication.

    This is useful to avoid displaying sensitive information on console or
    flooding the console with long output, such as certificates.
    For many debug or control purposes, the stakes lie more in dispatching than in
    actual values.

    In case the value is itself a collection type, obfuscation occurs within the value.
    For mapping types, keys are not obfuscated.
    Here are some examples:

    * ``'secret password'`` becomes ``'<str>'``
    * ``['secret', 1]`` becomes ``['<str>', '<int>']``
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
    .. versionadded:: 2015.8.0

    Calls the master for a fresh pillar, generates the pillar data on the
    fly (same as :py:func:`items`), but only shows the available main keys.

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.ls
    '''

    return list(items(*args).keys())


def item(*args, **kwargs):
    '''
    .. versionadded:: 0.16.2

    Return one or more pillar entries

    pillar : none
        if specified, allows for a dictionary of pillar data to be made
        available to pillar and ext_pillar rendering. these pillar variables
        will also override any variables of the same name in pillar or
        ext_pillar.

        .. versionadded:: 2015.5.0

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.item foo
        salt '*' pillar.item foo bar baz
    '''
    ret = {}
    default = kwargs.get('default', '')
    delimiter = kwargs.get('delimiter', ':')

    try:
        for arg in args:
            ret[arg] = salt.utils.traverse_dict_and_list(__pillar__,
                                                        arg,
                                                        default,
                                                        delimiter)
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


def ext(external, pillar=None):
    '''
    Generate the pillar and apply an explicit external pillar

    CLI Example:

    pillar : None
        If specified, allows for a dictionary of pillar data to be made
        available to pillar and ext_pillar rendering. These pillar variables
        will also override any variables of the same name in pillar or
        ext_pillar.

        .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' pillar.ext '{libvirt: _}'
    '''
    if isinstance(external, six.string_types):
        external = yaml.safe_load(external)
    pillar_obj = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['environment'],
        ext=external,
        pillar=pillar)

    ret = pillar_obj.compile_pillar()

    return ret


def keys(key, delimiter=DEFAULT_TARGET_DELIM):
    '''
    .. versionadded:: 2015.8.0

    Attempt to retrieve a list of keys from the named value from the pillar.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict, similar to how pillar.get works.

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.keys web:sites
    '''
    ret = salt.utils.traverse_dict_and_list(
        __pillar__, key, KeyError, delimiter)

    if ret is KeyError:
        raise KeyError("Pillar key not found: {0}".format(key))

    if not isinstance(ret, dict):
        raise ValueError("Pillar value in key {0} is not a dict".format(key))

    return ret.keys()


def file_exists(path, saltenv=None):
    '''
    .. versionadded:: 2016.3.0

    This is a master-only function. Calling from the minion is not supported.

    Use the given path and search relative to the pillar environments to see if
    a file exists at that path.

    If the ``saltenv`` argument is given, restrict search to that environment
    only.

    Will only work with ``pillar_roots``, not external pillars.

    Returns True if the file is found, and False otherwise.

    path
        The path to the file in question. Will be treated as a relative path

    saltenv
        Optional argument to restrict the search to a specific saltenv

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.file_exists foo/bar.sls
    '''
    pillar_roots = __opts__.get('pillar_roots')
    if not pillar_roots:
        raise CommandExecutionError('No pillar_roots found. Are you running '
                                    'this on the master?')

    if saltenv:
        if saltenv in pillar_roots:
            pillar_roots = {saltenv: pillar_roots[saltenv]}
        else:
            return False

    for env in pillar_roots:
        for pillar_dir in pillar_roots[env]:
            full_path = os.path.join(pillar_dir, path)
            if __salt__['file.file_exists'](full_path):
                return True

    return False


# Provide a jinja function call compatible get aliased as fetch
fetch = get

# -*- coding: utf-8 -*-
'''
Extract the pillar data for this minion
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import collections

# Import third party libs
import copy
import os
import copy
import logging
from salt.ext import six

# Import salt libs
import salt.pillar
import salt.utils.crypt
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.functools
import salt.utils.odict
import salt.utils.yaml
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import CommandExecutionError

__proxyenabled__ = ['*']

log = logging.getLogger(__name__)


def get(key,
        default=KeyError,
        merge=False,
        merge_nested_lists=None,
        delimiter=DEFAULT_TARGET_DELIM,
        pillarenv=None,
        saltenv=None):
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

    merge : ``False``
        If ``True``, the retrieved values will be merged into the passed
        default. When the default and the retrieved value are both
        dictionaries, the dictionaries will be recursively merged.

        .. versionadded:: 2014.7.0
        .. versionchanged:: 2016.3.7,2016.11.4,2017.7.0
            If the default and the retrieved value are not of the same type,
            then merging will be skipped and the retrieved value will be
            returned. Earlier releases raised an error in these cases.

    merge_nested_lists
        If set to ``False``, lists nested within the retrieved pillar
        dictionary will *overwrite* lists in ``default``. If set to ``True``,
        nested lists will be *merged* into lists in ``default``. If unspecified
        (the default), this option is inherited from the
        :conf_minion:`pillar_merge_lists` minion config option.

        .. note::
            This option is ignored when ``merge`` is set to ``False``.

        .. versionadded:: 2016.11.6

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict.
        This is useful for when the desired key contains a colon. See CLI
        example below for usage.

        .. versionadded:: 2014.7.0

    pillarenv
        If specified, this function will query the master to generate fresh
        pillar data on the fly, specifically from the requested pillar
        environment. Note that this can produce different pillar data than
        executing this function without an environment, as its normal behavior
        is just to return a value from minion's pillar data in memory (which
        can be sourced from more than one pillar environment).

        Using this argument will not affect the pillar data in memory. It will
        however be slightly slower and use more resources on the master due to
        the need for the master to generate and send the minion fresh pillar
        data. This tradeoff in performance however allows for the use case
        where pillar data is desired only from a single environment.

        .. versionadded:: 2017.7.0

    saltenv
        Included only for compatibility with
        :conf_minion:`pillarenv_from_saltenv`, and is otherwise ignored.

        .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.get pkg:apache
        salt '*' pillar.get abc::def|ghi delimiter='|'
    '''
    if not __opts__.get('pillar_raise_on_missing'):
        if default is KeyError:
            default = ''
    opt_merge_lists = __opts__.get('pillar_merge_lists', False) if \
        merge_nested_lists is None else merge_nested_lists
    pillar_dict = __pillar__ \
        if all(x is None for x in (saltenv, pillarenv)) \
        else items(saltenv=saltenv, pillarenv=pillarenv)

    if merge:
        if isinstance(default, dict):
            ret = salt.utils.data.traverse_dict_and_list(
                pillar_dict,
                key,
                {},
                delimiter)
            if isinstance(ret, collections.Mapping):
                default = copy.deepcopy(default)
                return salt.utils.dictupdate.update(
                    default,
                    ret,
                    merge_lists=opt_merge_lists)
            else:
                log.error(
                    'pillar.get: Default (%s) is a dict, but the returned '
                    'pillar value (%s) is of type \'%s\'. Merge will be '
                    'skipped.', default, ret, type(ret).__name__
                )
        elif isinstance(default, list):
            ret = salt.utils.data.traverse_dict_and_list(
                pillar_dict,
                key,
                [],
                delimiter)
            if isinstance(ret, list):
                default = copy.deepcopy(default)
                default.extend([x for x in ret if x not in default])
                return default
            else:
                log.error(
                    'pillar.get: Default (%s) is a list, but the returned '
                    'pillar value (%s) is of type \'%s\'. Merge will be '
                    'skipped.', default, ret, type(ret).__name__
                )
        else:
            log.error(
                'pillar.get: Default (%s) is of type \'%s\', must be a dict '
                'or list to merge. Merge will be skipped.',
                default, type(default).__name__
            )

    ret = salt.utils.data.traverse_dict_and_list(
        pillar_dict,
        key,
        default,
        delimiter)
    if ret is KeyError:
        raise KeyError('Pillar key not found: {0}'.format(key))

    return ret


def items(*args, **kwargs):
    '''
    Calls the master for a fresh pillar and generates the pillar data on the
    fly

    Contrast with :py:func:`raw` which returns the pillar data that is
    currently loaded into the minion.

    pillar
        If specified, allows for a dictionary of pillar data to be made
        available to pillar and ext_pillar rendering. these pillar variables
        will also override any variables of the same name in pillar or
        ext_pillar.

        .. versionadded:: 2015.5.0

    pillar_enc
        If specified, the data passed in the ``pillar`` argument will be passed
        through this renderer to decrypt it.

        .. note::
            This will decrypt on the minion side, so the specified renderer
            must be set up on the minion for this to work. Alternatively,
            pillar data can be decrypted master-side. For more information, see
            the :ref:`Pillar Encryption <pillar-encryption>` documentation.
            Pillar data that is decrypted master-side, is not decrypted until
            the end of pillar compilation though, so minion-side decryption
            will be necessary if the encrypted pillar data must be made
            available in an decrypted state pillar/ext_pillar rendering.

        .. versionadded:: 2017.7.0

    pillarenv
        Pass a specific pillar environment from which to compile pillar data.
        If not specified, then the minion's :conf_minion:`pillarenv` option is
        not used, and if that also is not specified then all configured pillar
        environments will be merged into a single pillar dictionary and
        returned.

        .. versionadded:: 2016.11.2

    saltenv
        Included only for compatibility with
        :conf_minion:`pillarenv_from_saltenv`, and is otherwise ignored.

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.items
    '''
    # Preserve backwards compatibility
    if args:
        return item(*args)

    pillarenv = kwargs.get('pillarenv')
    if pillarenv is None:
        if __opts__.get('pillarenv_from_saltenv', False):
            pillarenv = kwargs.get('saltenv') or __opts__['saltenv']
        else:
            pillarenv = __opts__['pillarenv']

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')

    if pillar_override and pillar_enc:
        try:
            pillar_override = salt.utils.crypt.decrypt(
                pillar_override,
                pillar_enc,
                translate_newlines=True,
                opts=__opts__,
                valid_rend=__opts__['decrypt_pillar_renderers'])
        except Exception as exc:
            raise CommandExecutionError(
                'Failed to decrypt pillar override: {0}'.format(exc)
            )

    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        pillar_override=pillar_override,
        pillarenv=pillarenv)

    return pillar.compile_pillar()

# Allow pillar.data to also be used to return pillar data
data = salt.utils.functools.alias_function(items, 'data')


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

    Return one or more pillar entries from the :ref:`in-memory pillar data
    <pillar-in-memory>`.

    delimiter
        Delimiter used to traverse nested dictionaries.

        .. note::
            This is different from :py:func:`pillar.get
            <salt.modules.pillar.get>` in that no default value can be
            specified. :py:func:`pillar.get <salt.modules.pillar.get>` should
            probably still be used in most cases to retrieve nested pillar
            values, as it is a bit more flexible. One reason to use this
            function instead of :py:func:`pillar.get <salt.modules.pillar.get>`
            however is when it is desirable to retrieve the values of more than
            one key, since :py:func:`pillar.get <salt.modules.pillar.get>` can
            only retrieve one key at a time.

        .. versionadded:: 2015.8.0

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.item foo
        salt '*' pillar.item foo:bar
        salt '*' pillar.item foo bar baz
    '''
    ret = {}
    default = kwargs.get('default', '')
    delimiter = kwargs.get('delimiter', DEFAULT_TARGET_DELIM)

    try:
        for arg in args:
            ret[arg] = salt.utils.data.traverse_dict_and_list(
                __pillar__,
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
    .. versionchanged:: 2016.3.6,2016.11.3,2017.7.0
        The supported ext_pillar types are now tunable using the
        :conf_master:`on_demand_ext_pillar` config option. Earlier releases
        used a hard-coded default.

    Generate the pillar and apply an explicit external pillar


    external
        A single ext_pillar to add to the ext_pillar configuration. This must
        be passed as a single section from the ext_pillar configuration (see
        CLI examples below). For more complicated ``ext_pillar``
        configurations, it can be helpful to use the Python shell to load YAML
        configuration into a dictionary, and figure out

        .. code-block:: python

            >>> import salt.utils.yaml
            >>> ext_pillar = salt.utils.yaml.safe_load("""
            ... ext_pillar:
            ...   - git:
            ...     - issue38440 https://github.com/terminalmage/git_pillar:
            ...       - env: base
            ... """)
            >>> ext_pillar
            {'ext_pillar': [{'git': [{'mybranch https://github.com/myuser/myrepo': [{'env': 'base'}]}]}]}
            >>> ext_pillar['ext_pillar'][0]
            {'git': [{'mybranch https://github.com/myuser/myrepo': [{'env': 'base'}]}]}

        In the above example, the value to pass would be
        ``{'git': [{'mybranch https://github.com/myuser/myrepo': [{'env': 'base'}]}]}``.
        Note that this would need to be quoted when passing on the CLI (as in
        the CLI examples below).

    pillar : None
        If specified, allows for a dictionary of pillar data to be made
        available to pillar and ext_pillar rendering. These pillar variables
        will also override any variables of the same name in pillar or
        ext_pillar.

        .. versionadded:: 2015.5.0

    CLI Examples:

    .. code-block:: bash

        salt '*' pillar.ext '{libvirt: _}'
        salt '*' pillar.ext "{'git': ['master https://github.com/myuser/myrepo']}"
        salt '*' pillar.ext "{'git': [{'mybranch https://github.com/myuser/myrepo': [{'env': 'base'}]}]}"
    '''
    if isinstance(external, six.string_types):
        external = salt.utils.yaml.safe_load(external)
    pillar_obj = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['saltenv'],
        ext=external,
        pillar_override=pillar)

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
    ret = salt.utils.data.traverse_dict_and_list(
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


def filter_by(lookup_dict,
              pillar,
              merge=None,
              default='default',
              base=None):
    '''
    .. versionadded:: 2017.7.0

    Look up the given pillar in a given dictionary and return the result

    :param lookup_dict: A dictionary, keyed by a pillar, containing a value or
        values relevant to systems matching that pillar. For example, a key
        could be a pillar for a role and the value could the name of a package
        on that particular OS.

        The dictionary key can be a globbing pattern. The function will return
        the corresponding ``lookup_dict`` value where the pilalr value matches
        the  pattern. For example:

        .. code-block:: bash

            # this will render 'got some salt' if ``role`` begins with 'salt'
            salt '*' pillar.filter_by '{salt*: got some salt, default: salt is not here}' role

    :param pillar: The name of a pillar to match with the system's pillar. For
        example, the value of the "role" pillar could be used to pull values
        from the ``lookup_dict`` dictionary.

        The pillar value can be a list. The function will return the
        ``lookup_dict`` value for a first found item in the list matching
        one of the ``lookup_dict`` keys.

    :param merge: A dictionary to merge with the results of the pillar
        selection from ``lookup_dict``. This allows another dictionary to
        override the values in the ``lookup_dict``.

    :param default: default lookup_dict's key used if the pillar does not exist
        or if the pillar value has no match on lookup_dict.  If unspecified
        the value is "default".

    :param base: A lookup_dict key to use for a base dictionary.  The
        pillar-selected ``lookup_dict`` is merged over this and then finally
        the ``merge`` dictionary is merged.  This allows common values for
        each case to be collected in the base and overridden by the pillar
        selection dictionary and the merge dictionary.  Default is unset.

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.filter_by '{web: Serve it up, db: I query, default: x_x}' role
    '''
    return salt.utils.data.filter_by(lookup_dict=lookup_dict,
                                     lookup=pillar,
                                     traverse=__pillar__,
                                     merge=merge,
                                     default=default,
                                     base=base)

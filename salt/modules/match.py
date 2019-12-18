# -*- coding: utf-8 -*-
'''
The match module allows for match routines to be run and determine target specs
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import inspect
import logging
import sys
import copy

# Import salt libs
import salt.loader
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.ext import six

__func_alias__ = {
    'list_': 'list'
}

log = logging.getLogger(__name__)


def compound(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given compound target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.compound 'L@cheese,foo and *'
    '''
    if minion_id is not None:
        opts = copy.copy(__opts__)
        if not isinstance(minion_id, six.string_types):
            minion_id = six.text_type(minion_id)
        opts['id'] = minion_id
    else:
        opts = __opts__
    matchers = salt.loader.matchers(opts)
    try:
        return matchers['compound_match.match'](tgt)
    except Exception as exc:
        log.exception(exc)
        return False


def ipcidr(tgt):
    '''
    Return True if the minion matches the given ipcidr target

    CLI Example:

    .. code-block:: bash

        salt '*' match.ipcidr '192.168.44.0/24'

    delimiter
    Pillar Example:

    .. code-block:: yaml

       '172.16.0.0/12':
         - match: ipcidr
         - nodeclass: internal

    '''
    matchers = salt.loader.matchers(__opts__)
    try:
        return matchers['ipcidr_match.match'](tgt, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def pillar_pcre(tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Return True if the minion matches the given pillar_pcre target. The
    ``delimiter`` argument can be used to specify a different delimiter.

    CLI Example:

    .. code-block:: bash

        salt '*' match.pillar_pcre 'cheese:(swiss|american)'
        salt '*' match.pillar_pcre 'clone_url|https://github\\.com/.*\\.git' delimiter='|'

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 2014.7.0

    delim
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 0.16.4
        .. deprecated:: 2015.8.0
    '''
    matchers = salt.loader.matchers(__opts__)
    try:
        return matchers['pillar_pcre_match.match'](tgt, delimiter=delimiter, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def pillar(tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Return True if the minion matches the given pillar target. The
    ``delimiter`` argument can be used to specify a different delimiter.

    CLI Example:

    .. code-block:: bash

        salt '*' match.pillar 'cheese:foo'
        salt '*' match.pillar 'clone_url|https://github.com/saltstack/salt.git' delimiter='|'

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 2014.7.0

    delim
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 0.16.4
        .. deprecated:: 2015.8.0
    '''
    matchers = salt.loader.matchers(__opts__)
    try:
        return matchers['pillar_match.match'](tgt, delimiter=delimiter, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def data(tgt):
    '''
    Return True if the minion matches the given data target

    CLI Example:

    .. code-block:: bash

        salt '*' match.data 'spam:eggs'
    '''
    matchers = salt.loader.matchers(__opts__)
    try:
        return matchers['data_match.match'](tgt, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def grain_pcre(tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Return True if the minion matches the given grain_pcre target. The
    ``delimiter`` argument can be used to specify a different delimiter.

    CLI Example:

    .. code-block:: bash

        salt '*' match.grain_pcre 'os:Fedo.*'
        salt '*' match.grain_pcre 'ipv6|2001:.*' delimiter='|'

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 2014.7.0

    delim
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 0.16.4
        .. deprecated:: 2015.8.0
    '''
    matchers = salt.loader.matchers(__opts__)
    try:
        return matchers['grain_pcre_match.match'](tgt, delimiter=delimiter, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def grain(tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Return True if the minion matches the given grain target. The ``delimiter``
    argument can be used to specify a different delimiter.

    CLI Example:

    .. code-block:: bash

        salt '*' match.grain 'os:Ubuntu'
        salt '*' match.grain 'ipv6|2001:db8::ff00:42:8329' delimiter='|'

    delimiter
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 2014.7.0

    delim
        Specify an alternate delimiter to use when traversing a nested dict

        .. versionadded:: 0.16.4
        .. deprecated:: 2015.8.0
    '''
    matchers = salt.loader.matchers(__opts__)
    try:
        return matchers['grain_match.match'](tgt, delimiter=delimiter, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def list_(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given list target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.list 'server1,server2'
    '''
    if minion_id is not None:
        opts = copy.copy(__opts__)
        if not isinstance(minion_id, six.string_types):
            minion_id = six.text_type(minion_id)
        opts['id'] = minion_id
    else:
        opts = __opts__
    matchers = salt.loader.matchers(opts)
    try:
        return matchers['list_match.match'](tgt, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def pcre(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given pcre target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.pcre '.*'
    '''
    if minion_id is not None:
        opts = copy.copy(__opts__)
        if not isinstance(minion_id, six.string_types):
            minion_id = six.text_type(minion_id)
        opts['id'] = minion_id
    else:
        opts = __opts__
    matchers = salt.loader.matchers(opts)
    try:
        return matchers['pcre_match.match'](tgt, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def glob(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given glob target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.glob '*'
    '''
    if minion_id is not None:
        opts = copy.copy(__opts__)
        if not isinstance(minion_id, six.string_types):
            minion_id = six.text_type(minion_id)
        opts['id'] = minion_id
    else:
        opts = __opts__
    matchers = salt.loader.matchers(opts)

    try:
        return matchers['glob_match.match'](tgt, opts=__opts__)
    except Exception as exc:
        log.exception(exc)
        return False


def filter_by(lookup,
              tgt_type='compound',
              minion_id=None,
              default='default'):
    '''
    Return the first match in a dictionary of target patterns

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.filter_by '{foo*: Foo!, bar*: Bar!}' minion_id=bar03

    Pillar Example:

    .. code-block:: jinja

        # Filter the data for the current minion into a variable:
        {% set roles = salt['match.filter_by']({
            'web*': ['app', 'caching'],
            'db*': ['db'],
        }, default='web*') %}

        # Make the filtered data available to Pillar:
        roles: {{ roles | yaml() }}
    '''
    expr_funcs = dict(inspect.getmembers(sys.modules[__name__],
        predicate=inspect.isfunction))

    for key in lookup:
        params = (key, minion_id) if minion_id else (key, )
        if expr_funcs[tgt_type](*params):
            return lookup[key]

    return lookup.get(default, None)


def search_by(lookup, tgt_type='compound', minion_id=None):
    '''
    Search a dictionary of target strings for matching targets

    This is the inverse of :py:func:`match.filter_by
    <salt.modules.match.filter_by>` and allows matching values instead of
    matching keys. A minion can be matched by multiple entries.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.search_by '{web: [node1, node2], db: [node2, node]}'

    Pillar Example:

    .. code-block:: jinja

        {% set roles = salt.match.search_by({
            'web': ['G@os_family:Debian not nodeX'],
            'db': ['L@node2,node3 and G@datacenter:west'],
            'caching': ['node3', 'node4'],
        }) %}

        # Make the filtered data available to Pillar:
        roles: {{ roles | yaml() }}
    '''
    expr_funcs = dict(inspect.getmembers(sys.modules[__name__],
        predicate=inspect.isfunction))

    matches = []
    for key, target_list in lookup.items():
        for target in target_list:
            params = (target, minion_id) if minion_id else (target, )
            if expr_funcs[tgt_type](*params):
                matches.append(key)

    return matches or None

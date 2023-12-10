"""
The match module allows for match routines to be run and determine target specs
"""

import copy
import inspect
import logging
import sys
from collections.abc import Mapping

import salt.loader
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import SaltException
from salt.utils.decorators.jinja import jinja_global

__func_alias__ = {"list_": "list"}

log = logging.getLogger(__name__)


def _load_matchers():
    """
    Store matchers in __context__ so they're only loaded once
    """
    __context__["matchers"] = salt.loader.matchers(__opts__)


def compound(tgt, minion_id=None):
    """
    Return True if the minion ID matches the given compound target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.compound 'L@cheese,foo and *'
    """
    if minion_id is not None:
        if not isinstance(minion_id, str):
            minion_id = str(minion_id)
    if "matchers" not in __context__:
        _load_matchers()
    try:
        ret = __context__["matchers"]["compound_match.match"](
            tgt, opts=__opts__, minion_id=minion_id
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        ret = False

    return ret


def ipcidr(tgt):
    """
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

    """
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["ipcidr_match.match"](tgt, opts=__opts__)
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def pillar_pcre(tgt, delimiter=DEFAULT_TARGET_DELIM):
    """
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
    """
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["pillar_pcre_match.match"](
            tgt, delimiter=delimiter, opts=__opts__
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def pillar(tgt, delimiter=DEFAULT_TARGET_DELIM):
    """
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
    """
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["pillar_match.match"](
            tgt, delimiter=delimiter, opts=__opts__
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def data(tgt):
    """
    Return True if the minion matches the given data target

    CLI Example:

    .. code-block:: bash

        salt '*' match.data 'spam:eggs'
    """
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["data_match.match"](tgt, opts=__opts__)
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def grain_pcre(tgt, delimiter=DEFAULT_TARGET_DELIM):
    """
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
    """
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["grain_pcre_match.match"](
            tgt, delimiter=delimiter, opts=__opts__
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def grain(tgt, delimiter=DEFAULT_TARGET_DELIM):
    """
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
    """
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["grain_match.match"](
            tgt, delimiter=delimiter, opts=__opts__
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def list_(tgt, minion_id=None):
    """
    Return True if the minion ID matches the given list target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.list 'server1,server2'
    """
    if minion_id is not None:
        if not isinstance(minion_id, str):
            minion_id = str(minion_id)
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["list_match.match"](
            tgt, opts=__opts__, minion_id=minion_id
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def pcre(tgt, minion_id=None):
    """
    Return True if the minion ID matches the given pcre target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.pcre '.*'
    """
    if minion_id is not None:
        if not isinstance(minion_id, str):
            minion_id = str(minion_id)
    if "matchers" not in __context__:
        _load_matchers()
    try:
        return __context__["matchers"]["pcre_match.match"](
            tgt, opts=__opts__, minion_id=minion_id
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def glob(tgt, minion_id=None):
    """
    Return True if the minion ID matches the given glob target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' match.glob '*'
    """
    if minion_id is not None:
        if not isinstance(minion_id, str):
            minion_id = str(minion_id)
    if "matchers" not in __context__:
        _load_matchers()

    try:
        return __context__["matchers"]["glob_match.match"](
            tgt, opts=__opts__, minion_id=minion_id
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
        return False


def filter_by(
    lookup,
    tgt_type="compound",
    minion_id=None,
    merge=None,
    merge_lists=False,
    default="default",
):
    """
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
        }, minion_id=grains['id'], default='web*') %}

        # Make the filtered data available to Pillar:
        roles: {{ roles | yaml() }}
    """
    expr_funcs = dict(
        inspect.getmembers(sys.modules[__name__], predicate=inspect.isfunction)
    )

    for key in lookup:
        params = (key, minion_id) if minion_id else (key,)
        if expr_funcs[tgt_type](*params):
            if merge:
                if not isinstance(merge, Mapping):
                    raise SaltException(
                        "filter_by merge argument must be a dictionary."
                    )

                if lookup[key] is None:
                    return merge
                else:
                    salt.utils.dictupdate.update(
                        lookup[key], copy.deepcopy(merge), merge_lists=merge_lists
                    )

            return lookup[key]

    return lookup.get(default, None)


def search_by(lookup, tgt_type="compound", minion_id=None):
    """
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
    """
    expr_funcs = dict(
        inspect.getmembers(sys.modules[__name__], predicate=inspect.isfunction)
    )

    matches = []
    for key, target_list in lookup.items():
        for target in target_list:
            params = (target, minion_id) if minion_id else (target,)
            if expr_funcs[tgt_type](*params):
                matches.append(key)

    return matches or None


@jinja_global("ifelse")
def ifelse(
    *args,
    tgt_type="compound",
    minion_id=None,
    merge=None,
    merge_lists=False,
):
    """
    .. versionadded:: 3006.0

    Evaluate each pair of arguments up to the last one as a (matcher, value)
    tuple, returning ``value`` if matched.  If none match, returns the last
    argument.

    The ``ifelse`` function is like a multi-level if-else statement. It was
    inspired by CFEngine's ``ifelse`` function which in turn was inspired by
    Oracle's ``DECODE`` function. It must have an odd number of arguments (from
    1 to N). The last argument is the default value, like the ``else`` clause in
    standard programming languages. Every pair of arguments before the last one
    are evaluated as a pair. If the first one evaluates true then the second one
    is returned, as if you had used the first one in a compound match
    expression. Boolean values can also be used as the first item in a pair,
    as it will be translated to a match that will always match ("*") or never
    match ("SALT_IFELSE_MATCH_NOTHING") a target system.

    This is essentially another way to express the ``filter_by`` functionality
    in way that's familiar to CFEngine or Oracle users. Consider using
    ``filter_by`` unless this function fits your workflow.

    CLI Example:

    .. code-block:: bash

        salt '*' match.ifelse 'foo*' 'Foo!' 'bar*' 'Bar!' minion_id=bar03
    """
    if len(args) % 2 == 0:
        raise SaltException("The ifelse function must have an odd number of arguments!")
    elif len(args) == 1:
        return args[0]

    default_key = "SALT_IFELSE_FUNCTION_DEFAULT"

    keys = list(args[::2])
    for idx, key in enumerate(keys):
        if key is True:
            keys[idx] = "*"
        elif key is False:
            keys[idx] = "SALT_IFELSE_MATCH_NOTHING"

    lookup = dict(zip(keys, args[1::2]))
    lookup.update({default_key: args[-1]})

    return filter_by(
        lookup=lookup,
        tgt_type=tgt_type,
        minion_id=minion_id,
        merge=merge,
        merge_lists=merge_lists,
        default=default_key,
    )

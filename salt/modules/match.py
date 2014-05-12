# -*- coding: utf-8 -*-
'''
The match module allows for match routines to be run and determine target specs
'''

# Import python libs
import logging

# Import salt libs
import salt.minion
from salt._compat import string_types

__func_alias__ = {
    'list_': 'list'
}

log = logging.getLogger(__name__)


def compound(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given compound target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: Helium

    CLI Example:

    .. code-block:: bash

        salt '*' match.compound 'L@cheese,foo and *'
    '''
    opts = {'grains': __grains__}
    if minion_id is not None:
        if not isinstance(minion_id, string_types):
            minion_id = str(minion_id)
    else:
        minion_id = __grains__['id']
    opts['id'] = minion_id
    matcher = salt.minion.Matcher(opts, __salt__)
    try:
        return matcher.compound_match(tgt)
    except Exception as exc:
        log.exception(exc)
        return False


def ipcidr(tgt):
    '''
    Return True if the minion matches the given ipcidr target

    CLI Example:

    .. code-block:: bash

        salt '*' match.ipcidr '192.168.44.0/24'
    '''
    matcher = salt.minion.Matcher({'grains': __grains__}, __salt__)
    try:
        return matcher.ipcidr_match(tgt)
    except Exception as exc:
        log.exception(exc)
        return False


def pillar(tgt, delim=':'):
    '''
    Return True if the minion matches the given pillar target. The
    ``delim`` argument can be used to specify a different delimiter.

    CLI Example:

    .. code-block:: bash

        salt '*' match.pillar 'cheese:foo'
        salt '*' match.pillar 'clone_url|https://github.com/saltstack/salt.git' delim='|'

    .. versionchanged:: 0.16.4
        ``delim`` argument added
    '''
    matcher = salt.minion.Matcher({'pillar': __pillar__}, __salt__)
    try:
        return matcher.pillar_match(tgt, delim=delim)
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
    matcher = salt.minion.Matcher(__opts__, __salt__)
    try:
        return matcher.data_match(tgt)
    except Exception as exc:
        log.exception(exc)
        return False


def grain_pcre(tgt, delim=':'):
    '''
    Return True if the minion matches the given grain_pcre target. The
    ``delim`` argument can be used to specify a different delimiter.

    CLI Example:

    .. code-block:: bash

        salt '*' match.grain_pcre 'os:Fedo.*'
        salt '*' match.grain_pcre 'ipv6|2001:.*' delim='|'

    .. versionchanged:: 0.16.4
        ``delim`` argument added
    '''
    matcher = salt.minion.Matcher({'grains': __grains__}, __salt__)
    try:
        return matcher.grain_pcre_match(tgt, delim=delim)
    except Exception as exc:
        log.exception(exc)
        return False


def grain(tgt, delim=':'):
    '''
    Return True if the minion matches the given grain target. The ``delim``
    argument can be used to specify a different delimiter.

    CLI Example:

    .. code-block:: bash

        salt '*' match.grain 'os:Ubuntu'
        salt '*' match.grain_pcre 'ipv6|2001:db8::ff00:42:8329' delim='|'

    .. versionchanged:: 0.16.4
        ``delim`` argument added
    '''
    matcher = salt.minion.Matcher({'grains': __grains__}, __salt__)
    try:
        return matcher.grain_match(tgt, delim=delim)
    except Exception as exc:
        log.exception(exc)
        return False


def list_(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given list target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: Helium

    CLI Example:

    .. code-block:: bash

        salt '*' match.list 'server1,server2'
    '''
    if minion_id is not None:
        if not isinstance(minion_id, string_types):
            minion_id = str(minion_id)
    else:
        minion_id = __grains__['id']
    matcher = salt.minion.Matcher({'id': minion_id}, __salt__)
    try:
        return matcher.list_match(tgt)
    except Exception as exc:
        log.exception(exc)
        return False


def pcre(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given pcre target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: Helium

    CLI Example:

    .. code-block:: bash

        salt '*' match.pcre '.*'
    '''
    if minion_id is not None:
        if not isinstance(minion_id, string_types):
            minion_id = str(minion_id)
    else:
        minion_id = __grains__['id']
    matcher = salt.minion.Matcher({'id': minion_id}, __salt__)
    try:
        return matcher.pcre_match(tgt)
    except Exception as exc:
        log.exception(exc)
        return False


def glob(tgt, minion_id=None):
    '''
    Return True if the minion ID matches the given glob target

    minion_id
        Specify the minion ID to match against the target expression

        .. versionadded:: Helium

    CLI Example:

    .. code-block:: bash

        salt '*' match.glob '*'
    '''
    if minion_id is not None:
        if not isinstance(minion_id, string_types):
            minion_id = str(minion_id)
    else:
        minion_id = __grains__['id']
    matcher = salt.minion.Matcher({'id': minion_id}, __salt__)
    try:
        return matcher.glob_match(tgt)
    except Exception as exc:
        log.exception(exc)
        return False

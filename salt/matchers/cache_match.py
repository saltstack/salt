# -*- coding: utf-8 -*-
'''
This is the default cache matcher function.  It only exists for the master,
this is why there is only a ``mmatch()`` but not ``match()``.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging
from salt.defaults import DEFAULT_TARGET_DELIM  # pylint: disable=3rd-party-module-not-gated

import salt.utils.data  # pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


def match(tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Reads in the grains glob match
    '''
    log.debug('grains target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for grains match '
                  'statement from master')
        return False
    return salt.utils.data.subdict_match(
        self.opts['grains'], tgt, delimiter=delimiter
    )


def mmatch(self,
           expr,
           delimiter,
           greedy,
           search_type,
           regex_match=False,
           exact_match=False):
    '''
    Helper function to search for minions in master caches
    If 'greedy' return accepted minions that matched by the condition or absend in the cache.
    If not 'greedy' return the only minions have cache data and matched by the condition.
    '''
    cache_enabled = self.opts.get('minion_data_cache', False)

    def list_cached_minions():
        return self.cache.list('minions')

    if greedy:
        minions = []
        for fn_ in salt.utils.data.sorted_ignorecase(os.listdir(os.path.join(self.opts['pki_dir'], self.acc))):
            if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, fn_)):
                minions.append(fn_)
    elif cache_enabled:
        minions = list_cached_minions()
    else:
        return {'minions': [],
                'missing': []}

    if cache_enabled:
        if greedy:
            cminions = list_cached_minions()
        else:
            cminions = minions
        if not cminions:
            return {'minions': minions,
                    'missing': []}
        minions = set(minions)
        for id_ in cminions:
            if greedy and id_ not in minions:
                continue
            mdata = self.cache.fetch('minions/{0}'.format(id_), 'data')
            if mdata is None:
                if not greedy:
                    minions.remove(id_)
                continue
            search_results = mdata.get(search_type)
            if not salt.utils.data.subdict_match(search_results,
                                                 expr,
                                                 delimiter=delimiter,
                                                 regex_match=regex_match,
                                                 exact_match=exact_match):
                minions.remove(id_)
        minions = list(minions)
    return {'minions': minions,
            'missing': []}

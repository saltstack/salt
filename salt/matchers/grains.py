# -*- coding: utf-8 -*-
'''
This is the default set of grains matcher functions.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging
from salt.defaults import DEFAULT_TARGET_DELIM  # pylint: disable=3rd-party-module-not-gated

import salt.utils.data  # pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


def grain_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
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


def grain_pcre_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Matches a grain based on regex
    '''
    log.debug('grains pcre target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for grains pcre match '
                  'statement from master')
        return False
    return salt.utils.data.subdict_match(
        self.opts['grains'], tgt, delimiter=delimiter, regex_match=True)

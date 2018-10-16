# -*- coding: utf-8 -*-
'''
This is the default grains matcher function.
'''
from __future__ import absolute_import, print_function, unicode_literals

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
        __opts__['grains'], tgt, delimiter=delimiter
    )

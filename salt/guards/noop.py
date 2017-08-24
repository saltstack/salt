# -*- coding: utf-8 -*-
'''
Noop guard that logs each data structure at the debug level
'''
from __future__ import absolute_import

# Import Python libs
import json
import logging

log = logging.getLogger(__name__)


def check_chunks(chunks):
    log.debug('NOOP GUARD CHUNKS OUTPUT START')
    log.debug(json.dumps(chunks, indent=2))
    log.debug('NOOP GUARD CHUNKS OUTPUT END')
    return []


def check_state(chunk):
    log.debug('NOOP GUARD STATE OUTPUT START')
    log.debug(json.dumps(chunk, indent=2))
    log.debug('NOOP GUARD STATE OUTPUT END')
    return []

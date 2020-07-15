# -*- coding: utf-8 -*-
"""
This is the default pillar matcher function.
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

import salt.utils.data  # pylint: disable=3rd-party-module-not-gated
from salt.defaults import (  # pylint: disable=3rd-party-module-not-gated
    DEFAULT_TARGET_DELIM,
)

log = logging.getLogger(__name__)


def match(tgt, delimiter=DEFAULT_TARGET_DELIM, opts=None):
    """
    Reads in the pillar glob match
    """
    if not opts:
        opts = __opts__
    log.debug("pillar target: %s", tgt)
    if delimiter not in tgt:
        log.error(
            "Got insufficient arguments for pillar match " "statement from master"
        )
        return False

    if "pillar" in opts:
        pillar = opts["pillar"]
    elif "ext_pillar" in opts:
        log.info("No pillar found, fallback to ext_pillar")
        pillar = opts["ext_pillar"]

    return salt.utils.data.subdict_match(pillar, tgt, delimiter=delimiter)

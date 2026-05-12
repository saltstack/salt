"""
External pillar module for testing the contents of __opts__ as seen
by external pillar modules.

Returns a hash of the name of the pillar module as defined in
_virtual__ with the value __opts__
"""

import logging

# Set up logging
log = logging.getLogger(__name__)

# DRY up the name we use
MY_NAME = "ext_pillar_opts"


def __virtual__():
    log.debug("Loaded external pillar %s as %s", __name__, MY_NAME)
    return True


def ext_pillar(minion_id, pillar, *args):
    return {MY_NAME: __opts__}

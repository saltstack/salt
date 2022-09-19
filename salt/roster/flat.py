"""
Read in the roster from a flat file using the renderer system
"""

import logging

import salt.config
import salt.loader
from salt.roster import get_roster_file
from salt.template import compile_template

log = logging.getLogger(__name__)


def targets(tgt, tgt_type="glob", **kwargs):
    """
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    """
    template = get_roster_file(__opts__)

    rend = salt.loader.render(__opts__, {})
    raw = compile_template(
        template,
        rend,
        __opts__["renderer"],
        __opts__["renderer_blacklist"],
        __opts__["renderer_whitelist"],
        mask_value="*passw*",
        **kwargs
    )
    conditioned_raw = {}
    for minion in raw:
        conditioned_raw[str(minion)] = salt.config.apply_sdb(raw[minion])
    return __utils__["roster_matcher.targets"](conditioned_raw, tgt, tgt_type, "ipv4")

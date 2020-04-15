# -*- coding: utf-8 -*-
"""
This is the default glob matcher function.
"""
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch

from salt.ext import six  # pylint: disable=3rd-party-module-not-gated


def match(tgt, opts=None):
    """
    Returns true if the passed glob matches the id
    """
    if not opts:
        opts = __opts__
    minion_id = opts.get("minion_id", opts["id"])
    if not isinstance(tgt, six.string_types):
        return False

    return fnmatch.fnmatch(minion_id, tgt)

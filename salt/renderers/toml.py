# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import warnings

# Import salt libs
import salt.utils.url
from salt.serializers.toml import deserialize

log = logging.getLogger(__name__)


def render(sls_data, saltenv="base", sls="", **kws):
    """
    Accepts TOML as a string or as a file object and runs it through the
    parser.

    :rtype: A Python data structure
    """
    with warnings.catch_warnings(record=True) as warn_list:
        data = deserialize(sls_data) or {}

        for item in warn_list:
            log.warning(
                "%s found in %s saltenv=%s",
                item.message,
                salt.utils.url.create(sls),
                saltenv,
            )

        log.debug("Results of SLS rendering: \n%s", data)

    return data

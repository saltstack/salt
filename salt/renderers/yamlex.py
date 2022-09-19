import logging
import warnings

import salt.utils.url
from salt.serializers.yamlex import deserialize

log = logging.getLogger(__name__)


def render(sls_data, saltenv="base", sls="", **kws):
    """
    Accepts YAML_EX as a string or as a file object and runs it through the YAML_EX
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

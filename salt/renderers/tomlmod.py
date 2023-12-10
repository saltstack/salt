import logging
import warnings

import salt.serializers.tomlmod
import salt.utils.url

log = logging.getLogger(__name__)


__virtualname__ = "toml"


def __virtual__():
    if salt.serializers.tomlmod.HAS_TOML is False:
        return (False, "The 'toml' library is missing")
    return __virtualname__


def render(sls_data, saltenv="base", sls="", **kws):
    """
    Accepts TOML as a string or as a file object and runs it through the
    parser.

    :rtype: A Python data structure
    """
    with warnings.catch_warnings(record=True) as warn_list:
        data = salt.serializers.tomlmod.deserialize(sls_data) or {}

        for item in warn_list:
            log.warning(
                "%s found in %s saltenv=%s",
                item.message,
                salt.utils.url.create(sls),
                saltenv,
            )

        log.debug("Results of SLS rendering: \n%s", data)

    return data

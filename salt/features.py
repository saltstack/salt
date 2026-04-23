import logging

import salt.utils.versions

log = logging.getLogger(__name__)


def setup_features(opts):
    """
    Setup the features grain
    """
    if "features" not in opts:
        opts["features"] = {}

    # Check for x509_v2 feature flag
    if "x509_v2" not in opts["features"]:
        # x509_v2 is enabled by default from Salt 3008 (Argon) onwards
        opts["features"]["x509_v2"] = True

    # Check for enable_deprecated_module_search_path_priority feature flag
    if "enable_deprecated_module_search_path_priority" not in opts["features"]:
        opts["features"]["enable_deprecated_module_search_path_priority"] = False

    if opts["features"]:
        for feature in opts["features"]:
            salt.utils.versions.warn_until(
                3009,
                "Please stop checking feature flags using 'salt.features' and instead "
                "check them in the '__opts__' dictionary directly. "
                "'salt.features' module will go away in {version}.",
            )

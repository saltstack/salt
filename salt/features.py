"""
Feature flags
"""

import logging

log = logging.getLogger(__name__)


class Features:
    def __init__(self, _features=None):
        if _features is None:
            self.features = {}
        else:
            self.features = _features
        self.setup = False

    def setup_features(self, opts):
        if not self.setup:
            if "features" not in opts:
                opts["features"] = {}

            # x509_v2 is enabled by default from Salt 3008 (Argon) onwards
            if "x509_v2" not in opts["features"]:
                opts["features"]["x509_v2"] = True

            if "enable_deprecated_module_search_path_priority" not in opts["features"]:
                opts["features"][
                    "enable_deprecated_module_search_path_priority"
                ] = False

            self.features.update(opts.get("features", {}))
        else:
            log.warning("Features already setup")

    def get(self, key, default=None):
        import salt.utils.versions

        salt.utils.versions.warn_until(
            3009,
            "Please stop checking feature flags using 'salt.features' and instead "
            "check the 'features' keyword on the configuration dictionary. The "
            "'salt.features' module will go away in {version}.",
        )
        return self.features.get(key, default)


features = Features()
setup_features = features.setup_features

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
            self.features.update(opts.get("features", {}))
        else:
            log.warning("Features already setup")

    def get(self, key, default=None):
        import salt.utils.versions

        salt.utils.versions.warn_until(
            3008,
            "Please stop checking feature flags using 'salt.features' and instead "
            "check the 'features' keyword on the configuration dictionary. The "
            "'salt.features' module will go away in {version}.",
        )
        return self.features.get(key, default)


features = Features()
setup_features = features.setup_features

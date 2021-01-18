"""
Feature flags
"""
import logging

log = logging.getLogger(__name__)


class Features:

    __slots__ = ("features", "setup")

    def __init__(self, _features=None):
        if _features is None:
            _features = {}
        self.features = _features
        self.setup = False

    def setup_features(self, opts):
        if self.setup is True:
            log.warning("Features already setup")
            return
        self.setup = True
        if "features" not in opts:
            return
        if not opts["features"]:
            return
        self.features.update(opts["features"])

    def get(self, key, default=None):
        return self.features.get(key, default)


features = Features()
setup_features = features.setup_features

import salt.config
import salt.loader
from tests.support.unit import TestCase


class ConfirmTop(TestCase):
    def setUp(self):
        opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.matchers = salt.loader.matchers(opts)

    def test_sanity(self):
        match = self.matchers["confirm_top.confirm_top"]
        self.assertTrue(match("*", []))

import salt.executors.splay as splay_exec
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class SplayTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {splay_exec: {"__grains__": {"id": "foo"}}}

    def test__get_hash(self):
        # We just want to make sure that this function does not result in an
        # error due to passing a unicode value to bytearray()
        assert splay_exec._get_hash()

import shutil
import tempfile

import salt.runners.net as net
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf


@skipIf(not net.HAS_NAPALM, "napalm module required for this test")
class NetTest(TestCase, LoaderModuleMockMixin):
    """
    Test the net runner
    """

    def setup_loader_modules(self):
        mock_get = MagicMock(return_value={})
        self.extmods_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.extmods_dir, ignore_errors=True)
        return {
            net: {
                "__opts__": {
                    "optimization_order": [0, 1, 2],
                    "renderer": "yaml",
                    "renderer_blacklist": [],
                    "renderer_whitelist": [],
                    "extension_modules": self.extmods_dir,
                },
                "__salt__": {"mine.get": mock_get},
            }
        }

    def test_interfaces(self):
        ret = net.interfaces()
        self.assertEqual(None, ret)

    def test_findarp(self):
        ret = net.findarp()
        self.assertEqual(None, ret)

    def test_findmac(self):
        ret = net.findmac()
        self.assertEqual(None, ret)

    def test_lldp(self):
        ret = net.lldp()
        self.assertEqual(None, ret)

    def test_find(self):
        ret = net.find("")
        self.assertEqual({}, ret)

    def test_multi_find(self):
        ret = net.multi_find()
        self.assertEqual(None, ret)

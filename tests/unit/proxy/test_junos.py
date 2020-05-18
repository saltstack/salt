# -*- coding: utf-8 -*-
import salt.proxy.junos as junos

import sys

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

if sys.version < "3":
    from salt.ext.six import StringIO
else:
    from io import BytesIO as StringIO

try:
    from jnpr.junos.device import Device  # pylint: disable=unused-import
    from jnpr.junos.exception import ConnectError
    import jxmlease  # pylint: disable=unused-import

    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False


@skipIf(not HAS_JUNOS, "The junos-eznc and jxmlease modules are required")
class JunosProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            junos: {
                "__virtual__": MagicMock(return_value="junos"),
                "DETAILS": {},
                "__pillar__": {},
            }
        }

    def setUp(self):
        self.opts = {"proxy": {"username": "xxxx", "password]": "xxx", "host": "junos"}}

    @patch("ncclient.manager.connect")
    def test_init(self, mock_connect):
        junos.init(self.opts)
        self.assertTrue(junos.thisproxy.get("initialized"))

    @patch("ncclient.manager.connect")
    def test_init_err(self, mock_connect):
        mock_connect.side_effect = ConnectError
        junos.init(self.opts)
        self.assertFalse(junos.thisproxy.get("initialized"))

    @patch("ncclient.manager.connect")
    def test_alive(self, mock_connect):
        junos.init(self.opts)
        junos.thisproxy["conn"]._conn._session._buffer = StringIO()
        self.assertTrue(junos.alive(self.opts))
        self.assertTrue(junos.thisproxy.get("initialized"))

"""
    :codeauthor: Alan Somers <asomers@gmail.com>
"""


import re

import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import salt.modules.bsd_shadow as shadow

    HAS_SHADOW = True
except ImportError:
    HAS_SHADOW = False

# Although bsd_shadow runs on NetBSD and OpenBSD as well, the mocks are
# currently only designed for FreeBSD.
@skipIf(not salt.utils.platform.is_freebsd(), "minion is not FreeBSD")
@skipIf(not HAS_SHADOW, "shadow module is not available")
class BSDShadowTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            shadow: {
                "__grains__": {"kernel": "FreeBSD", "os": "FreeBSD"},
                "__salt__": {"cmd.has_exec": MagicMock(return_value=True)},
            }
        }

    def test_del_password(self):
        """
        Test shadow.del_password
        """
        info_mock = MagicMock(return_value="root::0:0::0:0:Charlie &:/root:/bin/sh")
        usermod_mock = MagicMock(return_value=0)
        with patch.dict(shadow.__salt__, {"cmd.run_stdout": info_mock}):
            with patch.dict(shadow.__salt__, {"cmd.run": usermod_mock}):
                shadow.del_password("root")
        usermod_mock.assert_called_once_with(
            "pw user mod root -w none", output_loglevel="quiet", python_shell=False
        )

    def test_gen_password(self):
        """
        Test shadow.gen_password
        """
        self.assertEqual(
            "$6$salt$wZU8LXJfJJqoagopbB7RuK6JEotEMZ0CQDy0phpPAuLMYQFcmf6L6BdAbs/Q7w7o1qsZ9pFqFVY4yuUSWgaYt1",
            shadow.gen_password("x", crypt_salt="salt", algorithm="sha512"),
        )
        self.assertEqual(
            "$5$salt$eC8iHMk0B/acxRGi4idWiCK/.xXHLUsxovn4V591t3.",
            shadow.gen_password("x", crypt_salt="salt", algorithm="sha256"),
        )

    def test_info(self):
        """
        Test shadow.info
        """
        mock = MagicMock(return_value="root:*:0:0::42:69:Charlie &:/root:/bin/sh")
        with patch.dict(shadow.__salt__, {"cmd.run_stdout": mock}):
            info = shadow.info("root")
        self.assertEqual("root", info["name"])
        self.assertEqual(42, info["change"])
        self.assertEqual(69, info["expire"])
        self.assertTrue(
            info["passwd"] == "*"  # if the test is not running as root
            or re.match(r"^\$[0-9]\$", info["passwd"])  # modular format
            or re.match(r"^_", info["passwd"])  # DES Extended format
            or info["passwd"] == ""  # No password
            or re.match(r"^\*LOCKED\*", info["passwd"])  # Locked account
        )

    def test_set_change(self):
        """
        Test shadow.set_change
        """
        info_mock = MagicMock(return_value="root:*:0:0::0:0:Charlie &:/root:/bin/sh")
        usermod_mock = MagicMock(return_value=0)
        with patch.dict(shadow.__salt__, {"cmd.run_stdout": info_mock}):
            with patch.dict(shadow.__salt__, {"cmd.run": usermod_mock}):
                shadow.set_change("root", 42)
        usermod_mock.assert_called_once_with(
            ["pw", "user", "mod", "root", "-f", 42], python_shell=False
        )

    def test_set_expire(self):
        """
        Test shadow.set_expire
        """
        info_mock = MagicMock(return_value="root:*:0:0::0:0:Charlie &:/root:/bin/sh")
        usermod_mock = MagicMock(return_value=0)
        with patch.dict(shadow.__salt__, {"cmd.run_stdout": info_mock}):
            with patch.dict(shadow.__salt__, {"cmd.run": usermod_mock}):
                shadow.set_expire("root", 42)
        usermod_mock.assert_called_once_with(
            ["pw", "user", "mod", "root", "-e", 42], python_shell=False
        )

    def test_set_password(self):
        """
        Test shadow.set_password
        """
        PASSWORD = "$6$1jReqE6eU.b.fl0X$lzsxgaP6kgPyW0kxeDhAn0ySH08gn5A3At0NDHRFUSkk/6s4hCgE9OTpSsNs1Vcvws3zN0lEXkxCYeZoTVY4A1"
        info_mock = MagicMock(return_value="root:%s:0:0::0:0:Charlie &:/root:/bin/sh")
        usermod_mock = MagicMock(return_value=0)
        with patch.dict(shadow.__salt__, {"cmd.run_stdout": info_mock}):
            with patch.dict(shadow.__salt__, {"cmd.run": usermod_mock}):
                shadow.set_password("root", PASSWORD)
        usermod_mock.assert_called_once_with(
            ["pw", "user", "mod", "root", "-H", "0"],
            stdin=PASSWORD,
            output_loglevel="quiet",
            python_shell=False,
        )

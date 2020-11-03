import salt.utils.platform
from tests.support.case import SSHCase
from tests.support.helpers import slowTest
from tests.support.unit import skipIf


@skipIf(salt.utils.platform.is_windows(), "salt-ssh not available on Windows")
class SSHGrainsTest(SSHCase):
    """
    testing grains with salt-ssh
    """

    @slowTest
    def test_grains_items(self):
        """
        test grains.items with salt-ssh
        """
        ret = self.run_function("grains.items")
        if salt.utils.platform.is_darwin():
            grain = "Darwin"
        elif salt.utils.platform.is_aix():
            grain = "AIX"
        elif salt.utils.platform.is_freebsd():
            grain = "FreeBSD"
        else:
            grain = "Linux"
        self.assertEqual(ret["kernel"], grain)
        self.assertTrue(isinstance(ret, dict))

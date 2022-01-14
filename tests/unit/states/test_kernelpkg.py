"""
    :synopsis: Unit Tests for 'module.aptkernelpkg'
    :platform: Linux
    :maturity: develop
    versionadded:: 2018.3.0
"""
# pylint: disable=invalid-name,no-member


try:
    # Import Salt Testing Libs
    from tests.support.mixins import LoaderModuleMockMixin
    from tests.support.unit import skipIf, TestCase
    from tests.support.mock import MagicMock, patch

    # Import Salt Libs
    import salt.states.kernelpkg as kernelpkg

    HAS_MODULES = True
except ImportError:
    HAS_MODULES = False

KERNEL_LIST = ["4.4.0-70-generic", "4.4.0-71-generic", "4.5.1-14-generic"]
STATE_NAME = "kernelpkg-test"


@skipIf(not HAS_MODULES, "Salt modules could not be loaded")
class KernelPkgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.aptpkg
    """

    def setup_loader_modules(self):
        return {
            kernelpkg: {
                "__salt__": {
                    "system.reboot": MagicMock(return_value=None),
                    "kernelpkg.upgrade": MagicMock(
                        return_value={
                            "upgrades": {"kernel": {"old": "1.0.0", "new": "2.0.0"}}
                        }
                    ),
                    "kernelpkg.active": MagicMock(return_value=0),
                    "kernelpkg.latest_installed": MagicMock(return_value=0),
                }
            }
        }

    def test_latest_installed_with_changes(self):
        """
        Test - latest_installed when an upgrade is available
        """
        installed = MagicMock(return_value=KERNEL_LIST[:-1])
        upgrade = MagicMock(return_value=KERNEL_LIST[-1])
        with patch.dict(kernelpkg.__salt__, {"kernelpkg.list_installed": installed}):
            with patch.dict(
                kernelpkg.__salt__, {"kernelpkg.latest_available": upgrade}
            ):
                with patch.dict(kernelpkg.__opts__, {"test": False}):
                    kernelpkg.__salt__["kernelpkg.upgrade"].reset_mock()
                    ret = kernelpkg.latest_installed(name=STATE_NAME)
                    self.assertEqual(ret["name"], STATE_NAME)
                    self.assertTrue(ret["result"])
                    self.assertIsInstance(ret["changes"], dict)
                    self.assertIsInstance(ret["comment"], str)
                    kernelpkg.__salt__["kernelpkg.upgrade"].assert_called_once()

                with patch.dict(kernelpkg.__opts__, {"test": True}):
                    kernelpkg.__salt__["kernelpkg.upgrade"].reset_mock()
                    ret = kernelpkg.latest_installed(name=STATE_NAME)
                    self.assertEqual(ret["name"], STATE_NAME)
                    self.assertIsNone(ret["result"])
                    self.assertDictEqual(ret["changes"], {})
                    self.assertIsInstance(ret["comment"], str)
                    kernelpkg.__salt__["kernelpkg.upgrade"].assert_not_called()

    def test_latest_installed_at_latest(self):
        """
        Test - latest_installed when no upgrade is available
        """
        installed = MagicMock(return_value=KERNEL_LIST)
        upgrade = MagicMock(return_value=KERNEL_LIST[-1])
        with patch.dict(kernelpkg.__salt__, {"kernelpkg.list_installed": installed}):
            with patch.dict(
                kernelpkg.__salt__, {"kernelpkg.latest_available": upgrade}
            ):
                with patch.dict(kernelpkg.__opts__, {"test": False}):
                    ret = kernelpkg.latest_installed(name=STATE_NAME)
                    self.assertEqual(ret["name"], STATE_NAME)
                    self.assertTrue(ret["result"])
                    self.assertDictEqual(ret["changes"], {})
                    self.assertIsInstance(ret["comment"], str)
                    kernelpkg.__salt__["kernelpkg.upgrade"].assert_not_called()

                with patch.dict(kernelpkg.__opts__, {"test": True}):
                    ret = kernelpkg.latest_installed(name=STATE_NAME)
                    self.assertEqual(ret["name"], STATE_NAME)
                    self.assertTrue(ret["result"])
                    self.assertDictEqual(ret["changes"], {})
                    self.assertIsInstance(ret["comment"], str)
                    kernelpkg.__salt__["kernelpkg.upgrade"].assert_not_called()

    def test_latest_active_with_changes(self):
        """
        Test - latest_active when a new kernel is available
        """
        reboot = MagicMock(return_value=True)
        latest = MagicMock(return_value=1)
        with patch.dict(
            kernelpkg.__salt__,
            {"kernelpkg.needs_reboot": reboot, "kernelpkg.latest_installed": latest},
        ), patch.dict(kernelpkg.__opts__, {"test": False}):
            kernelpkg.__salt__["system.reboot"].reset_mock()
            ret = kernelpkg.latest_active(name=STATE_NAME)
            self.assertEqual(ret["name"], STATE_NAME)
            self.assertTrue(ret["result"])
            self.assertIsInstance(ret["changes"], dict)
            self.assertIsInstance(ret["comment"], str)
            kernelpkg.__salt__["system.reboot"].assert_called_once()

            with patch.dict(kernelpkg.__opts__, {"test": True}):
                kernelpkg.__salt__["system.reboot"].reset_mock()
                ret = kernelpkg.latest_active(name=STATE_NAME)
                self.assertEqual(ret["name"], STATE_NAME)
                self.assertIsNone(ret["result"])
                self.assertDictEqual(ret["changes"], {"kernel": {"new": 1, "old": 0}})
                self.assertIsInstance(ret["comment"], str)
                kernelpkg.__salt__["system.reboot"].assert_not_called()

    def test_latest_active_at_latest(self):
        """
        Test - latest_active when the newest kernel is already active
        """
        reboot = MagicMock(return_value=False)
        with patch.dict(kernelpkg.__salt__, {"kernelpkg.needs_reboot": reboot}):
            with patch.dict(kernelpkg.__opts__, {"test": False}):
                kernelpkg.__salt__["system.reboot"].reset_mock()
                ret = kernelpkg.latest_active(name=STATE_NAME)
                self.assertEqual(ret["name"], STATE_NAME)
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], {})
                self.assertIsInstance(ret["comment"], str)
                kernelpkg.__salt__["system.reboot"].assert_not_called()

            with patch.dict(kernelpkg.__opts__, {"test": True}):
                kernelpkg.__salt__["system.reboot"].reset_mock()
                ret = kernelpkg.latest_active(name=STATE_NAME)
                self.assertEqual(ret["name"], STATE_NAME)
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], {})
                self.assertIsInstance(ret["comment"], str)
                kernelpkg.__salt__["system.reboot"].assert_not_called()

    def test_latest_wait(self):
        """
        Test - latest_wait static results
        """
        ret = kernelpkg.latest_wait(name=STATE_NAME)
        self.assertEqual(ret["name"], STATE_NAME)
        self.assertTrue(ret["result"])
        self.assertDictEqual(ret["changes"], {})
        self.assertIsInstance(ret["comment"], str)

"""
    Test win_chcp
"""

from salt.exceptions import CodePageError
from salt.utils import platform, win_chcp
from tests.support.unit import TestCase, skipIf


@skipIf(not platform.is_windows(), "Windows only tests!")
class CHCPTest(TestCase):
    """
    Test case for salt.utils.win_chcp
    """

    @classmethod
    def setUpClass(cls):
        # Stores the initial code page for _reset_code_page()
        # Intentionally does not catch any exception, to find out which that would be.
        # That exception would then be added to cmdmod.py
        cls._chcp_code = win_chcp.get_codepage_id()

    @classmethod
    def tearDownClass(cls):
        cls._chcp_code = None

    def setUp(self):
        win_chcp.set_codepage_id(self._chcp_code)

    def tearDown(self):
        win_chcp.set_codepage_id(self._chcp_code)

    def test_get_and_set_code_page(self):
        for page in (20424, "20866", 437, 65001, "437"):
            self.assertEqual(win_chcp.set_codepage_id(page), int(page))
            self.assertEqual(win_chcp.get_codepage_id(), int(page))

    def test_bad_page_code(self):
        with win_chcp.chcp(437):
            self.assertEqual(win_chcp.get_codepage_id(), 437)

            bad_codes = ("0", "bad code", 1234, -34, "437 dogs", "(*&^(*^%&$%&")

            for page in bad_codes:
                self.assertEqual(win_chcp.set_codepage_id(page), -1)
                self.assertEqual(win_chcp.get_codepage_id(), 437)

            for page in bad_codes:
                self.assertRaises(CodePageError, win_chcp.set_codepage_id, page, True)

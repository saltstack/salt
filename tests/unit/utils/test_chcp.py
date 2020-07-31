# -*- coding: utf-8 -*-
"""
    Test chcp
"""


from tests.support.unit import TestCase, skipIf
from salt.utils import chcp
from salt.utils import platform


@skipIf(not platform.is_windows(), "Windows only tests!")
class CHCPTest(TestCase):
    """
    Test case for salt.utils.chcp
    """
    def __init__(self, *args, **kwargs):
        # Stores the initial code page for _reset_code_page()
        # Intentionally does not catch any exception, to find out which that would be.
        # That exception would then be added to cmdmod.py
        super().__init__(*args, **kwargs)
        self._chcp_code = chcp.chcp()

    def setUp(self):
        chcp.chcp(self._chcp_code)

    def tearDown(self):
        chcp.chcp(self._chcp_code)

    def test_get_and_set_code_page(self):
        self.assertEqual(self._chcp_code, chcp.chcp())
        for page in (20424, "20866", 437, 65001, "437"):
            self.assertEqual(chcp.chcp(page), str(page))
            self.assertEqual(chcp.chcp(), str(page))

    def test_bad_page_code(self):
        self.assertEqual(chcp.chcp(437), "437")

        bad_codes = ("0", "bad code", 1234, -34, "437 dogs", "(*&^(*^%&$%&")

        for page in bad_codes:
            self.assertEqual(chcp.chcp(page), "437")

        for page in bad_codes:
            self.assertRaises(chcp.CodePageError, chcp.chcp, page, True)

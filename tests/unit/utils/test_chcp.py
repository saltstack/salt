# -*- coding: utf-8 -*-
"""
    Test chcp
"""
import subprocess
import os


from tests.support.unit import TestCase, skipIf
from salt.utils import chcp
from salt.utils import platform


@skipIf(not platform.is_windows(), "Windows only tests!")
class CHCPTest(TestCase):
    """
    Test case for salt.utils.cache.ContextCache
    """
    def __init__(self, *args,  **kwargs):
        super().__init__(*args, **kwargs)

        self._chcp_code = None
        try:
            self._chcp_code = chcp.chcp()
        except Exception as exc:
            self._chcp_code = exc

    def setUp(self):
        self._reset_code_page()

    def tearDown(self):
        self._reset_code_page()

    def _reset_code_page(self):
        if isinstance(self._chcp_code, Exception):
            raise self._chcp_code

        chcp.chcp(self._chcp_code, True)

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

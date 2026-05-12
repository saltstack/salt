"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.utils.filebuffer_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import os

from salt.utils.filebuffer import BufferedReader, InvalidFileMode
from tests.support.paths import BASE_FILES
from tests.support.unit import TestCase


class TestFileBuffer(TestCase):
    def test_read_only_mode(self):
        with self.assertRaises(InvalidFileMode):
            BufferedReader("/tmp/foo", mode="a")

        with self.assertRaises(InvalidFileMode):
            BufferedReader("/tmp/foo", mode="ab")

        with self.assertRaises(InvalidFileMode):
            BufferedReader("/tmp/foo", mode="w")

        with self.assertRaises(InvalidFileMode):
            BufferedReader("/tmp/foo", mode="wb")

    def test_issue_51309(self):
        """
        https://github.com/saltstack/salt/issues/51309
        """
        file_name = os.path.join(BASE_FILES, "grail", "scene33")

        def find_value(text):
            stripped_text = text.strip()
            try:
                with BufferedReader(file_name) as breader:
                    for chunk in breader:
                        if stripped_text in chunk:
                            return True
                return False
            except OSError:
                return False

        self.assertTrue(find_value("We have the Holy Hand Grenade"))

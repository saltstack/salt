"""
Testing ini_manage exec module.
"""

import os
import tempfile

import salt.modules.ini_manage as ini
import salt.utils.files
import salt.utils.stringutils
from tests.support.unit import TestCase


class IniManageTestCase(TestCase):
    """
    Testing ini_manage exec module.
    """

    TEST_FILE_CONTENT = [
        "# Comment on the first line",
        "",
        "# First main option",
        "option1=main1",
        "",
        "# Second main option",
        "option2=main2",
        "",
        "",
        "[main]",
        "# Another comment",
        "test1=value 1",
        "",
        "test2=value 2",
        "",
        "[SectionB]",
        "test1=value 1B",
        "",
        "# Blank line should be above",
        "test3 = value 3B",
        "",
        "[SectionC]",
        "# The following option is empty",
        "empty_option=",
    ]

    maxDiff = None

    def _setUp(self, linesep):
        self.tfile = tempfile.NamedTemporaryFile(delete=False, mode="w+b")
        self.tfile.write(
            salt.utils.stringutils.to_bytes(linesep.join(self.TEST_FILE_CONTENT))
        )
        self.tfile.close()

    def setUp(self):
        self._setUp(os.linesep)

    def tearDown(self):
        os.remove(self.tfile.name)

    def test_get_option(self):
        """
        Test get_option method.
        """
        self.assertEqual(ini.get_option(self.tfile.name, "main", "test1"), "value 1")
        self.assertEqual(ini.get_option(self.tfile.name, "main", "test2"), "value 2")
        self.assertEqual(
            ini.get_option(self.tfile.name, "SectionB", "test1"), "value 1B"
        )
        self.assertEqual(
            ini.get_option(self.tfile.name, "SectionB", "test3"), "value 3B"
        )
        self.assertEqual(
            ini.get_option(self.tfile.name, "SectionC", "empty_option"), ""
        )

    def test_get_section(self):
        """
        Test get_section method.
        """
        self.assertEqual(
            ini.get_section(self.tfile.name, "SectionB"),
            {"test1": "value 1B", "test3": "value 3B"},
        )

    def test_remove_option(self):
        """
        Test remove_option method.
        """
        self.assertEqual(
            ini.remove_option(self.tfile.name, "SectionB", "test1"), "value 1B"
        )
        self.assertIsNone(ini.get_option(self.tfile.name, "SectionB", "test1"))

    def test_remove_section(self):
        """
        Test remove_section method.
        """
        self.assertEqual(
            ini.remove_section(self.tfile.name, "SectionB"),
            {"test1": "value 1B", "test3": "value 3B"},
        )
        self.assertEqual(ini.get_section(self.tfile.name, "SectionB"), {})

    def test_get_ini(self):
        """
        Test get_ini method.
        """
        self.assertEqual(
            dict(ini.get_ini(self.tfile.name)),
            {
                "SectionC": {"empty_option": ""},
                "SectionB": {"test1": "value 1B", "test3": "value 3B"},
                "main": {"test1": "value 1", "test2": "value 2"},
                "option2": "main2",
                "option1": "main1",
            },
        )

    def test_set_option(self):
        """
        Test set_option method.
        """
        result = ini.set_option(
            self.tfile.name,
            {
                "SectionB": {
                    "test3": "new value 3B",
                    "test_set_option": "test_set_value",
                },
                "SectionD": {"test_set_option2": "test_set_value1"},
            },
        )
        self.assertEqual(
            result,
            {
                "SectionB": {
                    "test3": {"after": "new value 3B", "before": "value 3B"},
                    "test_set_option": {"after": "test_set_value", "before": None},
                },
                "SectionD": {
                    "after": {"test_set_option2": "test_set_value1"},
                    "before": None,
                },
            },
        )
        # Check existing option updated
        self.assertEqual(
            ini.get_option(self.tfile.name, "SectionB", "test3"), "new value 3B"
        )
        # Check new section and option added
        self.assertEqual(
            ini.get_option(self.tfile.name, "SectionD", "test_set_option2"),
            "test_set_value1",
        )

    def test_empty_value(self):
        """
        Test empty value preserved after edit
        """
        ini.set_option(self.tfile.name, {"SectionB": {"test3": "new value 3B"}})
        with salt.utils.files.fopen(self.tfile.name, "r") as fp_:
            file_content = salt.utils.stringutils.to_unicode(fp_.read())
        expected = "{0}{1}{0}".format(os.linesep, "empty_option = ")
        self.assertIn(expected, file_content, "empty_option was not preserved")

    def test_empty_lines(self):
        """
        Test empty lines preserved after edit
        """
        ini.set_option(self.tfile.name, {"SectionB": {"test3": "new value 3B"}})
        expected = os.linesep.join(
            [
                "# Comment on the first line",
                "",
                "# First main option",
                "option1 = main1",
                "",
                "# Second main option",
                "option2 = main2",
                "",
                "[main]",
                "# Another comment",
                "test1 = value 1",
                "",
                "test2 = value 2",
                "",
                "[SectionB]",
                "test1 = value 1B",
                "",
                "# Blank line should be above",
                "test3 = new value 3B",
                "",
                "[SectionC]",
                "# The following option is empty",
                "empty_option = ",
                "",
            ]
        )
        with salt.utils.files.fopen(self.tfile.name, "r") as fp_:
            file_content = salt.utils.stringutils.to_unicode(fp_.read())
        self.assertEqual(expected, file_content)

    def test_empty_lines_multiple_edits(self):
        """
        Test empty lines preserved after multiple edits
        """
        ini.set_option(
            self.tfile.name,
            {"SectionB": {"test3": "this value will be edited two times"}},
        )
        self.test_empty_lines()

    def test_newline_characters(self):
        """
        Test newline characters
        """
        for c in ["\n", "\r", "\r\n"]:
            for test in [
                self.test_get_option,
                self.test_get_section,
                self.test_remove_option,
                self.test_remove_section,
                self.test_get_ini,
                self.test_set_option,
                self.test_empty_value,
                self.test_empty_lines,
                self.test_empty_lines_multiple_edits,
            ]:
                self.tearDown()
                self._setUp(c)
                test()

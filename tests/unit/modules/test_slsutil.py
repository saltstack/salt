import logging

import salt.exceptions
import salt.modules.slsutil as slsutil
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.unit import TestCase

log = logging.getLogger(__name__)

MASTER_DIRS = ["red", "red/files", "blue", "blue/files"]

MASTER_FILES = [
    "top.sls",
    "red/init.sls",
    "red/files/default.conf",
    "blue/init.sls",
    "blue/files/default.conf",
]


class SlsUtilTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.slsutil
    """

    def setup_loader_modules(self):
        return {
            slsutil: {
                "__salt__": {
                    "cp.list_master": MagicMock(return_value=MASTER_FILES),
                    "cp.list_master_dirs": MagicMock(return_value=MASTER_DIRS),
                },
            }
        }

    def test_banner(self):
        """
        Test banner function
        """
        self.check_banner()
        self.check_banner(width=81)
        self.check_banner(width=20)
        self.check_banner(commentchar="//", borderchar="-")
        self.check_banner(title="title here", text="text here")
        self.check_banner(commentchar=" *")

    def check_banner(
        self,
        width=72,
        commentchar="#",
        borderchar="#",
        blockstart=None,
        blockend=None,
        title=None,
        text=None,
        newline=True,
    ):

        result = slsutil.banner(
            width=width,
            commentchar=commentchar,
            borderchar=borderchar,
            blockstart=blockstart,
            blockend=blockend,
            title=title,
            text=text,
            newline=newline,
        ).splitlines()
        for line in result:
            self.assertEqual(len(line), width)
            self.assertTrue(line.startswith(commentchar))
            self.assertTrue(line.endswith(commentchar.strip()))

    def test_boolstr(self):
        """
        Test boolstr function
        """
        self.assertEqual("yes", slsutil.boolstr(True, true="yes", false="no"))
        self.assertEqual("no", slsutil.boolstr(False, true="yes", false="no"))

    def test_file_exists(self):
        """
        Test file_exists function
        """
        self.assertTrue(slsutil.file_exists("red/init.sls"))
        self.assertFalse(slsutil.file_exists("green/init.sls"))

    def test_dir_exists(self):
        """
        Test dir_exists function
        """
        self.assertTrue(slsutil.dir_exists("red"))
        self.assertFalse(slsutil.dir_exists("green"))

    def test_path_exists(self):
        """
        Test path_exists function
        """
        self.assertTrue(slsutil.path_exists("red"))
        self.assertFalse(slsutil.path_exists("green"))
        self.assertTrue(slsutil.path_exists("red/init.sls"))
        self.assertFalse(slsutil.path_exists("green/init.sls"))

    def test_findup(self):
        """
        Test findup function
        """
        self.assertEqual("red/init.sls", slsutil.findup("red/files", "init.sls"))
        self.assertEqual("top.sls", slsutil.findup("red/files", ["top.sls"]))
        self.assertEqual("top.sls", slsutil.findup("", "top.sls"))
        self.assertEqual("top.sls", slsutil.findup(None, "top.sls"))
        self.assertEqual(
            "red/init.sls", slsutil.findup("red/files", ["top.sls", "init.sls"])
        )

        with self.assertRaises(salt.exceptions.CommandExecutionError):
            slsutil.findup("red/files", "notfound")

        with self.assertRaises(salt.exceptions.CommandExecutionError):
            slsutil.findup("red", "default.conf")

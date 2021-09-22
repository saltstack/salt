"""
    :codeauthor: Ted Strzalkowski (tedski@gmail.com)


    tests.unit.modules.mdadm_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
import re
import sys

import pytest
import salt.modules.mdadm_raid as mdadm
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MdadmTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {mdadm: {}}

    @pytest.mark.skipif(
        sys.version_info < (3, 6), reason="Py3.5 dictionaries are not ordered"
    )
    def test_create(self):
        mock = MagicMock(return_value="salt")
        with patch.dict(mdadm.__salt__, {"cmd.run": mock}), patch(
            "salt.utils.path.which", lambda exe: exe
        ):
            ret = mdadm.create(
                "/dev/md0",
                5,
                devices=["/dev/sdb1", "/dev/sdc1", "/dev/sdd1"],
                test_mode=False,
                force=True,
                chunk=256,
            )
            self.assertEqual("salt", ret)
            mock.assert_called_with(
                [
                    "mdadm",
                    "-C",
                    "/dev/md0",
                    "-R",
                    "-v",
                    "-l",
                    "5",
                    "--force",
                    "--chunk",
                    "256",
                    "-e",
                    "default",
                    "-n",
                    "3",
                    "/dev/sdb1",
                    "/dev/sdc1",
                    "/dev/sdd1",
                ],
                python_shell=False,
            )

    @pytest.mark.skipif(
        sys.version_info < (3, 6), reason="Py3.5 dictionaries are not ordered"
    )
    def test_create_metadata(self):
        mock = MagicMock(return_value="salt")
        with patch.dict(mdadm.__salt__, {"cmd.run": mock}), patch(
            "salt.utils.path.which", lambda exe: exe
        ):
            ret = mdadm.create(
                "/dev/md0",
                5,
                devices=["/dev/sdb1", "/dev/sdc1", "/dev/sdd1"],
                metadata=0.9,
                test_mode=False,
                force=True,
                chunk=256,
            )
            self.assertEqual("salt", ret)
            mock.assert_called_with(
                [
                    "mdadm",
                    "-C",
                    "/dev/md0",
                    "-R",
                    "-v",
                    "-l",
                    "5",
                    "--force",
                    "--chunk",
                    "256",
                    "-e",
                    "0.9",
                    "-n",
                    "3",
                    "/dev/sdb1",
                    "/dev/sdc1",
                    "/dev/sdd1",
                ],
                python_shell=False,
            )

    def test_create_test_mode(self):
        mock = MagicMock()
        with patch.dict(mdadm.__salt__, {"cmd.run": mock}):
            ret = mdadm.create(
                "/dev/md0",
                5,
                devices=["/dev/sdb1", "/dev/sdc1", "/dev/sdd1"],
                force=True,
                chunk=256,
                test_mode=True,
            )
            self.assertEqual(
                sorted(
                    "mdadm -C /dev/md0 -R -v --chunk 256 "
                    "--force -l 5 -e default -n 3 "
                    "/dev/sdb1 /dev/sdc1 /dev/sdd1".split()
                ),
                sorted(ret.split()),
            )
            assert not mock.called, "test mode failed, cmd.run called"

    def test_examine(self):
        """
        Test for mdadm_raid.examine
        """
        mock = MagicMock(
            return_value=(
                "ARRAY /dev/md/pool metadata=1.2"
                " UUID=567da122:fb8e445e:55b853e0:81bd0a3e name=positron:pool"
            )
        )
        with patch.dict(mdadm.__salt__, {"cmd.run_stdout": mock}):
            self.assertEqual(
                mdadm.examine("/dev/md0"),
                {
                    "ARRAY /dev/md/pool metadata": (
                        "1.2 UUID=567da122:fb8e445e:55b853e0:81bd0a3e"
                        " name=positron:pool"
                    )
                },
            )
            mock.assert_called_with(
                "mdadm -Y -E /dev/md0", ignore_retcode=False, python_shell=False
            )

    def test_examine_quiet(self):
        """
        Test for mdadm_raid.examine
        """
        mock = MagicMock(return_value="")
        with patch.dict(mdadm.__salt__, {"cmd.run_stdout": mock}):
            self.assertEqual(mdadm.examine("/dev/md0", quiet=True), {})
            mock.assert_called_with(
                "mdadm -Y -E /dev/md0", ignore_retcode=True, python_shell=False
            )

    def test_device_match_regex_pattern(self):
        assert re.match(
            mdadm._VOL_REGEX_PATTERN_MATCH.format("/dev/md/1"),
            "ARRAY /dev/md/1  metadata=1.2 UUID=51f245bc:a1402c8a:2d598e79:589c07cf"
            " name=tst-ob-001:1",
        )
        assert not re.match(
            mdadm._VOL_REGEX_PATTERN_MATCH.format("/dev/md/1"),
            "ARRAY /dev/md/10  metadata=1.2 UUID=51f245bc:a1402c8a:2d598e79:589c07cf"
            " name=tst-ob-001:1",
        )

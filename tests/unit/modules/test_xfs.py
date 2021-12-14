import textwrap

import salt.modules.xfs as xfs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


@patch("salt.modules.xfs._get_mounts", MagicMock(return_value={}))
class XFSTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.xfs
    """

    def setup_loader_modules(self):
        return {xfs: {}}

    def test__blkid_output(self):
        """
        Test xfs._blkid_output when there is data
        """
        blkid_export = textwrap.dedent(
            """
            DEVNAME=/dev/sda1
            UUID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            TYPE=xfs
            PARTUUID=YYYYYYYY-YY

            DEVNAME=/dev/sdb1
            PARTUUID=ZZZZZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZZZZZZZZZ
            """
        )
        # We expect to find only data from /dev/sda1, nothig from
        # /dev/sdb1
        self.assertEqual(
            xfs._blkid_output(blkid_export),
            {
                "/dev/sda1": {
                    "label": None,
                    "partuuid": "YYYYYYYY-YY",
                    "uuid": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                }
            },
        )

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

    def test__parse_xfs_info(self):
        """
        Test parsing output from mkfs.xfs.
        """
        data = textwrap.dedent(
            """
            meta-data=/dev/vg00/testvol      isize=512    agcount=4, agsize=1310720 blks
                     =                       sectsz=4096  attr=2, projid32bit=1
                     =                       crc=1        finobt=1, sparse=1, rmapbt=0
                     =                       reflink=1
            data     =                       bsize=4096   blocks=5242880, imaxpct=25
                     =                       sunit=0      swidth=0 blks
            naming   =version 2              bsize=4096   ascii-ci=0, ftype=1
            log      =internal log           bsize=4096   blocks=2560, version=2
                     =                       sectsz=4096  sunit=1 blks, lazy-count=1
            realtime =none                   extsz=4096   blocks=0, rtextents=0
            Discarding blocks...Done.
            """
        )

        self.assertEqual(
            xfs._parse_xfs_info(data),
            {
                "meta-data": {
                    "section": "/dev/vg00/testvol",
                    "isize": "512",
                    "agcount": "4",
                    "agsize": "1310720 blks",
                    "sectsz": "4096",
                    "attr": "2",
                    "projid32bit": "1",
                    "crc": "1",
                    "finobt": "1",
                    "sparse": "1",
                    "rmapbt": "0",
                    "reflink": "1",
                },
                "data": {
                    "section": "data",
                    "bsize": "4096",
                    "blocks": "5242880",
                    "imaxpct": "25",
                    "sunit": "0",
                    "swidth": "0 blks",
                },
                "naming": {
                    "section": "version 2",
                    "bsize": "4096",
                    "ascii-ci": "0",
                    "ftype": "1",
                },
                "log": {
                    "section": "internal log",
                    "bsize": "4096",
                    "blocks": "2560",
                    "version": "2",
                    "sectsz": "4096",
                    "sunit": "1 blks",
                    "lazy-count": "1",
                },
                "realtime": {
                    "section": "none",
                    "extsz": "4096",
                    "blocks": "0",
                    "rtextents": "0",
                },
            },
        )

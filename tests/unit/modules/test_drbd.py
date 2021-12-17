"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.drbd as drbd
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DrbdTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.drbd
    """

    def setup_loader_modules(self):
        return {drbd: {}}

    # 'overview' function tests: 1

    def test_overview(self):
        """
        Test if it shows status of the DRBD devices
        """
        ret = {
            "connection state": "True",
            "device": "Stack",
            "fs": "None",
            "local disk state": "UpToDate",
            "local role": "master",
            "minor number": "Salt",
            "mountpoint": "True",
            "partner disk state": "UpToDate",
            "partner role": "minion",
            "percent": "888",
            "remains": "666",
            "total size": "50",
            "used": "50",
        }
        mock = MagicMock(
            return_value=(
                "Salt:Stack True master/minion UpToDate/UpToDate True None 50 50 666 888"
            )
        )
        with patch.dict(drbd.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(drbd.overview(), ret)

        ret = {
            "connection state": "True",
            "device": "Stack",
            "local disk state": "UpToDate",
            "local role": "master",
            "minor number": "Salt",
            "partner disk state": "partner",
            "partner role": "minion",
            "synched": "5050",
            "synchronisation: ": "syncbar",
        }
        mock = MagicMock(
            return_value=(
                "Salt:Stack True master/minion UpToDate/partner syncbar None 50 50"
            )
        )
        with patch.dict(drbd.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(drbd.overview(), ret)

    def test_status(self):
        """
        Test if it shows status of the DRBD resources via drbdadm
        """
        ret = [
            {
                "local role": "Primary",
                "local volumes": [{"disk": "UpToDate"}],
                "peer nodes": [
                    {
                        "peer volumes": [
                            {
                                "done": "96.47",
                                "peer-disk": "Inconsistent",
                                "replication": "SyncSource",
                            }
                        ],
                        "peernode name": "opensuse-node2",
                        "role": "Secondary",
                    }
                ],
                "resource name": "single",
            }
        ]

        mock = MagicMock(
            return_value="""
single role:Primary
  disk:UpToDate
  opensuse-node2 role:Secondary
    replication:SyncSource peer-disk:Inconsistent done:96.47
"""
        )

        with patch.dict(drbd.__salt__, {"cmd.run": mock}):
            try:  # python2
                self.assertItemsEqual(drbd.status(), ret)
            except AttributeError:  # python3
                self.assertCountEqual(drbd.status(), ret)

        ret = [
            {
                "local role": "Primary",
                "local volumes": [
                    {"disk": "UpToDate", "volume": "0"},
                    {"disk": "UpToDate", "volume": "1"},
                ],
                "peer nodes": [
                    {
                        "peer volumes": [
                            {"peer-disk": "UpToDate", "volume": "0"},
                            {"peer-disk": "UpToDate", "volume": "1"},
                        ],
                        "peernode name": "node2",
                        "role": "Secondary",
                    },
                    {
                        "peer volumes": [
                            {"peer-disk": "UpToDate", "volume": "0"},
                            {"peer-disk": "UpToDate", "volume": "1"},
                        ],
                        "peernode name": "node3",
                        "role": "Secondary",
                    },
                ],
                "resource name": "test",
            },
            {
                "local role": "Primary",
                "local volumes": [
                    {"disk": "UpToDate", "volume": "0"},
                    {"disk": "UpToDate", "volume": "1"},
                ],
                "peer nodes": [
                    {
                        "peer volumes": [
                            {"peer-disk": "UpToDate", "volume": "0"},
                            {"peer-disk": "UpToDate", "volume": "1"},
                        ],
                        "peernode name": "node2",
                        "role": "Secondary",
                    },
                    {
                        "peer volumes": [
                            {"peer-disk": "UpToDate", "volume": "0"},
                            {"peer-disk": "UpToDate", "volume": "1"},
                        ],
                        "peernode name": "node3",
                        "role": "Secondary",
                    },
                ],
                "resource name": "res",
            },
        ]

        mock = MagicMock(
            return_value="""
res role:Primary
  volume:0 disk:UpToDate
  volume:1 disk:UpToDate
  node2 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate
  node3 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate

test role:Primary
  volume:0 disk:UpToDate
  volume:1 disk:UpToDate
  node2 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate
  node3 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate

"""
        )
        with patch.dict(drbd.__salt__, {"cmd.run": mock}):
            try:  # python2
                self.assertItemsEqual(drbd.status(), ret)
            except AttributeError:  # python3
                self.assertCountEqual(drbd.status(), ret)

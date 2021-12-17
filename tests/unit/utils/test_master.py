import salt.utils.master
from tests.support.mock import patch
from tests.support.unit import TestCase


class MasterPillarUtilTestCase(TestCase):
    """
    TestCase for salt.utils.master.MasterPillarUtil methods
    """

    def test_get_minion_pillar(self):
        """
        test get_minion_pillar when
        target exists
        """
        opts = {"test": False}
        minion = "minion"
        pillar = salt.utils.master.MasterPillarUtil(
            tgt=minion, tgt_type="glob", opts=opts
        )
        grains_data = {minion: {"domain": ""}}
        pillar_data = {minion: {"test_pillar": "foo"}}

        patch_grain = patch(
            "salt.utils.master.MasterPillarUtil._get_minion_grains",
            return_value=grains_data,
        )
        patch_pillar = patch(
            "salt.utils.master.MasterPillarUtil._get_minion_pillar",
            return_value=pillar_data,
        )
        patch_tgt_list = patch(
            "salt.utils.master.MasterPillarUtil._tgt_to_list", return_value=[minion]
        )

        with patch_grain, patch_pillar, patch_tgt_list:
            ret = pillar.get_minion_pillar()
        assert ret[minion] == pillar_data[minion]

    def test_get_minion_pillar_doesnotexist(self):
        """
        test get_minion_pillar when
        target does not exist
        """
        opts = {"test": False}
        minion = "minion"
        pillar = salt.utils.master.MasterPillarUtil(
            tgt="doesnotexist", tgt_type="glob", opts=opts
        )
        grains_data = {minion: {"domain": ""}}
        pillar_data = {minion: {"test_pillar": "foo"}}

        patch_grain = patch(
            "salt.utils.master.MasterPillarUtil._get_minion_grains",
            return_value=grains_data,
        )
        patch_pillar = patch(
            "salt.utils.master.MasterPillarUtil._get_minion_pillar",
            return_value=pillar_data,
        )
        patch_tgt_list = patch(
            "salt.utils.master.MasterPillarUtil._tgt_to_list", return_value=[]
        )

        with patch_grain, patch_pillar, patch_tgt_list:
            ret = pillar.get_minion_pillar()
        assert minion not in ret

    def test_get_minion_pillar_notgt(self):
        """
        test get_minion_pillar when
        passing target None
        """
        opts = {"test": False}
        minion = "minion"
        pillar = salt.utils.master.MasterPillarUtil(
            tgt=None, tgt_type="glob", opts=opts
        )
        grains_data = {minion: {"domain": ""}}
        pillar_data = {minion: {"test_pillar": "foo"}}

        patch_grain = patch(
            "salt.utils.master.MasterPillarUtil._get_minion_grains",
            return_value=grains_data,
        )
        patch_pillar = patch(
            "salt.utils.master.MasterPillarUtil._get_minion_pillar",
            return_value=pillar_data,
        )
        patch_tgt_list = patch(
            "salt.utils.master.MasterPillarUtil._tgt_to_list", return_value=[]
        )

        with patch_grain, patch_pillar, patch_tgt_list:
            ret = pillar.get_minion_pillar()
        assert minion in ret

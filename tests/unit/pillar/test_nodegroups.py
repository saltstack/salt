# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.pillar.nodegroups as nodegroups

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

fake_minion_id = "fake_id"
fake_pillar = {}
fake_nodegroups = {
    "groupA": fake_minion_id,
    "groupB": "another_minion_id",
}
fake_opts = {"cache": "localfs", "nodegroups": fake_nodegroups, "id": fake_minion_id}
fake_pillar_name = "fake_pillar_name"


def side_effect(group_sel, t):
    if group_sel.find(fake_minion_id) != -1:
        return {"minions": [fake_minion_id], "missing": []}
    return {"minions": ["another_minion_id"], "missing": []}


class NodegroupsPillarTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.pillar.nodegroups
    """

    def setup_loader_modules(self):
        return {nodegroups: {"__opts__": fake_opts}}

    def _runner(self, expected_ret, pillar_name=None):
        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(side_effect=side_effect),
        ):
            pillar_name = pillar_name or fake_pillar_name
            actual_ret = nodegroups.ext_pillar(
                fake_minion_id, fake_pillar, pillar_name=pillar_name
            )
            self.assertDictEqual(actual_ret, expected_ret)

    def test_succeeds(self):
        ret = {fake_pillar_name: ["groupA"]}
        self._runner(ret)

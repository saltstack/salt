import pytest

import salt.pillar.nodegroups as nodegroups
from tests.support.mock import MagicMock, patch


@pytest.fixture
def fake_minion_id():
    return "fake_id"


@pytest.fixture
def fake_nodegroups(fake_minion_id):
    return {
        "groupA": fake_minion_id,
        "groupB": "another_minion_id",
    }


@pytest.fixture
def fake_pillar_name():
    return "fake_pillar_name"


@pytest.fixture
def configure_loader_modules(fake_minion_id, fake_nodegroups):
    fake_opts = {
        "cache": "localfs",
        "nodegroups": fake_nodegroups,
        "id": fake_minion_id,
    }
    return {nodegroups: {"__opts__": fake_opts}}


def _runner(expected_ret, fake_minion_id, fake_pillar_name, pillar_name=None):
    def _side_effect(group_sel, t):
        if group_sel.find(fake_minion_id) != -1:
            return {"minions": [fake_minion_id], "missing": []}
        return {"minions": ["another_minion_id"], "missing": []}

    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(side_effect=_side_effect),
    ):
        pillar_name = pillar_name or fake_pillar_name
        actual_ret = nodegroups.ext_pillar(fake_minion_id, {}, pillar_name=pillar_name)
        assert actual_ret == expected_ret


def test_succeeds(fake_pillar_name, fake_minion_id):
    ret = {fake_pillar_name: ["groupA"]}
    _runner(ret, fake_minion_id, fake_pillar_name)

import pytest
import salt.pillar

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_pillar_top_compound_match(salt_master, pillar_state_tree, grains):
    """
    Test that a compound match topfile that refers to a nodegroup via N@ works
    as expected.
    """
    top_file_contents = """
    base:
      'N@mins not L@minion':
        - ng1
      'N@missing_minion':
        - ng2
    """
    ng1_pillar_contents = "pillar_from_nodegroup: True"
    ng2_pillar_contents = "pillar_from_nodegroup_with_ghost: True"
    with pytest.helpers.temp_file(
        "top.sls", top_file_contents, pillar_state_tree
    ), pytest.helpers.temp_file(
        "ng1.sls", ng1_pillar_contents, pillar_state_tree
    ), pytest.helpers.temp_file(
        "ng2.sls", ng2_pillar_contents, pillar_state_tree
    ):
        opts = salt_master.config.copy()
        opts["nodegroups"] = {
            "min": "minion",
            "sub_min": "sub_minion",
            "mins": "N@min or N@sub_min",
            "missing_minion": "L@minion,ghostminion",
        }
        pillar_obj = salt.pillar.Pillar(opts, grains, "minion", "base")
        ret = pillar_obj.compile_pillar()
        assert ret.get("pillar_from_nodegroup_with_ghost") is True
        assert ret.get("pillar_from_nodegroup") is None

        sub_pillar_obj = salt.pillar.Pillar(opts, grains, "sub_minion", "base")
        sub_ret = sub_pillar_obj.compile_pillar()
        assert sub_ret.get("pillar_from_nodegroup_with_ghost") is None
        assert sub_ret.get("pillar_from_nodegroup") is True

"""
Tests for the templates utils
"""

import os

import pytest


def test_issue_60083(
    salt_call_cli,
    tmp_path,
    base_env_state_tree_root_dir,
):
    """
    Validate that we can serialize pillars to json in states.
    Issue #60083
    """
    target_path = tmp_path / "issue-60083-target.txt"
    assert not os.path.exists(str(target_path))
    sls_name = "issue-60083"
    sls_contents = """
    {{ pillar["target-path"] }}:
      file.managed:
        - contents: |
            {{ pillar|json }}
    """
    sls_tempfile = pytest.helpers.temp_file(
        f"{sls_name}.sls", sls_contents, base_env_state_tree_root_dir
    )
    with sls_tempfile:  # , issue_50221_ext_pillar_tempfile:
        ret = salt_call_cli.run(
            "state.apply", sls_name, pillar={"target-path": str(target_path)}
        )
        assert ret.stdout.find("Jinja error") == -1
        assert ret.data
        keys = list(ret.data.keys())
        assert len(keys) == 1
        key = keys[0]
        assert ret.data[key]["changes"]["diff"] == "New file"


def test_issue_62372(
    salt_call_cli,
    tmp_path,
    base_env_state_tree_root_dir,
):
    """
    Validate that we can use the random_* filters
    Issue #62372
    """
    target_path = tmp_path / "issue-62372-target.txt"
    assert not os.path.exists(str(target_path))
    sls_name = "issue-62372"
    sls_contents = """
    {% set my_list = ["one", "two", "three", "four"] -%}
    {{ pillar["target-path"] }}:
      file.managed:
        - contents: |
            {{ my_list | random_sample(2, seed="static") }}
            {{ my_list | random_shuffle(seed="static") }}
    """
    sls_tempfile = pytest.helpers.temp_file(
        f"{sls_name}.sls", sls_contents, base_env_state_tree_root_dir
    )
    with sls_tempfile:
        ret = salt_call_cli.run(
            "state.apply", sls_name, pillar={"target-path": str(target_path)}
        )
        assert ret.stdout.find("Jinja error") == -1
        assert ret.data
        keys = list(ret.data.keys())
        assert len(keys) == 1
        key = keys[0]
        assert ret.data[key]["changes"]["diff"] == "New file"

"""
Pillar include tests
"""

import pytest


@pytest.fixture(scope="module")
def pillar_include_tree(base_env_pillar_tree_root_dir, salt_minion, salt_call_cli):
    top_file = """
    base:
      '{}':
        - include
        - glob-include
        - include-c
        - include-d
    """.format(
        salt_minion.id
    )
    include_pillar_file = """
    include:
      - include-a:
          key: element:a
      - include-b:
          key: element:b
    """
    include_a_pillar_file = """
    a:
      - 'Entry A'
    """
    include_b_pillar_file = """
    b:
      - 'Entry B'
    """
    include_c_pillar_file = """
    c:
      - 'Entry C'
    """
    include_d_pillar_file = """
    include:
      - include-c:
          key: element:d
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    include_tempfile = pytest.helpers.temp_file(
        "include.sls", include_pillar_file, base_env_pillar_tree_root_dir
    )
    include_a_tempfile = pytest.helpers.temp_file(
        "include-a.sls", include_a_pillar_file, base_env_pillar_tree_root_dir
    )
    include_b_tempfile = pytest.helpers.temp_file(
        "include-b.sls", include_b_pillar_file, base_env_pillar_tree_root_dir
    )
    include_c_tempfile = pytest.helpers.temp_file(
        "include-c.sls", include_c_pillar_file, base_env_pillar_tree_root_dir
    )
    include_d_tempfile = pytest.helpers.temp_file(
        "include-d.sls", include_d_pillar_file, base_env_pillar_tree_root_dir
    )
    glob_include_pillar_file = """
    include:
      - 'glob-include-*'
    """
    glob_include_a_pillar_file = """
    glob-a:
      - 'Entry A'
    """
    glob_include_b_pillar_file = """
    glob-b:
      - 'Entry B'
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    glob_include_tempfile = pytest.helpers.temp_file(
        "glob-include.sls", glob_include_pillar_file, base_env_pillar_tree_root_dir
    )
    glob_include_a_tempfile = pytest.helpers.temp_file(
        "glob-include-a.sls", glob_include_a_pillar_file, base_env_pillar_tree_root_dir
    )
    glob_include_b_tempfile = pytest.helpers.temp_file(
        "glob-include-b.sls", glob_include_b_pillar_file, base_env_pillar_tree_root_dir
    )
    try:
        with (
            top_tempfile
        ), (
            include_tempfile
        ), (
            include_a_tempfile
        ), include_b_tempfile, include_c_tempfile, include_d_tempfile:
            with (
                glob_include_tempfile
            ), glob_include_a_tempfile, glob_include_b_tempfile:
                ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
                assert ret.returncode == 0
                assert ret.data is True
                yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True


def test_pillar_include(pillar_include_tree, salt_call_cli):
    """
    Test pillar include
    """
    ret = salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    assert "element" in ret.data
    assert "a" in ret.data["element"]
    assert ret.data["element"]["a"] == {"a": ["Entry A"]}
    assert "b" in ret.data["element"]
    assert ret.data["element"]["b"] == {"b": ["Entry B"]}


def test_pillar_glob_include(pillar_include_tree, salt_call_cli):
    """
    Test pillar include via glob pattern
    """
    ret = salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    assert "glob-a" in ret.data
    assert ret.data["glob-a"] == ["Entry A"]
    assert "glob-b" in ret.data
    assert ret.data["glob-b"] == ["Entry B"]


def test_pillar_include_already_included(pillar_include_tree, salt_call_cli):
    """
    Test pillar include when a pillar file
    has already been included.
    """
    ret = salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    assert "element" in ret.data
    assert "d" in ret.data["element"]
    assert ret.data["element"]["d"] == {"c": ["Entry C"]}

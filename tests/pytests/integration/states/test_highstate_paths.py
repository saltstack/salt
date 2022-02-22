"""
Tests for the highstate state relative and absolute paths
"""
import logging

import pytest

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def pillar_tree(salt_master, salt_minion, salt_call_cli):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = """
    monty: python
    companions:
      three:
        - liz
        - jo
        - sarah jane
    """
    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    basic_tempfile = salt_master.pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    )

    try:
        with top_tempfile, basic_tempfile:
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.exitcode == 0
            assert ret.json is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True


def test_rel_abs_path_ids(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
):
    """
    This tests for any regressions for this issue:
    https://github.com/saltstack/salt/issues/54179
    """
    test_tempdir = salt_master.state_tree.base.paths[0] / "tmp_dir"

    init_sls_name = "tmp_dir/init"
    init_sls_contents = """
    include:
      - .bug
      - tmp_dir/include
    """

    include_sls_name = "tmp_dir/include"
    include_sls_contents = """
    include:
      - tmp_dir/bug
    """

    include_bug_sls_name = "tmp_dir/include_bug"
    include_bug_sls_contents = """
    include_bug:
      test.succeed_without_changes:
        - name: include_bug
        - require:
          - id: bug
    """

    bug_sls_name = "tmp_dir/bug"
    bug_sls_contents = """
    bug:
      test.succeed_without_changes:
        - name: bug
    """

    init_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(init_sls_name), init_sls_contents
    )

    include_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_sls_name), include_sls_contents
    )

    include_bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_bug_sls_name), include_bug_sls_contents
    )

    bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(bug_sls_name), bug_sls_contents
    )

    with init_sls_tempfile, include_sls_tempfile, include_bug_sls_tempfile, bug_sls_tempfile:
        ret = salt_call_cli.run("--local", "state.apply", "tmp_dir")
        assert ret.exitcode == 0


def test_rel_rel_path_ids(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
):
    """
    This tests for any regressions for this issue:
    https://github.com/saltstack/salt/issues/54179
    """
    test_tempdir = salt_master.state_tree.base.paths[0] / "tmp_dir"

    init_sls_name = "tmp_dir/init"
    init_sls_contents = """
    include:
      - .bug
      - .include
    """

    include_sls_name = "tmp_dir/include"
    include_sls_contents = """
    include:
      - tmp_dir/bug
    """

    include_bug_sls_name = "tmp_dir/include_bug"
    include_bug_sls_contents = """
    include_bug:
      test.succeed_without_changes:
        - name: include_bug
        - require:
          - id: bug
    """

    bug_sls_name = "tmp_dir/bug"
    bug_sls_contents = """
    bug:
      test.succeed_without_changes:
        - name: bug
    """

    init_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(init_sls_name), init_sls_contents
    )

    include_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_sls_name), include_sls_contents
    )

    include_bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_bug_sls_name), include_bug_sls_contents
    )

    bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(bug_sls_name), bug_sls_contents
    )

    with init_sls_tempfile, include_sls_tempfile, include_bug_sls_tempfile, bug_sls_tempfile:
        ret = salt_call_cli.run("--local", "state.apply", "tmp_dir")
        assert ret.exitcode == 0


def test_abs_rel_path_ids(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
):
    """
    This tests for any regressions for this issue:
    https://github.com/saltstack/salt/issues/54179
    """
    test_tempdir = salt_master.state_tree.base.paths[0] / "tmp_dir"

    init_sls_name = "tmp_dir/init"
    init_sls_contents = """
    include:
      - tmp_dir/bug
      - .include
    """

    include_sls_name = "tmp_dir/include"
    include_sls_contents = """
    include:
      - tmp_dir/bug
    """

    include_bug_sls_name = "tmp_dir/include_bug"
    include_bug_sls_contents = """
    include_bug:
      test.succeed_without_changes:
        - name: include_bug
        - require:
          - id: bug
    """

    bug_sls_name = "tmp_dir/bug"
    bug_sls_contents = """
    bug:
      test.succeed_without_changes:
        - name: bug
    """

    init_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(init_sls_name), init_sls_contents
    )

    include_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_sls_name), include_sls_contents
    )

    include_bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_bug_sls_name), include_bug_sls_contents
    )

    bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(bug_sls_name), bug_sls_contents
    )

    with init_sls_tempfile, include_sls_tempfile, include_bug_sls_tempfile, bug_sls_tempfile:
        ret = salt_call_cli.run("--local", "state.apply", "tmp_dir")
        assert ret.exitcode == 0


def test_abs_abs_path_ids(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
):
    """
    This tests for any regressions for this issue:
    https://github.com/saltstack/salt/issues/54179
    """
    test_tempdir = salt_master.state_tree.base.paths[0] / "tmp_dir"

    init_sls_name = "tmp_dir/init"
    init_sls_contents = """
    include:
      - tmp_dir/bug
      - tmp_dir/include
    """

    include_sls_name = "tmp_dir/include"
    include_sls_contents = """
    include:
      - tmp_dir/bug
    """

    include_bug_sls_name = "tmp_dir/include_bug"
    include_bug_sls_contents = """
    include_bug:
      test.succeed_without_changes:
        - name: include_bug
        - require:
          - id: bug
    """

    bug_sls_name = "tmp_dir/bug"
    bug_sls_contents = """
    bug:
      test.succeed_without_changes:
        - name: bug
    """

    init_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(init_sls_name), init_sls_contents
    )

    include_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_sls_name), include_sls_contents
    )

    include_bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(include_bug_sls_name), include_bug_sls_contents
    )

    bug_sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(bug_sls_name), bug_sls_contents
    )

    with init_sls_tempfile, include_sls_tempfile, include_bug_sls_tempfile, bug_sls_tempfile:
        ret = salt_call_cli.run("--local", "state.apply", "tmp_dir")
        assert ret.exitcode == 0

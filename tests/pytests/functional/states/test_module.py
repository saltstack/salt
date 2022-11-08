import logging

import pytest

from tests.support.helpers import dedent

log = logging.getLogger(__name__)


@pytest.mark.slow_test
def test_issue_58763(tmp_path, modules, state_tree, caplog):

    venv_dir = tmp_path / "issue-2028-pip-installed"

    sls_contents = dedent(
        """
    run_old:
      module.run:
        - name: test.random_hash
        - size: 10
        - hash_type: md5

    run_new:
      module.run:
        - test.random_hash:
          - size: 10
          - hash_type: md5
    """
    )
    with pytest.helpers.temp_file("issue-58763.sls", sls_contents, state_tree):
        with caplog.at_level(logging.DEBUG):
            ret = modules.state.sls(
                mods="issue-58763",
            )
            assert len(ret.raw) == 2
            for k in ret.raw:
                assert ret.raw[k]["result"] is True
            assert "Detected legacy module.run syntax: run_old" in caplog.messages
            assert "Using new style module.run syntax: run_new" in caplog.messages


@pytest.mark.slow_test
def test_issue_58763_a(tmp_path, modules, state_tree, caplog):

    venv_dir = tmp_path / "issue-2028-pip-installed"

    sls_contents = dedent(
        """
    test.random_hash:
      module.run:
        - size: 10
        - hash_type: md5
    """
    )
    with pytest.helpers.temp_file("issue-58763.sls", sls_contents, state_tree):
        with caplog.at_level(logging.DEBUG):
            ret = modules.state.sls(
                mods="issue-58763",
            )
            assert len(ret.raw) == 1
            for k in ret.raw:
                assert ret.raw[k]["result"] is True
            assert (
                "Detected legacy module.run syntax: test.random_hash" in caplog.messages
            )


@pytest.mark.slow_test
def test_issue_58763_b(tmp_path, modules, state_tree, caplog):

    venv_dir = tmp_path / "issue-2028-pip-installed"

    sls_contents = dedent(
        """
    test.ping:
      module.run
    """
    )
    with pytest.helpers.temp_file("issue-58763.sls", sls_contents, state_tree):
        with caplog.at_level(logging.DEBUG):
            ret = modules.state.sls(
                mods="issue-58763",
            )
            assert len(ret.raw) == 1
            for k in ret.raw:
                assert ret.raw[k]["result"] is True
            assert "Detected legacy module.run syntax: test.ping" in caplog.messages


@pytest.mark.slow_test
def test_issue_62988_a(tmp_path, modules, state_tree, caplog):

    venv_dir = tmp_path / "issue-2028-pip-installed"

    sls_contents = dedent(
        """
    test_foo:
      test.succeed_with_changes

    run_new:
      module.wait:
        - test.random_hash:
          - size: 10
          - hash_type: md5
        - watch:
          - test: test_foo
    """
    )
    with pytest.helpers.temp_file("issue-62988.sls", sls_contents, state_tree):
        with caplog.at_level(logging.DEBUG):
            ret = modules.state.sls(
                mods="issue-62988",
            )
            assert len(ret.raw) == 2
            for k in ret.raw:
                assert ret.raw[k]["result"] is True
            assert "Using new style module.run syntax: run_new" in caplog.messages


@pytest.mark.slow_test
def test_issue_62988_b(tmp_path, modules, state_tree, caplog):

    venv_dir = tmp_path / "issue-2028-pip-installed"

    sls_contents = dedent(
        """
    test_foo:
      test.succeed_with_changes:
        - watch_in:
          - module: run_new

    run_new:
      module.wait:
        - test.random_hash:
          - size: 10
          - hash_type: md5
    """
    )
    with pytest.helpers.temp_file("issue-62988.sls", sls_contents, state_tree):
        with caplog.at_level(logging.DEBUG):
            ret = modules.state.sls(
                mods="issue-62988",
            )
            assert len(ret.raw) == 2
            for k in ret.raw:
                assert ret.raw[k]["result"] is True
            assert "Using new style module.run syntax: run_new" in caplog.messages

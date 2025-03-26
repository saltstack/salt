import logging

import pytest

from tests.support.helpers import dedent

log = logging.getLogger(__name__)


@pytest.mark.core_test
def test_issue_58763(tmp_path, modules, state_tree, caplog):

    sls_contents = dedent(
        """
    run_old:
      module.run:
        - name: test.random_hash
        - size: 10
        - hash_type: sha256

    run_new:
      module.run:
        - test.random_hash:
          - size: 10
          - hash_type: sha256
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


@pytest.mark.core_test
def test_issue_58763_a(tmp_path, modules, state_tree, caplog):

    sls_contents = dedent(
        """
    test.random_hash:
      module.run:
        - size: 10
        - hash_type: sha256
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


@pytest.mark.core_test
def test_issue_58763_b(tmp_path, modules, state_tree, caplog):

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


@pytest.mark.core_test
def test_issue_62988_a(tmp_path, modules, state_tree, caplog):

    sls_contents = dedent(
        """
    test_foo:
      test.succeed_with_changes

    run_new:
      module.wait:
        - test.random_hash:
          - size: 10
          - hash_type: sha256
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


@pytest.mark.core_test
def test_issue_62988_b(tmp_path, modules, state_tree, caplog):

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
          - hash_type: sha256
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


@pytest.mark.core_test
def test_issue_65842_result_false(tmp_path, modules, state_tree):

    sls_contents = dedent(
        """
    failed_state_new_syntax_False_result:
      module.run:
        - test.kwarg:
          - result: False
          - comment: "My Failure"
          - retcode: 0
    """
    )
    with pytest.helpers.temp_file("issue-65842.sls", sls_contents, state_tree):
        ret = modules.state.sls(
            mods="issue-65842",
        )
        assert len(ret.raw) == 1
        for k in ret.raw:
            assert isinstance(ret.raw[k]["result"], bool)
            assert ret.raw[k]["result"] is False
            assert ret.raw[k]["comment"] == "'test.kwarg' failed: My Failure"


@pytest.mark.core_test
def test_issue_65842_should_ok(tmp_path, modules, state_tree):

    sls_contents = dedent(
        """
    success_state_new_syntax:
      module.run:
        - test.kwarg:
          - result: True
          - comment: "This should be success"
          - retcode: 0
    """
    )
    with pytest.helpers.temp_file("issue-65842.sls", sls_contents, state_tree):
        ret = modules.state.sls(
            mods="issue-65842",
        )
        assert len(ret.raw) == 1
        for k in ret.raw:
            assert isinstance(ret.raw[k]["result"], bool)
            assert ret.raw[k]["result"] is True
            assert ret.raw[k]["comment"] == "test.kwarg: This should be success"


@pytest.mark.core_test
def test_issue_65842_retcode_1(tmp_path, modules, state_tree):

    sls_contents = dedent(
        """
    failed_state_new_syntax_1_retcode:
      module.run:
        - test.kwarg:
          - result: True
          - comment: "My Failure"
          - retcode: 1
    """
    )
    with pytest.helpers.temp_file("issue-65842.sls", sls_contents, state_tree):
        ret = modules.state.sls(
            mods="issue-65842",
        )
        assert len(ret.raw) == 1
        for k in ret.raw:
            assert isinstance(ret.raw[k]["result"], bool)
            assert ret.raw[k]["result"] is False
            assert ret.raw[k]["comment"] == "'test.kwarg' failed: My Failure"


@pytest.mark.core_test
def test_issue_65842_test_result_non_boolean_ok(tmp_path, modules, state_tree):

    sls_contents = dedent(
        """
    success_state_new_syntax_wrong_result_type:
      module.run:
        - test.kwarg:
          - result: "OK"
          - comment: "This should be success"
          - retcode: 0
    """
    )
    with pytest.helpers.temp_file("issue-65842.sls", sls_contents, state_tree):
        ret = modules.state.sls(
            mods="issue-65842",
        )
        assert len(ret.raw) == 1
        for k in ret.raw:
            assert isinstance(ret.raw[k]["result"], bool)
            assert ret.raw[k]["result"] is True
            assert ret.raw[k]["comment"] == "test.kwarg: This should be success"


@pytest.mark.core_test
def test_issue_65842_test_result_inner_dict(tmp_path, modules, state_tree):

    sls_contents = dedent(
        """
    failure_state_new_syntax_inner_dict:
      module.run:
        - test.kwarg:
          - comment: "This should be a failure"
          - myValue:
              result: False
    """
    )
    with pytest.helpers.temp_file("issue-65842.sls", sls_contents, state_tree):
        ret = modules.state.sls(
            mods="issue-65842",
        )
        assert len(ret.raw) == 1
        for k in ret.raw:
            assert isinstance(ret.raw[k]["result"], bool)
            assert ret.raw[k]["result"] is False
            assert (
                ret.raw[k]["comment"] == "'test.kwarg' failed: This should be a failure"
            )

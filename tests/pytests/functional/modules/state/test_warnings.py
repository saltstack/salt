import pytest


def test_warnings(state, state_tree):
    sls_contents = """
    throw-warning:
        test.deprecation_warning_raised
    """
    with pytest.helpers.temp_file("throw-warning.sls", sls_contents, state_tree):
        ret = state.sls("throw-warning")
        for state_return in ret:
            assert state_return.result is True
            assert state_return.warnings
            expected_warnings = 2
            for warning in state_return.warnings:
                if not expected_warnings:
                    break
                if "This is a test deprecation warning by version" in warning:
                    expected_warnings -= 1
                if (
                    "This is a test deprecation warning by date very far into the future"
                    in warning
                ):
                    expected_warnings -= 1
            assert (
                expected_warnings == 0
            ), "Did not find one or more of the expected deprecation warnings"


def test_no_warnings(state, state_tree):
    sls_contents = """
    test.succeed_with_changes:
      - name: foo
    """
    with pytest.helpers.temp_file("no-throw-warning.sls", sls_contents, state_tree):
        ret = state.sls("no-throw-warning")
        for state_return in ret:
            assert state_return.result is True
            assert not state_return.warnings

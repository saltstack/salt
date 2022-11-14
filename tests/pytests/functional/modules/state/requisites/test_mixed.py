import pytest

from . import normalize_ret

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_requisites_mixed_require_prereq_use_1(state, state_tree):
    """
    Call sls file containing several requisites.
    """
    expected_simple_result = {
        "cmd_|-A_|-echo A_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo A" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo B" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo C" run',
            "result": True,
            "changes": True,
        },
    }
    sls_contents = """
    # Simple mix between prereq and require
    # C (1) <--+ <------+
    #          |        |
    # B (2) -p-+ <-+    |
    #              |    |
    # A (3) --r----+ -p-+

    A:
      cmd.run:
        - name: echo A
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    B:
      cmd.run:
        - name: echo B
        - require_in:
          - cmd: A

    # infinite recursion.....?
    C:
      cmd.run:
        - name: echo C
        # will test B and be applied only if B changes,
        # and then will run before B
        - prereq:
            - cmd: B
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_simple_result


@pytest.mark.skip("Undetected infinite loops prevents this test from running...")
def test_requisites_mixed_require_prereq_use_2(state, state_tree):
    sls_contents = """
    # Complex require/require_in/prereq/preqreq_in graph
    #
    #
    # D (1) <--------r-----+
    #                      |
    # C (2) <--+ <-----p-------+
    #          |           |   |
    # B (3) -p-+ <-+ <-+ --+   |
    #              |   |       |
    # E (4) ---r---|---+ <-+   |
    #              |       |   |
    # A (5) --r----+ ---r--+ --+
    #

    A:
      cmd.run:
        - name: echo A fifth
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    B:
      cmd.run:
        - name: echo B third
        - require_in:
          - cmd: A

    # infinite recursion.....
    C:
      cmd.run:
        - name: echo C second
        # will test B and be applied only if B changes,
        # and then will run before B
        - prereq:
            - cmd: B

    D:
      cmd.run:
        - name: echo D first
        # issue #8773
        - require_in:
            cmd: B

    E:
      cmd.run:
        - name: echo E fourth
        - require:
          - cmd: B
        - require_in:
          - cmd: A
    """
    expected_result = {
        "cmd_|-A_|-echo A fifth_|-run": {
            "__run_num__": 4,
            "comment": 'Command "echo A fifth" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B third_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo B third" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo C second" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-D_|-echo D first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo D first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-E_|-echo E fourth_|-run": {
            "__run_num__": 3,
            "comment": 'Command "echo E fourth" run',
            "result": True,
            "changes": True,
        },
    }
    # undetected infinite loops prevents this test from running...
    # TODO: this is actually failing badly
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


@pytest.mark.skip("Undetected infinite loops prevents this test from running...")
def test_requisites_mixed_require_prereq_use_3(state, state_tree):
    # test Traceback recursion prereq+require #8785
    sls_contents = """
    # issue #8785
    # B <--+ ----r-+
    #      |       |
    # A -p-+ <-----+-- ERROR: cannot respect both require and prereq

    A:
      cmd.run:
        - name: echo A
        - require_in:
          - cmd: B

    # infinite recursion.....?
    B:
      cmd.run:
        - name: echo B
        # will test A and be applied only if A changes,
        # and then will run before A
        - prereq:
            - cmd: A
    """
    expected_result = ['A recursive requisite was found, SLS "requisite" ID "B" ID "A"']
    # TODO: this is actually failing badly
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert isinstance(ret, list)  # Error
        assert ret == expected_result


@pytest.mark.skip("Undetected infinite loops prevents this test from running...")
def test_requisites_mixed_require_prereq_use_4(state, state_tree):
    # test Infinite recursion prereq+require #8785 v2
    sls_contents = """
    # issue #8785 RuntimeError: maximum recursion depth exceeded
    # C <--+ <------+ -r-+
    #      |        |    |
    # B -p-+ <-+    | <--+-- ERROR: cannot respect both require and prereq
    #          |    |
    # A --r----+ -p-+

    A:
      cmd.run:
        - name: echo A
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    B:
      cmd.run:
        - name: echo B
        - require_in:
          - cmd: A
          # this should raise the error
          - cmd: C

    # infinite recursion.....?
    C:
      cmd.run:
        - name: echo C
        # will test B and be applied only if B changes,
        # and then will run before B
        - prereq:
            - cmd: B
    """
    expected_result = ['A recursive requisite was found, SLS "requisite" ID "B" ID "A"']
    # TODO: this is actually failing badly
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert isinstance(ret, list)  # Error
        assert ret == expected_result


@pytest.mark.skip("Undetected infinite loops prevents this test from running...")
def test_requisites_mixed_require_prereq_use_5(state, state_tree):
    # test Infinite recursion prereq+require #8785 v3
    sls_contents = """
    # issue #8785
    #
    # Here it's more complex. Order SHOULD be ok.
    # When B changes something the require is verified.
    # What should happen if B does not chane anything?
    # It should also run because of the require.
    # Currently we have:
    # RuntimeError: maximum recursion depth exceeded

    # B (1) <---+ <--+
    #           |    |
    # A (2) -r--+ -p-+

    A:
      cmd.run:
        - name: echo A
        # is running in test mode before B
        # B gets executed first if this states modify something
        # key of bug
        - prereq_in:
          - cmd: B
    B:
      cmd.run:
        - name: echo B
        # B should run before A
        - require_in:
          - cmd: A
    """
    expected_result = ['A recursive requisite was found, SLS "requisite" ID "B" ID "A"']
    # TODO: this is actually failing badly, and expected result is maybe not a recursion
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert isinstance(ret, list)  # Error
        assert ret == expected_result


def test_issue_46762_prereqs_on_a_state_with_unfulfilled_requirements(
    state, state_tree
):
    """
    This tests the case where state C requires state A, which fails.
    State C is a pre-required state for State B.
    Since state A fails, state C will not run because the requisite failed,
    therefore state B will not run because state C failed to run.

    See https://github.com/saltstack/salt/issues/46762 for
    more information.
    """
    sls_contents = """
    a: test.fail_without_changes

    b:
      test.nop:
        - prereq:
          - c

    c:
      test.nop:
      - require:
        - a
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")

    state_id = "test_|-a_|-a_|-fail_without_changes"
    assert state_id in ret
    assert ret[state_id].result is False
    assert ret[state_id].comment == "Failure!"

    state_id = "test_|-b_|-b_|-nop"
    assert state_id in ret
    assert ret[state_id].result is False
    assert ret[state_id].comment == "One or more requisite failed: requisite.c"

    state_id = "test_|-c_|-c_|-nop"
    assert state_id in ret
    assert ret[state_id].result is False
    assert ret[state_id].comment == "One or more requisite failed: requisite.a"


@pytest.mark.skip_on_darwin(reason="Test is broken on macosx")
@pytest.mark.slow_test
def test_issue_30161_unless_and_onlyif_together(state, state_tree, tmp_path):
    """
    test cmd.run using multiple unless options where the first cmd in the
    list will pass, but the second will fail. This tests the fix for issue
    #35384. (The fix is in PR #35545.)
    """
    test_txt_path = tmp_path / "test.txt"
    sls_contents = """
    unless_false_onlyif_true:
      file.managed:
        - name: {test_txt_path}
        - unless: {test_false}
        - onlyif: {test_true}

    unless_true_onlyif_false:
      file.managed:
        - name: {test_txt_path}
        - unless: {test_true}
        - onlyif: {test_false}

    unless_true_onlyif_true:
      file.managed:
        - name: {test_txt_path}
        - unless: {test_true}
        - onlyif: {test_true}

    unless_false_onlyif_false:
      file.managed:
        - name: {test_txt_path}
        - contents: test
        - unless: {test_false}
        - onlyif: {test_false}
    """.format(
        test_true=pytest.helpers.shell_test_true(),
        test_false=pytest.helpers.shell_test_false(),
        test_txt_path=test_txt_path,
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        for state_entry in ret:
            assert state_entry.result is True
        # We must assert against the comment here to make sure the comment reads that the
        # command "echo "hello"" was run. This ensures that we made it to the last unless
        # command in the state. If the comment reads "unless condition is true", or similar,
        # then the unless state run bailed out after the first unless command succeeded,
        # which is the bug we're regression testing for.
    _expected = {
        "file_|-unless_false_onlyif_false_|-{}_|-managed".format(test_txt_path): {
            "comment": "onlyif condition is false\nunless condition is false",
            "name": "{}".format(test_txt_path),
            "skip_watch": True,
            "changes": {},
            "result": True,
        },
        "file_|-unless_false_onlyif_true_|-{}_|-managed".format(test_txt_path): {
            "comment": "Empty file",
            "name": str(test_txt_path),
            "start_time": "18:10:20.341753",
            "result": True,
            "changes": {"new": "file {} created".format(test_txt_path)},
        },
        "file_|-unless_true_onlyif_false_|-{}_|-managed".format(test_txt_path): {
            "comment": "onlyif condition is false\nunless condition is true",
            "name": str(test_txt_path),
            "start_time": "18:10:22.936446",
            "skip_watch": True,
            "changes": {},
            "result": True,
        },
        "file_|-unless_true_onlyif_true_|-{}_|-managed".format(test_txt_path): {
            "comment": "onlyif condition is true\nunless condition is true",
            "name": str(test_txt_path),
            "skip_watch": True,
            "changes": {},
            "result": True,
        },
    }
    for slsid in _expected:
        assert ret[slsid].comment == _expected[slsid]["comment"]

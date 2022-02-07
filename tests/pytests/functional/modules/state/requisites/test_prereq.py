import pytest

from . import normalize_ret

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_requisites_full_sls_prereq(state, state_tree):
    """
    Test the sls special command in requisites
    """
    full_sls_contents = """
    B:
      cmd.run:
        - name: echo B
    C:
      cmd.run:
        - name: echo C
    """
    sls_contents = """
    include:
      - fullsls
    A:
      cmd.run:
        - name: echo A
        - prereq:
          - sls: fullsls
    """
    expected_result = {
        "cmd_|-A_|-echo A_|-run": {
            "__run_num__": 0,
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
            "__run_num__": 2,
            "comment": 'Command "echo C" run',
            "result": True,
            "changes": True,
        },
    }
    with pytest.helpers.temp_file(
        "requisite.sls", sls_contents, state_tree
    ), pytest.helpers.temp_file("fullsls.sls", full_sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_1(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - cmd: C
    C:
      cmd.run:
        - name: echo C second

    # will fail with "The following requisites were not found"
    I:
      cmd.run:
        - name: echo I
        - prereq:
          - cmd: Z
    J:
      cmd.run:
        - name: echo J
        - prereq:
          - foobar: A
    """
    expected_result = {
        "cmd_|-A_|-echo A third_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo A third" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo B first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo C second" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-I_|-echo I_|-run": {
            "__run_num__": 3,
            "comment": "The following requisites were not found:\n"
            + "                   prereq:\n"
            + "                       cmd: Z\n",
            "result": False,
            "changes": False,
        },
        "cmd_|-J_|-echo J_|-run": {
            "__run_num__": 4,
            "comment": "The following requisites were not found:\n"
            + "                   prereq:\n"
            + "                       foobar: A\n",
            "result": False,
            "changes": False,
        },
    }
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_2(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    # same test, but not using lists in yaml syntax
    sls_contents = """
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
           cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
            cmd: C
    C:
      cmd.run:
        - name: echo C second
    """
    errmsg = (
        "The prereq statement in state 'B' in SLS 'requisite' needs to be formed as a"
        " list"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_requisites_prereq_simple_ordering_and_errors_3(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - C
    C:
      cmd.run:
        - name: echo C second

    # will fail with "The following requisites were not found"
    I:
      cmd.run:
        - name: echo I
        - prereq:
          - Z
        """
    expected_result = {
        "cmd_|-A_|-echo A third_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo A third" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo B first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo C second" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-I_|-echo I_|-run": {
            "__run_num__": 3,
            "comment": "The following requisites were not found:\n"
            + "                   prereq:\n"
            + "                       id: Z\n",
            "result": False,
            "changes": False,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_4(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # Theory:
    #
    # C <--+ <--+ <-+ <-+
    #      |    |   |   |
    # A ---+    |   |   |
    #           |   |   |
    # B --------+   |   |
    #               |   |
    # D-------------+   |
    #                   |
    # E-----------------+

    # runs after C
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

    # runs before D and B
    C:
      cmd.run:
        - name: echo C
        # will test D and be applied only if D changes,
        # and then will run before D. Same for B
        - prereq:
          - cmd: B
          - cmd: D

    D:
      cmd.run:
        - name: echo D

    E:
      cmd.run:
        - name: echo E
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    """
    expected_result = {
        "cmd_|-A_|-echo A_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo A" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B_|-run": {
            "__run_num__": 2,
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
        "cmd_|-D_|-echo D_|-run": {
            "__run_num__": 3,
            "comment": 'Command "echo D" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-E_|-echo E_|-run": {
            "__run_num__": 4,
            "comment": 'Command "echo E" run',
            "result": True,
            "changes": True,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_5(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # A --+
    #     |
    # B <-+ ----+
    #           |
    # C <-------+

    # runs before A and/or B
    A:
      cmd.run:
        - name: echo A first
        # is running in test mode before B/C
        - prereq:
          - cmd: B
          - cmd: C

    # always has to run
    B:
      cmd.run:
        - name: echo B second

    # never has to run
    C:
      cmd.wait:
        - name: echo C third
    """
    expected_result = {
        "cmd_|-A_|-echo A first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo A first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo B second" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C third_|-wait": {
            "__run_num__": 2,
            "comment": "",
            "result": True,
            "changes": False,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_6(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # issue #8211
    #             expected rank
    # B --+             1
    #     |
    # C <-+ ----+       2/3
    #           |
    # D ---+    |       3/2
    #      |    |
    # A <--+ <--+       4
    #
    #             resulting rank
    # D --+
    #     |
    # A <-+ <==+
    #          |
    # B --+    +--> unrespected A prereq_in C (FAILURE)
    #     |    |
    # C <-+ ===+

    # runs after C
    A:
      cmd.run:
        - name: echo A fourth
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - cmd: C

    C:
      cmd.run:
        - name: echo C second
        # replacing A prereq_in C by theses lines
        # changes nothing actually
        #- prereq:
        #  - cmd: A

    # Removing D, A gets executed after C
    # as described in (A prereq_in C)
    # runs before A
    D:
      cmd.run:
        - name: echo D third
        # will test A and be applied only if A changes,
        # and then will run before A
        - prereq:
          - cmd: A
    """
    expected_result = {
        "cmd_|-A_|-echo A fourth_|-run": {
            "__run_num__": 3,
            "comment": 'Command "echo A fourth" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-B_|-echo B first_|-run": {
            "__run_num__": 0,
            "comment": 'Command "echo B first" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-C_|-echo C second_|-run": {
            "__run_num__": 1,
            "comment": 'Command "echo C second" run',
            "result": True,
            "changes": True,
        },
        "cmd_|-D_|-echo D third_|-run": {
            "__run_num__": 2,
            "comment": 'Command "echo D third" run',
            "result": True,
            "changes": True,
        },
    }

    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        result = normalize_ret(ret.raw)
        assert result == expected_result


def test_requisites_prereq_simple_ordering_and_errors_7(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    # will fail with 'Cannot extend ID Z (...) not part of the high state.'
    # and not "The following requisites were not found" like in yaml list syntax
    I:
      cmd.run:
        - name: echo I
        - prereq:
          - cmd: Z
    """
    errmsg = (
        "The following requisites were not found:\n"
        "                   prereq:\n"
        "                       cmd: Z\n"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret["cmd_|-I_|-echo I_|-run"].comment == errmsg


def test_requisites_prereq_simple_ordering_and_errors_8(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    A:
      cmd.run:
        - name: echo A

    B:
      cmd.run:
        - name: echo B
        - prereq:
          - foobar: A
    """
    errmsg = (
        "The following requisites were not found:\n"
        "                   prereq:\n"
        "                       foobar: A\n"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret["cmd_|-B_|-echo B_|-run"].comment == errmsg


def test_requisites_prereq_simple_ordering_and_errors_9(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    A:
      cmd.run:
        - name: echo A

    B:
      cmd.run:
        - name: echo B
        - prereq:
          - foobar: C
    """
    errmsg = (
        "The following requisites were not found:\n"
        "                   prereq:\n"
        "                       foobar: C\n"
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret["cmd_|-B_|-echo B_|-run"].comment == errmsg


@pytest.mark.skip("issue #8210 : prereq recursion undetected")
def test_requisites_prereq_simple_ordering_and_errors_10(state, state_tree):
    """
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    """
    sls_contents = """
    A:
      cmd.run:
        - name: echo A
        - prereq_in:
          - cmd: B
    B:
      cmd.run:
        - name: echo B
        - prereq_in:
          - cmd: A
    """
    errmsg = (
        'A recursive requisite was found, SLS "requisites.prereq_recursion_error" ID'
        ' "B" ID "A"'
    )
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_infinite_recursion_sls_prereq(state, state_tree):
    sls_contents = """
    include:
      - requisite2
    A:
      test.succeed_without_changes:
        - name: A
        - prereq:
          - sls: requisite2
    """
    sls_2_contents = """
    B:
      test.succeed_without_changes:
        - name: B
    """
    with pytest.helpers.temp_file(
        "requisite.sls", sls_contents, state_tree
    ), pytest.helpers.temp_file("requisite2.sls", sls_2_contents, state_tree):
        ret = state.sls("requisite")
        for state_return in ret:
            assert state_return.result is True

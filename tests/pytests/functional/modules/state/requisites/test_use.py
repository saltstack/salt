import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.core_test,
]


def test_requisites_use(state, state_tree):
    """
    Call sls file containing several use_in and use.

    """
    # TODO issue #8235 & #8774 some examples are still commented in the test file
    sls_contents = """
    # None of theses states should run
    A:
      cmd.run:
        - name: echo "A"
        - onlyif: 'false'

    # issue #8235
    #B:
    #  cmd.run:
    #    - name: echo "B"
    #  # here used without "-"
    #    - use:
    #        cmd: A

    C:
      cmd.run:
        - name: echo "C"
        - use:
            - cmd: A

    D:
      cmd.run:
        - name: echo "D"
        - onlyif: 'false'
        - use_in:
            - cmd: E

    E:
      cmd.run:
        - name: echo "E"

    # issue 8235
    #F:
    #  cmd.run:
    #    - name: echo "F"
    #    - onlyif: return 0
    #    - use_in:
    #        cmd: G
    #
    #G:
    #  cmd.run:
    #    - name: echo "G"

    # issue xxxx
    #H:
    #  cmd.run:
    #    - name: echo "H"
    #    - use:
    #        - cmd: C
    #I:
    #  cmd.run:
    #    - name: echo "I"
    #    - use:
    #        - cmd: E
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        for state_return in ret:
            assert state_return.comment == "onlyif condition is false"


@pytest.mark.skip(
    "issue #8802 : use recursions undetected. See comment in test for more info"
)
def test_requisites_use_recursion_1(state, state_tree):
    """
    Call sls file containing several use_in and use.
    """
    # TODO: issue #8802 : use recursions undetected
    # issue is closed as use does not actually inherit requisites
    # if chain-use is added after #8774 resolution theses tests would maybe become useful
    sls_contents = """
    A:
      cmd.run:
        - name: echo "A"
        - onlyif: return False
        - use:
            cmd: B

    B:
      cmd.run:
        - name: echo "B"
        - unless: return False
        - use:
            cmd: A
    """
    errmsg = 'A recursive requisite was found, SLS "requisite" ID "B" ID "A"'
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


@pytest.mark.skip(
    "issue #8802 : use recursions undetected. See comment in test for more info"
)
def test_requisites_use_recursion_2(state, state_tree):
    """
    Call sls file containing several use_in and use.
    """
    # TODO: issue #8802 : use recursions undetected
    # issue is closed as use does not actually inherit requisites
    # if chain-use is added after #8774 resolution theses tests would maybe become useful
    sls_contents = """
    #
    # A <--+ ---u--+
    #      |       |
    # B -u-+ <-+   |
    #          |   |
    # C -u-----+ <-+

    A:
      cmd.run:
        - name: echo "A"
        - use:
            cmd: C

    B:
      cmd.run:
        - name: echo "B"
        - use:
            cmd: C

    C:
      cmd.run:
        - name: echo "B"
        - use:
            cmd: A
    """
    errmsg = 'A recursive requisite was found, SLS "requisite" ID "C" ID "A"'
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


@pytest.mark.skip(
    "issue #8802 : use recursions undetected. See comment in test for more info"
)
def test_requisites_use_recursion_3(state, state_tree):
    """
    Call sls file containing several use_in and use.
    """
    # TODO: issue #8802 : use recursions undetected
    # issue is closed as use does not actually inherit requisites
    # if chain-use is added after #8774 resolution theses tests would maybe become useful
    sls_contents = """
    A:
      cmd.run:
        - name: echo "A"
        - use:
            cmd: A
    """
    errmsg = 'A recursive requisite was found, SLS "requisite" ID "A" ID "A"'
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert ret.failed
        assert ret.errors == [errmsg]


def test_requisites_use_no_state_module(state, state_tree):
    """
    Call sls file containing several use_in and use.
    """
    sls_contents = """
    # None of theses states should run
    A:
      cmd.run:
        - name: echo "A"
        - onlyif: 'false'

    # issue #8235
    #B:
    #  cmd.run:
    #    - name: echo "B"
    #  # here used without "-"
    #    - use:
    #        cmd: A

    C:
      cmd.run:
        - name: echo "C"
        - use:
            - A

    D:
      cmd.run:
        - name: echo "D"
        - onlyif: 'false'
        - use_in:
            - E

    E:
      cmd.run:
        - name: echo "E"

    # issue 8235
    #F:
    #  cmd.run:
    #    - name: echo "F"
    #    - onlyif: return 0
    #    - use_in:
    #        cmd: G
    #
    #G:
    #  cmd.run:
    #    - name: echo "G"

    # issue xxxx
    #H:
    #  cmd.run:
    #    - name: echo "H"
    #    - use:
    #        - cmd: C
    #I:
    #  cmd.run:
    #    - name: echo "I"
    #    - use:
    #        - cmd: E
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        for state_return in ret:
            assert state_return.comment == "onlyif condition is false"

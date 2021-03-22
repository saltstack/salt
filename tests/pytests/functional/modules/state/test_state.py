import logging
import os
import textwrap
import threading
import time

import pytest
import salt.loader
import salt.utils.atomicfile
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_show_highstate(state, state_testfile_dest_path):
    """
    state.show_highstate
    """
    high = state.show_highstate()
    assert isinstance(high, dict)
    assert str(state_testfile_dest_path) in high
    assert high[str(state_testfile_dest_path)]["__env__"] == "base"


def test_show_lowstate(state):
    """
    state.show_lowstate
    """
    low = state.show_lowstate()
    assert isinstance(low, list)
    for entry in low:
        assert isinstance(entry, dict)


def test_show_states(state):
    """
    state.show_states
    """
    states = state.show_states()
    assert isinstance(states, list)
    for entry in states:
        assert isinstance(entry, str)
    assert states == ["core"]


def test_show_states_missing_sls(state, state_tree):
    """
    Test state.show_states with a sls file
    defined in a top file is missing
    """
    top_sls_contents = """
    base:
      '*':
        - core
        - does-not-exist
    """
    with pytest.helpers.temp_file("top.sls", top_sls_contents, state_tree):
        states = state.show_states()
        assert isinstance(states, list)
        assert states == ["No matching sls found for 'does-not-exist' in env 'base'"]


def test_catch_recurse(state, state_tree):
    """
    state.show_sls used to catch a recursive ref
    """
    sls_contents = """
    mysql:
      service:
        - running
        - require:
          - file: /etc/mysql/my.cnf

    /etc/mysql/my.cnf:
      file:
        - managed
        - source: salt://master.cnf
        - require:
          - service: mysql
    """
    with pytest.helpers.temp_file("recurse-fail.sls", sls_contents, state_tree):
        ret = state.sls("recurse-fail")
        assert isinstance(ret, list)  # This is an error
        assert len(ret) == 1  # It only has one entry
        assert "recursive" in ret[0]


RECURSE_SLS_ONE = """
snmpd:
  pkg:
    - installed
  service:
    - running
    - require:
      - pkg: snmpd
    - watch:
      - file: /etc/snmp/snmpd.conf

/etc/snmp/snmpd.conf:
  file:
    - managed
    - source: salt://snmpd/snmpd.conf.jinja
    - template: jinja
    - user: root
    - group: root
    - mode: "0600"
    - require:
      - pkg: snmpd
"""
RECURSE_SLS_TWO = """
nagios-nrpe-server:
  pkg:
    - installed
  service:
    - running
    - watch:
      - file: /etc/nagios/nrpe.cfg

/etc/nagios/nrpe.cfg:
  file:
    - managed
    - source: salt://baseserver/nrpe.cfg
    - require:
      - pkg: nagios-nrpe-server
"""


@pytest.mark.parametrize(
    "sls_contents, expected_in_output",
    [(RECURSE_SLS_ONE, "snmpd"), (RECURSE_SLS_TWO, "/etc/nagios/nrpe.cfg")],
    ids=("recurse-scenario-1", "recurse-scenario-2"),
)
def test_no_recurse(state, state_tree, sls_contents, expected_in_output):
    """
    verify that a sls structure is NOT a recursive ref
    """
    with pytest.helpers.temp_file("recurse-ok.sls", sls_contents, state_tree):
        ret = state.show_sls("recurse-ok")
        assert expected_in_output in ret


def test_running_dictionary_consistency(state):
    """
    Test the structure of the running dictionary so we don't change it
    without deprecating/documenting the change
    """
    running_dict_fields = {
        "__id__",
        "__run_num__",
        "__sls__",
        "changes",
        "comment",
        "duration",
        "name",
        "result",
        "start_time",
    }

    sls = state.single("test.succeed_without_changes", name="gndn")
    for ret in sls.values():
        ret_values_set = set(ret.keys())
        assert running_dict_fields.issubset(ret_values_set)


def test_running_dictionary_key_sls(state, state_tree):
    """
    Ensure the __sls__ key is either null or a string
    """
    sls1 = state.single("test.succeed_with_changes", name="gndn")
    sls_contents = """
    gndn:
      test.succeed_with_changes
    """
    with pytest.helpers.temp_file("gndn.sls", sls_contents, state_tree):
        sls2 = state.sls(mods="gndn")

    for ret in sls1.values():
        assert "__sls__" in ret
        assert ret["__sls__"] is None

    for ret in sls2.values():
        assert "__sls__" in ret
        assert isinstance(ret["__sls__"], str)


@pytest.fixture
def requested_sls_key(minion_opts, state_tree):
    if not salt.utils.platform.is_windows():
        sls_contents = """
        count_root_dir_contents:
          cmd.run:
            - name: 'ls -a / | wc -l'
        """
        sls_key = "cmd_|-count_root_dir_contents_|-ls -a / | wc -l_|-run"
    else:
        sls_contents = r"""
        count_root_dir_contents:
          cmd.run:
            - name: 'Get-ChildItem C:\ | Measure-Object | %{$_.Count}'
            - shell: powershell
        """
        sls_key = r"cmd_|-count_root_dir_contents_|-Get-ChildItem C:\ | Measure-Object | %{$_.Count}_|-run"
    try:
        with pytest.helpers.temp_file(
            "requested.sls", sls_contents, state_tree
        ) as sls_path:
            yield sls_key
    finally:
        cache_file = os.path.join(minion_opts["cachedir"], "req_state.p")
        if os.path.exists(cache_file):
            os.remove(cache_file)


def test_request(state, requested_sls_key):
    """
    verify sending a state request to the minion(s)
    """
    ret = state.request("requested")
    assert ret[requested_sls_key]["result"] is None


def test_check_request(state, requested_sls_key):
    """
    verify checking a state request sent to the minion(s)
    """
    ret = state.request("requested")
    assert ret[requested_sls_key]["result"] is None

    ret = state.check_request()
    assert ret["default"]["test_run"][requested_sls_key]["result"] is None


def test_clear_request(state, requested_sls_key):
    """
    verify clearing a state request sent to the minion(s)
    """
    ret = state.request("requested")
    assert ret[requested_sls_key]["result"] is None

    ret = state.clear_request()
    assert ret is True


def test_run_request_succeeded(state, requested_sls_key):
    """
    verify running a state request sent to the minion(s)
    """
    ret = state.request("requested")
    assert ret[requested_sls_key]["result"] is None

    ret = state.run_request()
    assert ret[requested_sls_key]["result"] is True


def test_run_request_failed_no_request_staged(state, requested_sls_key):
    """
    verify not running a state request sent to the minion(s)
    """
    ret = state.request("requested")
    assert ret[requested_sls_key]["result"] is None

    ret = state.clear_request()
    assert ret is True

    ret = state.run_request()
    assert ret == {}


def test_issue_1876_syntax_error(state, state_tree, tmp_path):
    """
    verify that we catch the following syntax error::

        /tmp/salttest/issue-1876:

          file:
            - managed
            - source: salt://testfile

          file.append:
            - text: foo

    """
    testfile = tmp_path / "issue-1876.txt"
    sls_contents = """
    {}:
      file:
        - managed
        - source: salt://testfile

      file.append:
        - text: foo
    """.format(
        testfile
    )
    with pytest.helpers.temp_file("issue-1876.sls", sls_contents, state_tree):

        ret = state.sls("issue-1876")
        assert isinstance(ret, list)  # An error
        errmsg = "ID '{}' in SLS 'issue-1876' contains multiple state declarations of the same type".format(
            testfile
        )
        assert ret == [errmsg]


def test_issue_1879_too_simple_contains_check(state, state_tree, tmp_path):
    testfile = tmp_path / "issue-1979.txt"
    init_sls_contents = """
    {}:
      file:
        - touch
    """.format(
        testfile
    )
    step1_sls_contents = """
    {}:
      file.append:
        - text: |
            # set variable identifying the chroot you work in (used in the prompt below)
            if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
                debian_chroot=$(cat /etc/debian_chroot)
            fi

    """.format(
        testfile
    )
    step2_sls_contents = """
    {}:
      file.append:
        - text: |
            # enable bash completion in interactive shells
            if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
                . /etc/bash_completion
            fi

    """.format(
        testfile
    )

    expected = textwrap.dedent(
        """\
        # set variable identifying the chroot you work in (used in the prompt below)
        if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
            debian_chroot=$(cat /etc/debian_chroot)
        fi
        # enable bash completion in interactive shells
        if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
            . /etc/bash_completion
        fi
        """
    )

    issue_1879_dir = state_tree / "issue-1879"
    with pytest.helpers.temp_file(
        "init.sls", init_sls_contents, issue_1879_dir
    ), pytest.helpers.temp_file(
        "step-1.sls", step1_sls_contents, issue_1879_dir
    ), pytest.helpers.temp_file(
        "step-2.sls", step2_sls_contents, issue_1879_dir
    ):
        # Create the file
        ret = state.sls("issue-1879")
        staterun = next(iter(ret.values()))
        assert staterun["result"] is True

        # The first append
        ret = state.sls("issue-1879.step-1")
        staterun = next(iter(ret.values()))
        assert staterun["result"] is True

        # The second append
        ret = state.sls("issue-1879.step-2")
        staterun = next(iter(ret.values()))
        assert staterun["result"] is True

        # Does it match?
        contents = testfile.read_text()
        assert contents == expected

        # Make sure we don't re-append existing text
        ret = state.sls("issue-1879.step-1")
        staterun = next(iter(ret.values()))
        assert staterun["result"] is True

        ret = state.sls("issue-1879.step-2")
        staterun = next(iter(ret.values()))
        assert staterun["result"] is True

        # Does it match?
        contents = testfile.read_text()
        assert contents == expected


def test_include(state, state_tree, tmp_path):
    testfile_path = tmp_path / "testfile"
    testfile_path.write_text("foo")
    include_test_path = tmp_path / "include-test.txt"
    to_include_test_path = tmp_path / "to-include-test.txt"
    exclude_test_path = tmp_path / "exclude-test.txt"
    to_include_sls_contents = """
    {}:
      file.managed:
        - source: salt://testfile
    """.format(
        to_include_test_path
    )
    include_sls_contents = """
    include:
      - to-include-test

    {}:
      file.managed:
        - source: salt://testfile
    """.format(
        include_test_path
    )
    with pytest.helpers.temp_file(
        "testfile", "foo", state_tree
    ), pytest.helpers.temp_file(
        "to-include-test.sls", to_include_sls_contents, state_tree
    ), pytest.helpers.temp_file(
        "include-test.sls", include_sls_contents, state_tree
    ):
        ret = state.sls("include-test")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()

    assert include_test_path.exists()
    assert to_include_test_path.exists()
    assert exclude_test_path.exists() is False


def test_exclude(state, state_tree, tmp_path):
    testfile_path = tmp_path / "testfile"
    testfile_path.write_text("foo")
    include_test_path = tmp_path / "include-test.txt"
    to_include_test_path = tmp_path / "to-include-test.txt"
    exclude_test_path = tmp_path / "exclude-test.txt"
    to_include_sls_contents = """
    {}:
      file.managed:
        - source: salt://testfile
    """.format(
        to_include_test_path
    )
    include_sls_contents = """
    include:
      - to-include-test

    {}:
      file.managed:
        - source: salt://testfile
    """.format(
        include_test_path
    )
    exclude_sls_contents = """
    exclude:
      - to-include-test

    include:
      - include-test

    {}:
      file.managed:
        - source: salt://testfile
    """.format(
        exclude_test_path
    )
    with pytest.helpers.temp_file(
        "testfile", "foo", state_tree
    ), pytest.helpers.temp_file(
        "to-include-test.sls", to_include_sls_contents, state_tree
    ), pytest.helpers.temp_file(
        "include-test.sls", include_sls_contents, state_tree
    ), pytest.helpers.temp_file(
        "exclude-test.sls", exclude_sls_contents, state_tree
    ):
        ret = state.sls("exclude-test")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()

    assert include_test_path.exists()
    assert exclude_test_path.exists()
    assert to_include_test_path.exists() is False


def test_issue_2068_template_str(state, state_tree):
    template_str_no_dot_sls_contents = """
    required_state:
      test:
        - succeed_without_changes

    requiring_state:
      test:
        - succeed_without_changes
        - require:
          - test: required_state
    """
    template_str_sls_contents = """
    required_state: test.succeed_without_changes

    requiring_state:
      test.succeed_without_changes:
        - require:
          - test: required_state
    """
    with pytest.helpers.temp_file(
        "issue-2068-no-dot.sls", template_str_no_dot_sls_contents, state_tree
    ) as template_str_no_dot_path, pytest.helpers.temp_file(
        "issue-2068.sls", template_str_sls_contents, state_tree
    ) as template_str_path:
        # If running this state with state.sls works, so should using state.template_str
        ret = state.sls("issue-2068-no-dot")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()

        template_str_no_dot_contents = template_str_no_dot_path.read_text()
        ret = state.template_str(template_str_no_dot_contents)
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()

        # Now using state.template
        ret = state.template(str(template_str_no_dot_path))
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()

        # Now the problematic #2068 including dot's
        ret = state.sls("issue-2068")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()

        template_str_contents = template_str_path.read_text()
        ret = state.template_str(template_str_contents)
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()

        # Now using state.template
        ret = state.template(str(template_str_path))
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()


@pytest.mark.parametrize("item", ("include", "exclude", "extends"))
def test_template_str_invalid_items(state, item):
    TEMPLATE = textwrap.dedent(
        """\
        {}:
          - existing-state

        /tmp/test-template-invalid-items:
          file:
            - managed
            - source: salt://testfile
        """.format(
            item
        )
    )

    ret = state.template_str(TEMPLATE.format(item))
    assert isinstance(ret, list)  # An error
    assert ret != []  # Not an empty error
    errmsg = (
        "The '{}' declaration found on '<template-str>' is invalid when "
        "rendering single templates".format(item)
    )
    assert ret == [errmsg]


@pytest.mark.skip_on_windows(
    reason=(
        "Functional testing this on windows raises unicode errors. "
        "Tested in tests/pytests/integration/modules/state/test_state.py"
    )
)
def test_pydsl(state, state_tree, tmp_path):
    """
    Test the basics of the pydsl
    """
    testfile = tmp_path / "testfile"
    sls_contents = """
    #!pydsl

    state("{}").file("touch")
    """.format(
        testfile
    )
    with pytest.helpers.temp_file("pydsl.sls", sls_contents, state_tree):
        ret = state.sls("pydsl")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()
        assert testfile.exists()


def test_issues_7905_and_8174_sls_syntax_error(state, state_tree):
    """
    Call sls file with yaml syntax error.

    Ensure theses errors are detected and presented to the user without
    stack traces.
    """
    badlist_1_sls_contents = """
    # Missing " " between "-" and "foo" or "name"
    A:
      cmd.run:
        -name: echo foo
        -foo:
          - bar
    """
    badlist_2_sls_contents = """
    # C should fail with bad list error message
    B:
      # ok
      file.exist:
        - name: /foo/bar/foobar
    # ok
    /foo/bar/foobar:
      file.exist

    # nok
    C:
      /foo/bar/foobar:
        file.exist
    """
    with pytest.helpers.temp_file(
        "badlist1.sls", badlist_1_sls_contents, state_tree
    ), pytest.helpers.temp_file("badlist2.sls", badlist_2_sls_contents, state_tree):
        ret = state.sls("badlist1")
        assert isinstance(ret, list)
        assert ret == ["State 'A' in SLS 'badlist1' is not formed as a list"]

        ret = state.sls("badlist2")
        assert isinstance(ret, list)
        assert ret == ["State 'C' in SLS 'badlist2' is not formed as a list"]


@pytest.mark.slow_test
def test_retry_option(state, state_tree):
    """
    test the retry option on a simple state with defaults
    ensure comment is as expected
    ensure state duration is greater than configured the passed (interval * attempts)
    """
    sls_contents = """
    file_test:
      file.exists:
        - name: /path/to/a/non-existent/file.txt
        - retry:
            until: True
            attempts: 3
            interval: 1
            splay: 0
    """
    expected_comment = (
        'Attempt 1: Returned a result of "False", with the following '
        'comment: "Specified path /path/to/a/non-existent/file.txt does not exist"'
    )
    with pytest.helpers.temp_file("retry.sls", sls_contents, state_tree):
        ret = state.sls("retry")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_false_return()
        ret.assert_in_state_comment(expected_comment)
        for entry in ret.get_within_state_return("duration"):
            assert entry >= 3


@pytest.mark.flaky(max_runs=4, rerun_filter=lambda *a: salt.utils.platform.is_windows())
def test_retry_option_success(state, state_tree, tmp_path):
    """
    test a state with the retry option that should return True immedietly (i.e. no retries)
    """
    testfile = tmp_path / "testfile"
    testfile.touch()
    sls_contents = """
    file_test:
      file.exists:
        - name: {}
        - retry:
            until: True
            attempts: 5
            interval: 2
            splay: 0
    """.format(
        testfile
    )
    with pytest.helpers.temp_file("retry.sls", sls_contents, state_tree):
        ret = state.sls("retry")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()
        for entry in ret.get_within_state_return("duration"):
            assert entry < 4
        # It should not take 2 attempts
        ret.assert_not_in_state_comment("Attempt 2")


@pytest.mark.slow_test
def test_retry_option_eventual_success(state, state_tree, tmp_path):
    """
    test a state with the retry option that should return True, eventually
    """
    testfile1 = tmp_path / "testfile-1"
    testfile2 = tmp_path / "testfile-2"

    def create_testfile(testfile1, testfile2):
        while True:
            if testfile1.exists():
                break
        time.sleep(2)
        testfile2.touch()

    thread = threading.Thread(target=create_testfile, args=(testfile1, testfile2))
    sls_contents = """
    file_test_a:
      file.managed:
        - name: {}
        - content: 'a'

    file_test:
      file.exists:
        - name: {}
        - retry:
            until: True
            attempts: 5
            interval: 2
            splay: 0
        - require:
          - file_test_a
    """.format(
        testfile1, testfile2
    )
    with pytest.helpers.temp_file("retry.sls", sls_contents, state_tree):
        thread.start()
        ret = state.sls("retry")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()
        for entry in ret.get_within_state_return("duration"):
            assert entry > 4  # It needs more than one iteration
        # It should not take 5 attempts
        ret.assert_not_in_state_comment("Attempt 5")


@pytest.mark.slow_test
def test_state_non_base_environment(state, state_tree_prod, tmp_path):
    """
    test state.sls with saltenv using a nonbase environment
    with a salt source
    """
    testfile = tmp_path / "testfile"
    sls_contents = """
    {}:
      file.managed:
        - content: foo
    """.format(
        testfile
    )
    with pytest.helpers.temp_file("non-base-env.sls", sls_contents, state_tree_prod):
        ret = state.sls("non-base-env", saltenv="prod")
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()
        assert testfile.exists()


@pytest.mark.skip_on_windows(
    reason="Skipped until parallel states can be fixed on Windows"
)
def test_parallel_state_with_long_tag(state, state_tree):
    """
    This tests the case where the state being executed has a long ID dec or
    name and states are being run in parallel. The filenames used for the
    parallel state cache were previously based on the tag for each chunk,
    and longer ID decs or name params can cause the cache file to be longer
    than the operating system's max file name length. To counter this we
    instead generate a SHA1 hash of the chunk's tag to use as the cache
    filename. This test will ensure that long tags don't cause caching
    failures.

    See https://github.com/saltstack/salt/issues/49738 for more info.
    """
    short_command = "helloworld"
    long_command = short_command * 25
    sls_contents = """
    test_cmd_short:
      cmd.run:
        - name: {}
        - parallel: True

    test_cmd_long:
      cmd.run:
        - name: {}
        - parallel: True
    """.format(
        short_command, long_command
    )
    with pytest.helpers.temp_file("issue-49738.sls", sls_contents, state_tree):
        ret = state.sls(
            "issue-49738",
            __pub_jid="1",  # Because these run in parallel we need a fake JID
        )

    comments = sorted([x["comment"] for x in ret.values()])
    expected = sorted(
        ['Command "{}" run'.format(x) for x in (short_command, long_command)]
    )
    assert comments == expected, "{} != {}".format(comments, expected)


@pytest.mark.skip_on_darwin(reason="Test is broken on macosx")
@pytest.mark.skip_on_windows(
    reason=(
        "Functional testing this on windows raises unicode errors. "
        "Tested in tests/pytests/integration/modules/state/test_state.py"
    )
)
def test_state_sls_unicode_characters(state, state_tree):
    """
    test state.sls when state file contains non-ascii characters
    """
    sls_contents = """
    echo1:
      cmd.run:
        - name: "echo 'This is Æ test!'"
    """
    with pytest.helpers.temp_file("issue-46672.sls", sls_contents, state_tree):
        ret = state.sls("issue-46672")
        expected = "cmd_|-echo1_|-echo 'This is Æ test!'_|-run"
        assert expected in ret


def test_state_sls_integer_name(state, state_tree):
    """
    This tests the case where the state file is named
    only with integers
    """
    sls_contents = """
    always-passes:
      test.succeed_without_changes
    """
    state_id = "test_|-always-passes_|-always-passes_|-succeed_without_changes"
    with pytest.helpers.temp_file("12345.sls", sls_contents, state_tree):
        ret = state.sls("12345")
        assert state_id in ret
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()
        ret.assert_in_state_comment("Success!")

        ret = state.sls(mods=12345)
        assert state_id in ret
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()
        ret.assert_in_state_comment("Success!")


def test_state_sls_lazyloader_allows_recursion(state, state_tree):
    """
    This tests that referencing dunders like __salt__ work
    context: https://github.com/saltstack/salt/pull/51499
    """
    sls_contents = """
    {% if 'nonexistent_module.function' in salt %}
    {% do salt.log.warning("Module is available") %}
    {% endif %}
    always-passes:
      test.succeed_without_changes:
        - name: foo
    """
    state_id = "test_|-always-passes_|-foo_|-succeed_without_changes"
    with pytest.helpers.temp_file("issue-51499.sls", sls_contents, state_tree):
        ret = state.sls("issue-51499")
        assert state_id in ret
        ret = pytest.helpers.state_return(ret)
        ret.assert_state_true_return()
        ret.assert_in_state_comment("Success!")

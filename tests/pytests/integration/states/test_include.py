"""
Integration tests for the jinja includes in states
"""

import logging

import pytest

log = logging.getLogger(__name__)


@pytest.mark.slow_test
def test_issue_64111(salt_master, salt_minion, salt_call_cli):
    # This needs to be an integration test. A functional test does not trigger
    # the issue fixed.

    macros_jinja = """
    {% macro a_jinja_macro(arg) -%}
    {{ arg }}
    {%- endmacro %}
    """

    init_sls = """
    include:
      - common.file1
    """

    file1_sls = """
    {% from 'common/macros.jinja' import a_jinja_macro with context %}

    a state id:
      cmd.run:
        - name: echo {{ a_jinja_macro("hello world") }}
    """
    tf = salt_master.state_tree.base.temp_file

    with tf("common/macros.jinja", macros_jinja):
        with tf("common/init.sls", init_sls):
            with tf("common/file1.sls", file1_sls):
                ret = salt_call_cli.run("state.apply", "common")
                assert ret.returncode == 0


@pytest.mark.slow_test
def test_issue_65080(salt_master, salt_minion, salt_call_cli):
    """
    Test scenario when a state includes another state that only includes a third state
    """

    only_include_sls = """
include:
  - includetest.another-include
    """

    another_include_sls = """
/tmp/from-test-file.txt:
  file.managed:
    - contents: Hello from test-file.sls
    """

    init_sls = """
include:
  - includetest.only-include

/tmp/from-init.txt:
  file.managed:
    - contents: Hello from init.sls
    - require:
      - sls: includetest.only-include
    """

    tf = salt_master.state_tree.base.temp_file

    with tf("includetest/init.sls", init_sls):
        with tf("includetest/another-include.sls", another_include_sls):
            with tf("includetest/only-include.sls", only_include_sls):
                ret = salt_call_cli.run("state.apply", "includetest")
                assert ret.returncode == 0

                ret = salt_call_cli.run("state.show_low_sls", "includetest")
                assert "__sls_included_from__" in ret.data[0]
                assert (
                    "includetest.only-include" in ret.data[0]["__sls_included_from__"]
                )


@pytest.mark.slow_test
def test_issue_65080_multiple_includes(salt_master, salt_minion, salt_call_cli):
    """
    Test scenario when a state includes another state that only includes a third state
    """

    only_include_one_sls = """
include:
  - includetest.include-one
    """

    only_include_two_sls = """
include:
  - includetest.include-two
    """

    include_one_sls = """
/tmp/from-test-file1.txt:
  file.managed:
    - contents: Hello from test-file.sls
    """

    include_two_sls = """
/tmp/from-test-file2.txt:
  file.managed:
    - contents: Hello from test-file.sls
    """

    init_sls = """
include:
  - includetest.only-include-one
  - includetest.only-include-two

/tmp/from-init.txt:
  file.managed:
    - contents: Hello from init.sls
    - require:
      - sls: includetest.only-include-one
      - sls: includetest.only-include-two
    """

    tf = salt_master.state_tree.base.temp_file

    with tf("includetest/init.sls", init_sls):
        with tf("includetest/include-one.sls", include_one_sls), tf(
            "includetest/include-two.sls", include_two_sls
        ):
            with tf("includetest/only-include-one.sls", only_include_one_sls), tf(
                "includetest/only-include-two.sls", only_include_two_sls
            ):
                ret = salt_call_cli.run("state.apply", "includetest")
                assert ret.returncode == 0

                ret = salt_call_cli.run("state.show_low_sls", "includetest")
                assert "__sls_included_from__" in ret.data[0]
                assert (
                    "includetest.only-include-one"
                    in ret.data[0]["__sls_included_from__"]
                )

                assert "__sls_included_from__" in ret.data[1]
                assert (
                    "includetest.only-include-two"
                    in ret.data[1]["__sls_included_from__"]
                )


@pytest.mark.slow_test
def test_issue_65080_saltenv(salt_master, salt_minion, salt_call_cli):
    """
    Test scenario when a state includes another state that only includes a third state
    """

    only_include_sls = """
include:
  - includetest.another-include
    """

    another_include_sls = """
/tmp/from-test-file.txt:
  file.managed:
    - contents: Hello from test-file.sls
    """

    init_sls = """
include:
  - prod: includetest.only-include

/tmp/from-init.txt:
  file.managed:
    - contents: Hello from init.sls
    - require:
      - sls: includetest.only-include
    """

    base_tf = salt_master.state_tree.base.temp_file
    prod_tf = salt_master.state_tree.prod.temp_file

    with base_tf("includetest/init.sls", init_sls):
        with prod_tf("includetest/only-include.sls", only_include_sls):
            with prod_tf("includetest/another-include.sls", another_include_sls):
                ret = salt_call_cli.run("state.apply", "includetest")
                assert ret.returncode == 0

                ret = salt_call_cli.run("state.show_low_sls", "includetest")
                assert "__sls_included_from__" in ret.data[0]
                assert (
                    "includetest.only-include" in ret.data[0]["__sls_included_from__"]
                )

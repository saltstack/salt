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

"""
validate the use of shell processing for cmd.run on the salt command line
and in templating
"""

import os
import textwrap

import pytest

import salt.utils.files
import salt.utils.platform

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_on_freebsd,
]


@pytest.fixture
def test_cmd():
    if salt.utils.platform.is_windows():
        return 'where cmd whoami xcopy | find /c /v "" && echo saltines && echo duh > NUL 2>&1'
    else:
        return (
            "printf '%s\\n' first second third | wc -l ; "
            "export SALTY_VARIABLE='saltines' && echo $SALTY_VARIABLE ; "
            "echo duh &> /dev/null"
        )


@pytest.fixture
def ret_disabled():
    if salt.utils.platform.is_windows():
        return 'ERROR: Value for default option cannot be empty.\r\nType "WHERE /?" for usage.'
    else:
        return (
            "first\nsecond\nthird\n|\nwc\n-l\n;\nexport\nSALTY_VARIABLE=saltines"
            "\n&&\necho\n$SALTY_VARIABLE\n;\necho\nduh\n&>\n/dev/null"
        )


@pytest.fixture
def ret_enabled(cmd):
    if salt.utils.platform.is_windows():
        cmd_text = 'where cmd whoami xcopy | find /c /v ""'
        num_lines = cmd.run(cmd_text, python_shell=True)
        return f"{num_lines}{os.linesep}saltines"
    else:
        return f"3{os.linesep}saltines"


@pytest.fixture(scope="module")
def cmd(modules):
    return modules.cmd


@pytest.fixture(scope="module")
def state(modules):
    return modules.state


def test_run_default(cmd, test_cmd, ret_disabled):
    """
    ensure that python_shell defaults to False for cmd.run
    """
    ret = cmd.run(test_cmd)
    assert ret == ret_disabled


def test_shell_default(cmd, test_cmd, ret_enabled):
    """
    ensure that python_shell defaults to True for cmd.shell
    """
    ret = cmd.shell(test_cmd)
    assert ret == ret_enabled


def test_run_disabled(cmd, test_cmd, ret_disabled):
    """
    test python_shell disabled output for cmd.run
    """
    ret = cmd.run(test_cmd, python_shell=False)
    assert ret.strip() == ret_disabled


def test_shell_disabled(cmd, test_cmd, ret_disabled):
    """
    test python_shell disabled output for cmd.shell
    """
    ret = cmd.shell(test_cmd, python_shell=False)
    assert ret.strip() == ret_disabled


def test_run_enabled(cmd, test_cmd, ret_enabled):
    """
    test python_shell enabled output for cmd.run
    """
    ret = cmd.run(test_cmd, python_shell=True)
    assert ret.strip() == ret_enabled


def test_shell_enabled(cmd, test_cmd, ret_enabled):
    """
    test python_shell enabled output for cmd.shell
    """
    ret = cmd.shell(test_cmd, python_shell=True)
    assert ret.strip() == ret_enabled


@pytest.mark.slow_test
def test_template_run_default(state, state_tree, test_cmd, ret_disabled):
    """
    test python_shell disabled output for templates using run
    (python_shell=False is the default beginning with the 2017.7.0 release).
    """
    state_name = "template_run_default"
    state_file_name = state_name + ".sls"
    if salt.utils.platform.is_windows():
        test_cmd = f"'{test_cmd}'"
    else:
        test_cmd = f'"{test_cmd}"'
    state_file_contents = textwrap.dedent(
        f"""
        {{% set run_default= salt['cmd.run']({test_cmd}) %}}

        run_default:
          test.configurable_test_state:
            - name: '{{{{ run_default }}}}'
        """
    )

    # the result of running self.cmd not in a shell
    ret_disabled = ret_disabled.replace(os.linesep, " ")
    ret_key = f"test_|-run_default_|-{ret_disabled}_|-configurable_test_state"
    with pytest.helpers.temp_file(state_file_name, state_file_contents, state_tree):
        ret = state.sls(state_name)
        assert ret[ret_key]["name"] == ret_disabled


@pytest.mark.slow_test
def test_template_shell_default(state, state_tree, test_cmd, ret_enabled):
    """
    test python_shell enabled output for templates using shell
    (python_shell=True is the default beginning with the 2017.7.0 release).
    """
    state_name = "template_shell_enabled"
    state_file_name = state_name + ".sls"
    if salt.utils.platform.is_windows():
        test_cmd = f"'{test_cmd}'"
    else:
        test_cmd = f'"{test_cmd}"'
    state_file_contents = textwrap.dedent(
        f"""
        {{% set shell_default= salt['cmd.shell']({test_cmd}) %}}

        shell_default:
          test.configurable_test_state:
            - name: '{{{{ shell_default }}}}'
        """
    )

    # the result of running self.cmd not in a shell
    ret_enabled = ret_enabled.replace(os.linesep, " ")
    ret_key = f"test_|-shell_default_|-{ret_enabled}_|-configurable_test_state"
    with pytest.helpers.temp_file(state_file_name, state_file_contents, state_tree):
        ret = state.sls(state_name)
        assert ret[ret_key]["name"] == ret_enabled


@pytest.mark.slow_test
def test_template_run_disabled(state, state_tree, test_cmd, ret_disabled):
    """
    test python_shell disabled output for templates using run
    """
    state_name = "template_run_disabled"
    state_file_name = state_name + ".sls"
    if salt.utils.platform.is_windows():
        test_cmd = f"'{test_cmd}'"
    else:
        test_cmd = f'"{test_cmd}"'
    state_file_contents = textwrap.dedent(
        f"""
        {{% set run_disabled = salt['cmd.run']({test_cmd}, python_shell=False) %}}

        run_disabled:
          test.configurable_test_state:
            - name: '{{{{ run_disabled }}}}'
        """
    )

    # the result of running self.cmd not in a shell
    ret_disabled = ret_disabled.replace(os.linesep, " ")
    ret_key = f"test_|-run_disabled_|-{ret_disabled}_|-configurable_test_state"
    with pytest.helpers.temp_file(state_file_name, state_file_contents, state_tree):
        ret = state.sls(state_name)
        assert ret[ret_key]["name"] == ret_disabled


@pytest.mark.slow_test
def test_template_shell_disabled(state, state_tree, test_cmd, ret_disabled):
    """
    test python_shell disabled output for templates using shell
    """
    state_name = "template_shell_disabled"
    state_file_name = state_name + ".sls"
    if salt.utils.platform.is_windows():
        test_cmd = f"'{test_cmd}'"
    else:
        test_cmd = f'"{test_cmd}"'
    state_file_contents = textwrap.dedent(
        f"""
        {{% set shell_disabled = salt['cmd.shell']({test_cmd}, python_shell=False) %}}

        shell_disabled:
          test.configurable_test_state:
            - name: '{{{{ shell_disabled }}}}'
        """
    )

    # the result of running self.cmd not in a shell
    ret_disabled = ret_disabled.replace(os.linesep, " ")
    ret_key = f"test_|-shell_disabled_|-{ret_disabled}_|-configurable_test_state"
    with pytest.helpers.temp_file(state_file_name, state_file_contents, state_tree):
        ret = state.sls(state_name)
        assert ret[ret_key]["name"] == ret_disabled


@pytest.mark.slow_test
def test_template_run_enabled(state, state_tree, test_cmd, ret_enabled):
    """
    Test cmd.run works correctly when using a template.
    """
    state_name = "template_run_enabled"
    state_file_name = state_name + ".sls"
    if salt.utils.platform.is_windows():
        test_cmd = f"'{test_cmd}'"
    else:
        test_cmd = f'"{test_cmd}"'
    state_file_contents = textwrap.dedent(
        f"""
        {{% set run_enabled = salt['cmd.run']({test_cmd}, python_shell=True).strip() %}}

        run_enabled:
          test.configurable_test_state:
            - name: '{{{{ run_enabled }}}}'
        """
    )

    ret_enabled = ret_enabled.replace(os.linesep, " ")
    ret_key = f"test_|-run_enabled_|-{ret_enabled}_|-configurable_test_state"

    with pytest.helpers.temp_file(state_file_name, state_file_contents, state_tree):
        ret = state.sls(state_name)
        assert ret[ret_key]["name"] == ret_enabled


@pytest.mark.slow_test
def test_template_shell_enabled(state, state_tree, test_cmd, ret_enabled):
    """
    Test cmd.shell works correctly when using a template.

    Note: This test used to test that python_shell defaulted to True for templates
    in releases before 2017.7.0. The cmd.run --> cmd.shell aliasing was removed in
    2017.7.0. Templates should now be using cmd.shell.
    """
    state_name = "template_shell_enabled"
    state_file_name = state_name + ".sls"
    if salt.utils.platform.is_windows():
        test_cmd = f"'{test_cmd}'"
    else:
        test_cmd = f'"{test_cmd}"'
    state_file_contents = textwrap.dedent(
        f"""
        {{% set shell_enabled = salt['cmd.shell']({test_cmd}, python_shell=True).strip() %}}

        shell_enabled:
          test.configurable_test_state:
            - name: '{{{{ shell_enabled }}}}'
        """
    )

    ret_enabled = ret_enabled.replace(os.linesep, " ")
    ret_key = f"test_|-shell_enabled_|-{ret_enabled}_|-configurable_test_state"

    with pytest.helpers.temp_file(state_file_name, state_file_contents, state_tree):
        ret = state.sls(state_name)
        assert ret[ret_key]["name"] == ret_enabled

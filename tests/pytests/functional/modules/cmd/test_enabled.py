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
]


@pytest.fixture
def test_cmd():
    if salt.utils.platform.is_windows():
        # I couldn't find a command on Windows that acts the same way as the
        # printf statement in Linux
        # Powershell
        # cmd = (
        #     '("{0}`n{1}`n{2}" -f "first", "second", "third" | Measure-Object -Line).Lines; '
        #     "$env:SALTY_VARIABLE='saltines'; echo $env:SALTY_VARIABLE; "
        #     "echo duh *> $null"
        # )
        return '(echo(first & echo(second & echo(third) | find /v /c "" && echo saltines && echo duh > NUL 2>&1'
    else:
        return (
            "printf '%s\\n' first second third | wc -l ; "
            "export SALTY_VARIABLE='saltines' && echo $SALTY_VARIABLE ; "
            "echo duh &> /dev/null"
        )


@pytest.fixture
def ret_disabled():
    if salt.utils.platform.is_windows():
        return "Access denied - \\"
    else:
        return (
            "first\nsecond\nthird\n|\nwc\n-l\n;\nexport\nSALTY_VARIABLE=saltines"
            "\n&&\necho\n$SALTY_VARIABLE\n;\necho\nduh\n&>\n/dev/null"
        )


@pytest.fixture
def ret_enabled():
    return f"3{os.linesep}saltines"


@pytest.fixture(scope="module")
def cmd(modules):
    return modules.cmd


@pytest.fixture(scope="module")
def state(modules):
    return modules.state


# @pytest.mark.skip_on_windows(reason="Skip on Windows OS")
@pytest.mark.skip_on_freebsd
def test_shell_default_disabled(cmd, test_cmd, ret_disabled):
    """
    ensure that python_shell defaults to False for cmd.run
    """
    ret = cmd.run(test_cmd)
    assert ret == ret_disabled


# @pytest.mark.skip_on_windows(reason="Skip on Windows OS")
def test_shell_disabled(cmd, test_cmd, ret_disabled):
    """
    test shell disabled output for cmd.run
    """
    ret = cmd.run(test_cmd, python_shell=False)
    assert ret.strip() == ret_disabled


# @pytest.mark.skip_on_windows(reason="Skip on Windows OS")
def test_shell_enabled(cmd, test_cmd, ret_enabled):
    """
    test shell disabled output for cmd.run
    """
    enabled_ret = f"3{os.linesep}saltines"
    ret = cmd.run(test_cmd, python_shell=True)
    assert ret.strip() == ret_enabled


# @pytest.mark.skip_on_windows(reason="Skip on Windows OS")
def test_template_shell(state, state_tree, test_cmd, ret_enabled):
    """
    Test cmd.shell works correctly when using a template.

    Note: This test used to test that python_shell defaulted to True for templates
    in releases before 2017.7.0. The cmd.run --> cmd.shell aliasing was removed in
    2017.7.0. Templates should now be using cmd.shell.
    """
    state_name = "template_shell_enabled"
    state_file_name = state_name + ".sls"
    state_file_contents = textwrap.dedent(
        f"""
        {{% set shell_enabled = salt['cmd.shell']("{test_cmd}", python_shell=True).strip() %}}

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


# @pytest.mark.skip_on_windows(reason="Skip on Windows OS")
@pytest.mark.slow_test
def test_template_default_disabled(state, state_tree, test_cmd, ret_disabled):
    """
    test shell disabled output for templates (python_shell=False is the default
    beginning with the 2017.7.0 release).
    """
    state_name = "template_shell_disabled"
    state_file_name = state_name + ".sls"
    state_file_contents = textwrap.dedent(
        f"""
        {{% set shell_disabled = salt['cmd.run']("{test_cmd}") %}}

        shell_enabled:
          test.configurable_test_state:
            - name: '{{{{ shell_disabled }}}}'
        """
    )

    # the result of running self.cmd not in a shell
    ret_disabled = ret_disabled.replace(os.linesep, " ")
    ret_key = f"test_|-shell_enabled_|-{ret_disabled}_|-configurable_test_state"
    with pytest.helpers.temp_file(state_file_name, state_file_contents, state_tree):
        ret = state.sls(state_name)
        assert ret[ret_key]["name"] == ret_disabled

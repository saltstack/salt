"""
salt-ssh testing
"""

import pathlib
import shutil

import pytest

import salt.utils.files
import salt.utils.yaml
from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(autouse=True)
def thin_dir(salt_ssh_cli):
    try:
        yield
    finally:
        ret = salt_ssh_cli.run("config.get", "thin_dir")
        assert ret.returncode == 0
        thin_dir_path = ret.data
        shutil.rmtree(thin_dir_path, ignore_errors=True)


@pytest.fixture(scope="module")
def invalid_json_exe_mod(salt_run_cli, base_env_state_tree_root_dir):
    module_contents = r"""
import os
import sys


def __virtual__():
    return "whoops"


def test():
    data = '{\n  "local": {\n    "whoops": "hrhrhr"\n  }\n}'
    ctr = 0
    for line in data.splitlines():
        sys.stdout.write(line)
        if ctr == 3:
            print("Warning: Chaos is not a letter")
        ctr += 1
    sys.stdout.flush()
    os._exit(0)
"""
    module_dir = base_env_state_tree_root_dir / "_modules"
    module_tempfile = pytest.helpers.temp_file("whoops.py", module_contents, module_dir)
    try:
        with module_tempfile:
            ret = salt_run_cli.run("saltutil.sync_modules")
            assert ret.returncode == 0
            assert "modules.whoops" in ret.data
            yield
    finally:
        ret = salt_run_cli.run("saltutil.sync_modules")
        assert ret.returncode == 0


@pytest.fixture(scope="module")
def invalid_return_exe_mod(salt_run_cli, base_env_state_tree_root_dir):
    module_contents = r"""
import json
import os
import sys


def __virtual__():
    return "whoopsiedoodle"


def test(wrapped=True):
    data = "Chaos is a ladder though"
    if wrapped:
        data = {"local": {"no_return_key_present": data}}
    else:
        data = {"no_local_key_present": data}

    print(json.dumps(data))
    sys.stdout.flush()
    os._exit(0)
"""
    module_dir = base_env_state_tree_root_dir / "_modules"
    module_tempfile = pytest.helpers.temp_file(
        "whoopsiedoodle.py", module_contents, module_dir
    )
    try:
        with module_tempfile:
            ret = salt_run_cli.run("saltutil.sync_modules")
            assert ret.returncode == 0
            assert "modules.whoopsiedoodle" in ret.data
            yield
    finally:
        ret = salt_run_cli.run("saltutil.sync_modules")
        assert ret.returncode == 0


@pytest.fixture(scope="module")
def remote_exception_wrap_mod(salt_master):
    module_contents = r"""
def __virtual__():
    return "check_exception"


def failure():
    # This should raise an exception
    ret = __salt__["disk.usage"]("c")
    return f"Probably got garbage: {ret}"
"""
    module_dir = pathlib.Path(salt_master.config["extension_modules"]) / "wrapper"
    module_tempfile = pytest.helpers.temp_file(
        "check_exception.py", module_contents, module_dir
    )
    with module_tempfile:
        yield


@pytest.fixture(scope="module")
def remote_parsing_failure_wrap_mod(salt_master, invalid_json_exe_mod):
    module_contents = r"""
def __virtual__():
    return "check_parsing"


def failure(mod):
    # This should raise an exception
    ret = __salt__[f"{mod}.test"]()
    return f"Probably got garbage: {ret}"
"""
    module_dir = pathlib.Path(salt_master.config["extension_modules"]) / "wrapper"
    module_tempfile = pytest.helpers.temp_file(
        "check_parsing.py", module_contents, module_dir
    )
    with module_tempfile:
        yield


def test_ping(salt_ssh_cli):
    """
    Test a simple ping
    """
    ret = salt_ssh_cli.run("test.ping")
    assert ret.returncode == 0
    assert ret.data is True


def test_thin_dir(salt_ssh_cli):
    """
    test to make sure thin_dir is created
    and salt-call file is included
    """
    ret = salt_ssh_cli.run("config.get", "thin_dir")
    assert ret.returncode == 0
    thin_dir = pathlib.Path(ret.data)
    assert thin_dir.is_dir()
    assert thin_dir.joinpath("salt-call").exists()
    assert thin_dir.joinpath("running_data").exists()


def test_relenv_dir(salt_ssh_cli):
    """
    test to make sure thin_dir is created
    and salt-call file is included
    """
    ret = salt_ssh_cli.run("--relenv", "config.get", "thin_dir")
    assert ret.returncode == 0
    thin_dir = pathlib.Path(ret.data)
    assert thin_dir.is_dir()
    assert thin_dir
    assert thin_dir.joinpath("salt-call").exists()


def test_relenv_ping(salt_ssh_cli):
    """
    Test a simple ping
    """
    ret = salt_ssh_cli.run("--relenv", "test.ping")
    assert ret.returncode == 0
    assert ret.data is True


def test_wipe(salt_ssh_cli):
    """
    Ensure --wipe is respected by the state module wrapper
    issue #61083
    """
    ret = salt_ssh_cli.run("config.get", "thin_dir")
    assert ret.returncode == 0
    thin_dir = pathlib.Path(ret.data)
    assert thin_dir.exists()
    # only few modules (state and cp) will actually respect --wipe
    # (see commit #8a414d53284ec04940540ebd823306ab5119e105)
    salt_ssh_cli.run("--wipe", "state.apply")
    assert not thin_dir.exists()


def test_set_path(salt_ssh_cli, tmp_path, salt_ssh_roster_file):
    """
    test setting the path env variable
    """
    path = "/pathdoesnotexist/"
    roster_file = tmp_path / "roster-set-path"
    with salt.utils.files.fopen(salt_ssh_roster_file) as rfh:
        roster_data = salt.utils.yaml.safe_load(rfh)
        roster_data["localhost"].update(
            {
                "set_path": f"$PATH:/usr/local/bin/:{path}",
            }
        )
    with salt.utils.files.fopen(roster_file, "w") as wfh:
        salt.utils.yaml.safe_dump(roster_data, wfh)

    ret = salt_ssh_cli.run(f"--roster-file={roster_file}", "environ.get", "PATH")
    assert ret.returncode == 0
    assert path in ret.data


def test_tty(salt_ssh_cli, tmp_path, salt_ssh_roster_file):
    """
    test using tty
    """
    roster_file = tmp_path / "roster-tty"
    with salt.utils.files.fopen(salt_ssh_roster_file) as rfh:
        roster_data = salt.utils.yaml.safe_load(rfh)
        roster_data["localhost"].update({"tty": True})
    with salt.utils.files.fopen(roster_file, "w") as wfh:
        salt.utils.yaml.safe_dump(roster_data, wfh)
    ret = salt_ssh_cli.run(f"--roster-file={roster_file}", "test.ping")
    assert ret.returncode == 0
    assert ret.data is True


def test_retcode_exe_run_fail(salt_ssh_cli):
    """
    Verify salt-ssh passes through the retcode it receives.
    """
    ret = salt_ssh_cli.run("file.touch", "/tmp/non/ex/is/tent")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, dict)
    # This should be the exact output, but some other warnings
    # might be printed to stderr.
    assert "Error running 'file.touch': No such file or directory" in ret.data["stderr"]


def test_retcode_exe_run_exception(salt_ssh_cli):
    """
    Verify salt-ssh passes through the retcode it receives
    when an exception is thrown. (Ref #50727)
    """
    ret = salt_ssh_cli.run("salttest.jinja_error")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, dict)
    assert ret.data["stderr"].endswith("Exception: hehehe")


@pytest.mark.usefixtures("invalid_json_exe_mod")
def test_retcode_json_decode_error(salt_ssh_cli):
    """
    Verify salt-ssh exits with a non-zero exit code when
    it cannot decode the output of a command.
    """
    ret = salt_ssh_cli.run("whoops.test")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, dict)
    assert (
        ret.data["stdout"]
        == '{  "local": {    "whoops": "hrhrhr"  }Warning: Chaos is not a letter\n}'
    )
    assert ret.data["_error"] == "Failed to return clean data"
    assert ret.data["retcode"] == 0


@pytest.mark.usefixtures("invalid_return_exe_mod")
def test_retcode_invalid_return(salt_ssh_cli):
    """
    Verify salt-ssh exits with a non-zero exit code when
    the decoded command output is invalid.
    """
    ret = salt_ssh_cli.run("whoopsiedoodle.test", "false")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, dict)
    assert ret.data["stdout"] == '{"no_local_key_present": "Chaos is a ladder though"}'
    assert ret.data["_error"] == "Return dict was malformed"
    assert ret.data["retcode"] == 0
    assert ret.data["parsed"] == {"no_local_key_present": "Chaos is a ladder though"}


@pytest.mark.usefixtures("remote_exception_wrap_mod")
def test_wrapper_unwrapped_command_exception(salt_ssh_cli):
    """
    Verify salt-ssh does not return unexpected exception output to wrapper modules.
    """
    ret = salt_ssh_cli.run("check_exception.failure")
    assert ret.returncode == EX_AGGREGATE
    # "Probably got garbage" would be returned as a string (the module return),
    # so no need to check
    assert isinstance(ret.data, dict)
    assert ret.data
    assert (
        "Error running 'disk.usage': Invalid flag passed to disk.usage"
        in ret.data["stderr"]
    )


@pytest.mark.usefixtures("remote_parsing_failure_wrap_mod", "invalid_json_exe_mod")
def test_wrapper_unwrapped_command_parsing_failure(salt_ssh_cli):
    """
    Verify salt-ssh does not return unexpected unparsable output to wrapper modules.
    """
    ret = salt_ssh_cli.run("check_parsing.failure", "whoops")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data["_error"] == "Failed to return clean data"
    assert ret.data["retcode"] == 0
    assert (
        ret.data["stdout"]
        == '{  "local": {    "whoops": "hrhrhr"  }Warning: Chaos is not a letter\n}'
    )


@pytest.mark.usefixtures("remote_parsing_failure_wrap_mod", "invalid_return_exe_mod")
def test_wrapper_unwrapped_command_invalid_return(salt_ssh_cli):
    """
    Verify salt-ssh does not return unexpected unparsable output to wrapper modules.
    """
    ret = salt_ssh_cli.run("check_parsing.failure", "whoopsiedoodle")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data["_error"] == "Return dict was malformed"
    assert ret.data["retcode"] == 0
    assert (
        ret.data["stdout"]
        == '{"local": {"no_return_key_present": "Chaos is a ladder though"}}'
    )
    assert ret.data["parsed"] == {
        "local": {"no_return_key_present": "Chaos is a ladder though"}
    }


@pytest.fixture(scope="module")
def utils_dependent_module(salt_run_cli, salt_master):
    module_contents = r"""
import customutilsmodule


def __virtual__():
    return "utilsync"


def test():
    return customutilsmodule.test()
"""
    utils_contents = r"""
def test():
    return "success"
"""
    module_tempfile = salt_master.state_tree.base.temp_file(
        "_modules/utilsync.py", contents=module_contents
    )
    util_tempfile = salt_master.state_tree.base.temp_file(
        "_utils/customutilsmodule.py", contents=utils_contents
    )
    with module_tempfile, util_tempfile:
        yield


@pytest.mark.usefixtures("utils_dependent_module")
def test_custom_utils_are_present_on_target(salt_ssh_cli):
    ret = salt_ssh_cli.run("utilsync.test")
    assert ret.returncode == 0
    assert ret.data == "success"

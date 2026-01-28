import subprocess

import pytest
from pytestskipmarkers.utils import platform

import salt.version
from salt.utils.versions import Version


def test_salt_call_local(salt_call_cli):
    """
    Test salt-call --local test.ping
    """
    ret = salt_call_cli.run("--local", "test.ping")
    assert ret.returncode == 0
    assert ret.data is True


def test_salt_call(salt_call_cli, salt_master):
    """
    Test salt-call test.ping
    """
    assert salt_master.is_running()

    ret = salt_call_cli.run("test.ping")
    assert ret.returncode == 0
    assert ret.data is True


@pytest.fixture
def state_name(salt_master):
    name = "state_name"
    sls_contents = """
    test_foo:
      test.succeed_with_changes:
          - name: foo
    """
    with salt_master.state_tree.base.temp_file(f"{name}.sls", sls_contents):
        if not platform.is_windows() and not platform.is_darwin():
            subprocess.run(
                [
                    "chown",
                    "-R",
                    "salt:salt",
                    str(salt_master.state_tree.base.write_path),
                ],
                check=False,
            )
        yield name


@pytest.fixture
def state_name_dict_arg(salt_master):
    name = "state_name_dict_arg"
    sls_contents = """
    test_foo:
      test.succeed_with_changes:
          name: foo
    """
    with salt_master.state_tree.base.temp_file(f"{name}.sls", sls_contents):
        if not platform.is_windows() and not platform.is_darwin():
            subprocess.run(
                [
                    "chown",
                    "-R",
                    "salt:salt",
                    str(salt_master.state_tree.base.write_path),
                ],
                check=False,
            )
        yield name


@pytest.mark.parametrize("fixture_name", ["state_name", "state_name_dict_arg"])
def test_sls(salt_call_cli, salt_master, fixture_name, request):
    """
    Test calling a sls file
    """
    min_version_required = Version("3008.0")
    current_version = Version(salt.version.__version__)
    if fixture_name == "state_name_dict_arg" and current_version < min_version_required:
        pytest.skip(
            f"requires Salt >= {min_version_required}, running {current_version}"
        )
    assert salt_master.is_running()
    sls_id = request.getfixturevalue(fixture_name)

    ret = salt_call_cli.run("state.apply", sls_id)
    assert ret.returncode == 0
    assert ret.data
    sls_ret = ret.data[next(iter(ret.data))]
    assert sls_ret["changes"]["testing"]["new"] == "Something pretended to change"


def test_salt_call_local_sys_doc_none(salt_call_cli):
    """
    Test salt-call --local sys.doc none
    """
    ret = salt_call_cli.run("--local", "sys.doc", "none")
    assert ret.returncode == 0
    assert not ret.data


def test_salt_call_local_sys_doc_aliases(salt_call_cli):
    """
    Test salt-call --local sys.doc aliases
    """
    ret = salt_call_cli.run("--local", "sys.doc", "aliases.list_aliases")
    assert ret.returncode == 0
    assert "aliases.list_aliases" in ret.data


@pytest.mark.skip_on_windows
def test_salt_call_cmd_run_id_runas(salt_call_cli, pkg_tests_account, caplog):
    """
    Test salt-call --local cmd_run id with runas
    """
    ret = salt_call_cli.run(
        "--local", "cmd.run", "id", runas=pkg_tests_account.username
    )
    assert "Environment could not be retrieved for user" not in caplog.text
    assert str(pkg_tests_account.info.uid) in ret.stdout
    assert str(pkg_tests_account.info.gid) in ret.stdout

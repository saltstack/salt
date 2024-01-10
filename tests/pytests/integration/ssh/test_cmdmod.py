import pytest

pytestmark = [pytest.mark.slow_test]


@pytest.fixture(scope="module", autouse=True)
def pillar_tree(base_env_pillar_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    basic_pillar_file = """
    alot: many
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    basic_tempfile = pytest.helpers.temp_file(
        "basic.sls", basic_pillar_file, base_env_pillar_tree_root_dir
    )

    with top_tempfile, basic_tempfile:
        yield


@pytest.fixture(scope="module")
def script_templated(base_env_state_tree_root_dir):
    contents = """
#!/usr/bin/env bash

echo {{ pillar["alot"] }}
"""
    with pytest.helpers.temp_file(
        "parrot.sh", contents, base_env_state_tree_root_dir
    ) as script:
        yield f"salt://{script.name}"


def test_script(salt_ssh_cli):
    args = "saltines crackers biscuits=yes"
    script = "salt://script.py"
    ret = salt_ssh_cli.run("cmd.script", script, args)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data["stdout"] == args


def test_script_query_string(salt_ssh_cli):
    args = "saltines crackers biscuits=yes"
    script = "salt://script.py?saltenv=base"
    ret = salt_ssh_cli.run("cmd.script", script, args)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data["stdout"] == args


def test_script_cwd(salt_ssh_cli, tmp_path):
    args = "saltines crackers biscuits=yes"
    script = "salt://script.py"
    # can't pass cwd as kwarg
    ret = salt_ssh_cli.run("cmd.script", script, args, tmp_path)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data["stdout"] == args


def test_script_cwd_with_space(salt_ssh_cli, tmp_path):
    tmp_cwd = tmp_path / "test 2"
    tmp_cwd.mkdir()
    args = "saltines crackers biscuits=yes"
    script = "salt://script.py"
    ret = salt_ssh_cli.run("cmd.script", script, args, cwd=tmp_cwd)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data["stdout"] == args


@pytest.mark.parametrize("template", (None, "jinja"))
def test_script_nonexistent(salt_ssh_cli, template):
    script = "salt://non/ex/is/tent.sh"
    ret = salt_ssh_cli.run("cmd.script", script, "", template=template)
    assert ret.returncode == 0  # meh
    assert isinstance(ret.data, dict)
    assert ret.data
    assert "cache_error" in ret.data
    assert "retcode" in ret.data
    assert ret.data["retcode"] == 1


@pytest.mark.parametrize("pillar", (None, {"alot": "meow"}))
def test_script_template(salt_ssh_cli, script_templated, pillar):
    ret = salt_ssh_cli.run(
        "cmd.script", script_templated, template="jinja", pillar=pillar
    )
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data["stdout"] == (pillar or {}).get("alot", "many")


def test_script_retcode(salt_ssh_cli):
    script = "salt://script.py"
    ret = salt_ssh_cli.run("cmd.script_retcode", script)
    assert ret.returncode == 0
    assert ret.data == 0

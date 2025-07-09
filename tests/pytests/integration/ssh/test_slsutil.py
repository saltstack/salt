import json

import pytest


@pytest.mark.usefixtures("state_tree")
def test_renderer_file(salt_ssh_cli):
    ret = salt_ssh_cli.run("slsutil.renderer", "salt://test.sls")
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert "Ok with def" in ret.data


def test_renderer_string(salt_ssh_cli):
    rend = "{{ salt['test.echo']('foo') }}: {{ pillar['ext_spam'] }}"
    ret = salt_ssh_cli.run("slsutil.renderer", string=rend)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data == {"foo": "eggs"}


def test_serialize(salt_ssh_cli):
    obj = {"foo": "bar"}
    ret = salt_ssh_cli.run("slsutil.serialize", "json", obj)
    assert ret.returncode == 0
    assert isinstance(ret.data, str)
    assert ret.data == json.dumps(obj)


def test_deserialize(salt_ssh_cli):
    obj = {"foo": "bar"}
    data = json.dumps(obj)
    # Need to quote it, otherwise it's deserialized by the
    # test wrapper
    ret = salt_ssh_cli.run("slsutil.deserialize", "json", f"'{data}'")
    assert ret.returncode == 0
    assert isinstance(ret.data, type(obj))
    assert ret.data == obj


@pytest.mark.parametrize(
    "path,expected",
    [
        ("test_deep", True),
        ("test_deep/test.sls", False),
        ("test_deep/b/2", True),
        ("does_not/ex/ist", False),
    ],
)
def test_dir_exists(salt_ssh_cli, path, expected):
    ret = salt_ssh_cli.run("slsutil.dir_exists", path)
    assert ret.returncode == 0
    assert isinstance(ret.data, bool)
    assert ret.data is expected


@pytest.mark.parametrize(
    "path,expected", [("test_deep", False), ("test_deep/test.sls", True)]
)
def test_file_exists(salt_ssh_cli, path, expected):
    ret = salt_ssh_cli.run("slsutil.file_exists", path)
    assert ret.returncode == 0
    assert isinstance(ret.data, bool)
    assert ret.data is expected


@pytest.mark.parametrize(
    "start,name,expected",
    [
        ("test_deep/b/2", "test.sls", "test_deep/b/2/test.sls"),
        ("test_deep/b/2", "cheese", "cheese"),
    ],
)
def test_findup(salt_ssh_cli, start, name, expected):
    ret = salt_ssh_cli.run("slsutil.findup", start, name)
    assert ret.returncode == 0
    assert isinstance(ret.data, str)
    assert ret.data == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("test_deep", True),
        ("test_deep/test.sls", True),
        ("test_deep/b/2", True),
        ("does_not/ex/ist", False),
    ],
)
def test_path_exists(salt_ssh_cli, path, expected):
    ret = salt_ssh_cli.run("slsutil.path_exists", path)
    assert ret.returncode == 0
    assert isinstance(ret.data, bool)
    assert ret.data is expected

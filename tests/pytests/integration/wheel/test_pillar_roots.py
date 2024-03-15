import pytest
from saltfactories.utils import random_string

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def pillar_file_path(salt_master):
    pillar_dir = salt_master.pillar_tree.base.write_path
    testfile = pillar_dir / random_string("foo")
    try:
        yield testfile
    finally:
        if testfile.exists():
            testfile.unlink()


def test_write(client, pillar_file_path):
    ret = client.cmd(
        "pillar_roots.write", kwarg={"data": "foo: bar", "path": pillar_file_path.name}
    )
    assert pillar_file_path.is_file()
    assert ret.find("Wrote data to file") != -1


def test_write_subdir(client, salt_master):
    ret = client.cmd(
        "pillar_roots.write", kwarg={"data": "foo: bar", "path": "sub/dir/file"}
    )
    pillar_file_path = salt_master.pillar_tree.base.write_path / "sub" / "dir" / "file"
    assert pillar_file_path.is_file()
    assert ret.find("Wrote data to file") != -1


def test_cvr_2021_25282(client, pillar_file_path):
    ret = client.cmd(
        "pillar_roots.write",
        kwarg={"data": "foo", "path": f"../{pillar_file_path.name}"},
    )
    assert not pillar_file_path.parent.parent.joinpath(pillar_file_path.name).is_file()
    assert ret.find("Invalid path") != -1


def test_cvr_2021_25282_subdir(client, pillar_file_path):
    ret = client.cmd(
        "pillar_roots.write",
        kwarg={"data": "foo", "path": f"../../{pillar_file_path.name}"},
    )
    assert not pillar_file_path.parent.parent.parent.joinpath(
        pillar_file_path.name
    ).is_file()
    assert ret.find("Invalid path") != -1

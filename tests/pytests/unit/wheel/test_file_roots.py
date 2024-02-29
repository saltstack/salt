import pathlib

import pytest

from salt.wheel import file_roots


def _make_temp_root_file(root, *subpaths, binary=False, dir_only=False):
    """
    Creates a file under the specified subpaths of the given root with the filepath as its content.
    """
    full_path = pathlib.Path(root, *subpaths)
    full_path.parent.mkdir(exist_ok=True, parents=True)
    if not dir_only:
        if binary:
            content = b"\x00"
            full_path.write_bytes(content)
        else:
            content = str(full_path)
            full_path.write_text(content, encoding="utf-8")


@pytest.fixture
def base_root_1(tmp_path):
    path = tmp_path / "base_root_1"
    path.mkdir()
    return path


@pytest.fixture
def base_root_2(tmp_path):
    path = tmp_path / "base_root_2"
    path.mkdir()
    return path


@pytest.fixture
def prod_root_1(tmp_path):
    path = tmp_path / "prod_root_1"
    path.mkdir()
    return path


@pytest.fixture
def prod_root_2(tmp_path):
    path = tmp_path / "prod_root_2"
    path.mkdir()
    return path


@pytest.fixture
def populated_roots(
    base_root_1,
    base_root_2,
    prod_root_1,
    prod_root_2,
):
    roots = {
        "base": [str(base_root_1), str(base_root_2)],
        "prod": [str(prod_root_1), str(prod_root_2)],
    }

    _make_temp_root_file(base_root_1, "test_base_1_file")
    _make_temp_root_file(base_root_1, "common_file")
    _make_temp_root_file(base_root_1, "base_1_subdir", "test_base_1_file_in_subdir")
    _make_temp_root_file(base_root_1, "base_1_subdir", "common_file")
    _make_temp_root_file(
        base_root_1, "base_1_subdir", "test_base_1_file_in_subdir_binary", binary=True
    )
    _make_temp_root_file(
        base_root_1,
        "base_1_subdir",
        "base_1_sub_subdir",
        "test_base_1_file_in_sub_subdir",
    )
    _make_temp_root_file(base_root_2, "test_base_2_file_1")
    _make_temp_root_file(base_root_2, "test_base_2_file_2")
    _make_temp_root_file(base_root_2, "common_file")
    _make_temp_root_file(prod_root_1, "test_prod_2_file")
    _make_temp_root_file(prod_root_1, "common_file")
    _make_temp_root_file(prod_root_1, "prod_1_subdir", dir_only=True)

    return roots


@pytest.fixture
def base_list_env(
    base_root_1,
    base_root_2,
):
    return {
        str(base_root_1): {
            "base_1_subdir": {
                "base_1_sub_subdir": {"test_base_1_file_in_sub_subdir": "f"},
                "test_base_1_file_in_subdir_binary": "f",
                "common_file": "f",
                "test_base_1_file_in_subdir": "f",
            },
            "common_file": "f",
            "test_base_1_file": "f",
        },
        str(base_root_2): {
            "common_file": "f",
            "test_base_2_file_2": "f",
            "test_base_2_file_1": "f",
        },
    }


@pytest.fixture
def prod_list_env(
    prod_root_1,
    prod_root_2,
):
    return {
        str(prod_root_1): {"common_file": "f", "test_prod_2_file": "f"},
        str(prod_root_2): {},
    }


@pytest.fixture
def configure_loader_modules(populated_roots):
    return {
        file_roots: {
            "__opts__": {"file_roots": populated_roots},
        },
    }


def test_find(base_root_1, base_root_2):
    file_name = "common_file"
    expected = [
        {str(base_root_1 / file_name): "txt"},
        {str(base_root_2 / file_name): "txt"},
    ]
    ret = file_roots.find(file_name)
    assert ret == expected


def test_find_prod(prod_root_1):
    file_name = "common_file"
    expected = [{str(prod_root_1 / file_name): "txt"}]
    ret = file_roots.find(file_name, saltenv="prod")
    assert ret == expected


def test_find_in_subdir(base_root_1):
    file_name = pathlib.Path("base_1_subdir", "test_base_1_file_in_subdir")
    expected = [{str(base_root_1 / file_name): "txt"}]
    ret = file_roots.find(str(file_name))
    assert ret == expected


def test_find_does_not_exist():
    file_name = "prod_1_subdir"
    expected = []
    ret = file_roots.find(str(file_name), saltenv="prod")
    assert ret == expected


def test_find_binary(base_root_1):
    file_name = pathlib.Path("base_1_subdir", "test_base_1_file_in_subdir_binary")
    expected = [{str(base_root_1 / file_name): "bin"}]
    ret = file_roots.find(str(file_name))
    assert ret == expected


def test_list_env(base_list_env):
    ret = file_roots.list_env()
    assert ret == base_list_env


def test_list_env_prod(prod_list_env):
    ret = file_roots.list_env(saltenv="prod")
    assert ret == prod_list_env


def test_list_roots(base_list_env, prod_list_env):
    expected = {"base": [base_list_env], "prod": [prod_list_env]}
    ret = file_roots.list_roots()
    assert ret == expected


def test_read(base_root_1, base_root_2):
    file_name = "common_file"
    root_1_file = str(base_root_1 / file_name)
    root_2_file = str(base_root_2 / file_name)
    expected = [{root_1_file: root_1_file}, {root_2_file: root_2_file}]
    ret = file_roots.read(file_name)
    assert ret == expected


def test_read_prod(prod_root_1):
    file_name = "common_file"
    root_1_file = str(prod_root_1 / file_name)
    expected = [{root_1_file: root_1_file}]
    ret = file_roots.read(file_name, saltenv="prod")
    assert ret == expected


def test_read_binary():
    file_name = pathlib.Path("base_1_subdir", "test_base_1_file_in_subdir_binary")
    ret = file_roots.read(str(file_name))
    assert ret == []


def test_read_in_subdir(base_root_1):
    file_name = pathlib.Path("base_1_subdir", "test_base_1_file_in_subdir")
    subdir_file = str(base_root_1 / file_name)
    expected = [{subdir_file: subdir_file}]
    ret = file_roots.read(str(file_name))
    assert ret == expected


def test_write(base_root_1):
    file_name = "testfile"
    ret = file_roots.write(file_name, file_name)
    assert f"Wrote data to file {str(base_root_1 / file_name)}" in ret


def test_write_index(base_root_2):
    file_name = "testfile"
    ret = file_roots.write(file_name, file_name, index=1)
    assert f"Wrote data to file {str(base_root_2 / file_name)}" in ret


def test_write_prod(prod_root_2):
    file_name = "testfile"
    ret = file_roots.write(file_name, file_name, saltenv="prod", index=1)
    assert f"Wrote data to file {str(prod_root_2 / file_name)}" in ret


def test_write_subdir(prod_root_1):
    file_name = str(pathlib.Path("prod_1_subdir", "testfile"))
    ret = file_roots.write(file_name, file_name, saltenv="prod")
    assert f"Wrote data to file {str(prod_root_1 / file_name)}" in ret


def test_write_make_new_subdir(prod_root_2):
    file_name = str(pathlib.Path("prod_2_subdir", "testfile"))
    ret = file_roots.write(file_name, file_name, saltenv="prod", index=1)
    assert f"Wrote data to file {str(prod_root_2 / file_name)}" in ret


def test_write_invalid_env():
    file_name = "testfile"
    env = "not_an_env"
    ret = file_roots.write(file_name, file_name, saltenv=env)
    assert f"{env} is not present" in ret


def test_write_invalid_index():
    file_name = "testfile"
    ret = file_roots.write(file_name, file_name, index=2)
    assert "index 2 in environment base is not present" in ret


def test_write_invalid_absolute_path(base_root_1):
    file_name = str(base_root_1 / "testfile")
    ret = file_roots.write(file_name, file_name)
    assert "is not relative to the environment" in ret


def test_write_invalid_path():
    file_name = str(pathlib.Path("..", "testfile"))
    ret = file_roots.write(file_name, file_name)
    assert "Invalid path: " in ret

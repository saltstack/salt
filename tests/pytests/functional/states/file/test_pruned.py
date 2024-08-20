import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def file(states):
    return states.file


@pytest.fixture(scope="function")
def single_dir_with_file(tmp_path):
    file = tmp_path / "stuff.txt"
    file.write_text("things")
    yield str(tmp_path)


@pytest.fixture(scope="function")
def nested_empty_dirs(tmp_path):
    num_root = 2
    num_mid = 4
    num_last = 2
    for root in range(1, num_root + 1):
        for mid in range(1, num_mid + 1):
            for last in range(1, num_last + 1):
                nest = tmp_path / f"root{root}" / f"mid{mid}" / f"last{last}"
                nest.mkdir(parents=True, exist_ok=True)
    yield str(tmp_path)


@pytest.fixture(scope="function")
def nested_dirs_with_files(tmp_path):
    num_root = 2
    num_mid = 4
    num_last = 2
    for root in range(1, num_root + 1):
        for mid in range(1, num_mid + 1):
            for last in range(1, num_last + 1):
                nest = tmp_path / f"root{root}" / f"mid{mid}" / f"last{last}"
                nest.mkdir(parents=True, exist_ok=True)
                if last % 2:
                    last_file = nest / "stuff.txt"
                    last_file.write_text("things")
    yield str(tmp_path)


def test_pruned_failure(file, single_dir_with_file):
    ret = file.pruned(name=single_dir_with_file)
    assert ret.result is False
    assert not ret.changes["deleted"]
    assert len(ret.changes["errors"]) == 1
    assert ret.comment == f"Failed to remove directory {single_dir_with_file}"


def test_pruned_success_recurse_and_deleted(file, nested_empty_dirs):
    ret = file.pruned(name=nested_empty_dirs, recurse=True)
    assert ret.result is True
    assert len(ret.changes["deleted"]) == 27
    assert ret.comment == "Recursively removed empty directories under {}".format(
        nested_empty_dirs
    )


def test_pruned_success_ignore_errors_and_deleted(file, nested_dirs_with_files):
    ret = file.pruned(name=nested_dirs_with_files, ignore_errors=True)
    assert ret.result is True
    assert len(ret.changes["deleted"]) == 8
    assert ret.comment == "Recursively removed empty directories under {}".format(
        nested_dirs_with_files
    )

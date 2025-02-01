import pytest


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


@pytest.fixture(scope="function")
def source():
    with pytest.helpers.temp_file(contents="Source content") as source:
        yield source


def test_is_link_nostat(file, source):
    target = source.parent / "symlink.lnk"
    target.symlink_to(source)
    try:
        assert file.is_link(str(source), nostat=True) is False
        assert file.is_link(str(target), nostat=True) is True
    finally:
        target.unlink()

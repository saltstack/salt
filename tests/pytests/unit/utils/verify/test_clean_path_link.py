"""
Ensure salt.utils.clean_path works with symlinked directories and files
"""

import ctypes

import pytest

import salt.utils.verify


class Symlink:
    """
    symlink(source, link_name) Creates a symbolic link pointing to source named
    link_name
    """

    def __init__(self):
        self._csl = None

    def __call__(self, source, link_name):
        if self._csl is None:
            self._csl = ctypes.windll.kernel32.CreateSymbolicLinkW
            self._csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
            self._csl.restype = ctypes.c_ubyte
        flags = 0
        if source is not None and source.is_dir():
            flags = 1

        if self._csl(str(link_name), str(source), flags) == 0:
            raise ctypes.WinError()


@pytest.fixture(scope="module")
def symlink():
    return Symlink()


@pytest.fixture
def setup_links(tmp_path, symlink):
    to_path = tmp_path / "linkto"
    from_path = tmp_path / "linkfrom"
    if salt.utils.platform.is_windows():
        kwargs = {}
    else:
        kwargs = {"target_is_directory": True}
    if salt.utils.platform.is_windows():
        symlink(to_path, from_path, **kwargs)
    else:
        from_path.symlink_to(to_path, **kwargs)
    return to_path, from_path


def test_clean_path_symlinked_src(setup_links):
    to_path, from_path = setup_links
    test_path = from_path / "test"
    expect_path = str(to_path / "test")
    ret = salt.utils.verify.clean_path(str(from_path), str(test_path))
    assert ret == expect_path, f"{ret} is not {expect_path}"


def test_clean_path_symlinked_tgt(setup_links):
    to_path, from_path = setup_links
    test_path = to_path / "test"
    expect_path = str(to_path / "test")
    ret = salt.utils.verify.clean_path(str(from_path), str(test_path))
    assert ret == expect_path, f"{ret} is not {expect_path}"


def test_clean_path_symlinked_src_unresolved(setup_links):
    to_path, from_path = setup_links
    test_path = from_path / "test"
    expect_path = str(from_path / "test")
    ret = salt.utils.verify.clean_path(str(from_path), str(test_path), realpath=False)
    assert ret == expect_path, f"{ret} is not {expect_path}"

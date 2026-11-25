import pathlib
import tempfile


def test_tmp_path_world_rw_is_in_the_temporary_directory(tmp_path_world_rw):
    """
    The fixture used to call ``pathlib.Path(basetemp=...)``. ``Path`` has no such
    argument: Python 3.11 ignores it and gives the current directory, and Python
    3.14 raises ``TypeError``.
    """
    assert tmp_path_world_rw.parent == pathlib.Path(tempfile.gettempdir()).resolve()
    assert tmp_path_world_rw.is_dir()
    assert tmp_path_world_rw.stat().st_mode & 0o777 == 0o777

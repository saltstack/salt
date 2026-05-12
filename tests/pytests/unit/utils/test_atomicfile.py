"""
Tests for atomicfile utility module.
"""

import pytest

import salt.utils.files
from salt.utils.atomicfile import atomic_open


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_atomicfile_respects_umask(tmp_path):
    """
    Test that creating a file using atomic_open respects the umask, instead of
    creating the file with 0600 perms.
    """
    new_file = tmp_path / "foo"
    contents = "bar"

    # Set the umask specifically for this test so that we know what the mode of
    # the created file should be.
    with salt.utils.files.set_umask(0o022):
        with atomic_open(str(new_file), "w") as fh_:
            fh_.write(contents)

    assert new_file.read_text() == contents
    assert oct(new_file.stat().st_mode)[-3:] == "644"

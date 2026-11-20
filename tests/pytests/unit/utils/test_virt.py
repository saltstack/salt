import io
import pathlib
import urllib.error

import pytest

import salt.exceptions
import salt.utils.virt
from tests.support.mock import patch


def test_virt_key(tmp_path):
    opts = {"pki_dir": f"{tmp_path / 'pki'}"}
    salt.utils.virt.VirtKey("asdf", "minion", opts)


def test_virt_key_bad_hyper(tmp_path):
    opts = {"pki_dir": f"{tmp_path / 'pki'}"}
    with pytest.raises(salt.exceptions.SaltValidationError):
        salt.utils.virt.VirtKey("asdf/../../../sdf", "minion", opts)


def test_virt_key_bad_id_(tmp_path):
    opts = {"pki_dir": f"{tmp_path / 'pki'}"}
    with pytest.raises(salt.exceptions.SaltValidationError):
        salt.utils.virt.VirtKey("hyper", "minion/../../", opts)


def test_download_remote(tmp_path):
    """
    The downloaded content is written to a new file in the directory and the
    path of the file is returned.
    """
    with patch("urllib.request.urlopen", return_value=io.BytesIO(b"kernel data")):
        path = salt.utils.virt.download_remote(
            "http://example.com/images/linux", str(tmp_path)
        )
    downloaded = pathlib.Path(path)
    assert downloaded.parent == tmp_path
    assert downloaded.name.endswith("-linux")
    assert downloaded.read_bytes() == b"kernel data"


def test_download_remote_raises_the_error_of_the_download(tmp_path):
    error = urllib.error.URLError("no route to host")
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(urllib.error.URLError) as exc:
            salt.utils.virt.download_remote("http://example.com/linux", str(tmp_path))
    assert exc.value is error

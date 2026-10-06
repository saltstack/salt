import io
import sys
import tarfile

import pytest

import salt.utils.tarfileutil as tfutil
from tests.support.mock import patch


def _minimal_tar_bytes(name: str = "hello.txt", data: bytes = b"hi") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        ti = tarfile.TarInfo(name=name)
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def test_extractall_writes_member(tmp_path):
    data = _minimal_tar_bytes()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tar:
        tfutil.extractall(tar, str(tmp_path))  # nosec B202
    assert (tmp_path / "hello.txt").read_bytes() == b"hi"


def test_extract_writes_member(tmp_path):
    data = _minimal_tar_bytes()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tar:
        member = tar.getmember("hello.txt")
        tfutil.extract(tar, member, str(tmp_path))
    assert (tmp_path / "hello.txt").read_bytes() == b"hi"


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="filter kw only enforced on 3.12+"
)
def test_extractall_passes_data_filter_on_py312(tmp_path):
    data = _minimal_tar_bytes()
    tar = tarfile.open(fileobj=io.BytesIO(data), mode="r")
    try:
        with patch.object(tar, "extractall", wraps=tar.extractall) as m:
            tfutil.extractall(tar, str(tmp_path))  # nosec B202
        m.assert_called_once()
        _, kwargs = m.call_args
        assert kwargs.get("filter") == "data"
    finally:
        tar.close()


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="filter kw only enforced on 3.12+"
)
def test_extract_passes_data_filter_on_py312(tmp_path):
    data = _minimal_tar_bytes()
    tar = tarfile.open(fileobj=io.BytesIO(data), mode="r")
    try:
        member = tar.getmember("hello.txt")
        with patch.object(tar, "extract", wraps=tar.extract) as m:
            tfutil.extract(tar, member, str(tmp_path))
        m.assert_called_once()
        _, kwargs = m.call_args
        assert kwargs.get("filter") == "data"
    finally:
        tar.close()

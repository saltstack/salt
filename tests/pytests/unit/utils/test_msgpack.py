import pytest
import salt.utils.msgpack
from tests.support.mock import MagicMock, patch


def test_load_encoding(tmpdir):
    """
    test when using msgpack version >= 1.0.0 we
    can still load/dump when using unsupported
    encoding kwarg. This kwarg has been removed
    in this version.

    https://github.com/msgpack/msgpack-python/blob/master/ChangeLog.rst
    """
    fname = tmpdir.join("test_load_encoding.txt")
    kwargs = {"encoding": "utf-8"}
    data = [1, 2, 3]
    with patch.object(salt.utils.msgpack, "version", (1, 0, 0)):
        with salt.utils.files.fopen(fname.strpath, "wb") as wfh:
            salt.utils.msgpack.dump(data, wfh)
        with salt.utils.files.fopen(fname.strpath, "rb") as rfh:
            ret = salt.utils.msgpack.load(rfh, **kwargs)

        assert ret == data


@pytest.mark.parametrize(
    "version,encoding", [((2, 1, 3), False), ((1, 0, 0), False), ((0, 6, 2), True)]
)
def test_load_multiple_versions(version, encoding, tmpdir):
    """
    test when using msgpack on multiple versions that
    we only remove encoding on >= 1.0.0
    """
    fname = tmpdir.join("test_load_multipl_versions.txt")
    with patch.object(salt.utils.msgpack, "version", version):
        data = [1, 2, 3]

        mock_dump = MagicMock(return_value=data)
        patch_dump = patch("msgpack.pack", mock_dump)

        mock_load = MagicMock(return_value=data)
        patch_load = patch("msgpack.unpack", mock_load)

        kwargs = {"encoding": "utf-8"}
        with patch_dump, patch_load:
            with salt.utils.files.fopen(fname.strpath, "wb") as wfh:
                salt.utils.msgpack.dump(data, wfh, encoding="utf-8")
                if encoding:
                    assert "encoding" in mock_dump.call_args.kwargs
                else:
                    assert "encoding" not in mock_dump.call_args.kwargs

            with salt.utils.files.fopen(fname.strpath, "rb") as rfh:
                salt.utils.msgpack.load(rfh, **kwargs)
                if encoding:
                    assert "encoding" in mock_load.call_args.kwargs
                else:
                    assert "encoding" not in mock_load.call_args.kwargs

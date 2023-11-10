import salt.utils.msgpack
from tests.support.mock import MagicMock, patch


def test_load_encoding(tmp_path):
    """
    test when using msgpack version >= 1.0.0 we
    can still load/dump when using unsupported
    encoding kwarg. This kwarg has been removed
    in this version.

    https://github.com/msgpack/msgpack-python/blob/master/ChangeLog.rst
    """
    fname = str(tmp_path / "test_load_encoding.txt")
    kwargs = {"encoding": "utf-8"}
    data = [1, 2, 3]
    with salt.utils.files.fopen(fname, "wb") as wfh:
        salt.utils.msgpack.dump(data, wfh)
    with salt.utils.files.fopen(fname, "rb") as rfh:
        ret = salt.utils.msgpack.load(rfh, **kwargs)

    assert ret == data


def test_encoding_removal(tmp_path):
    """
    test when using msgpack on multiple versions that
    we only remove encoding on >= 1.0.0
    """
    fname = str(tmp_path / "test_load_multipl_versions.txt")
    data = [1, 2, 3]

    mock_dump = MagicMock(return_value=data)
    patch_dump = patch("msgpack.pack", mock_dump)

    mock_load = MagicMock(return_value=data)
    patch_load = patch("msgpack.unpack", mock_load)

    kwargs = {"encoding": "utf-8"}
    with patch_dump, patch_load:
        with salt.utils.files.fopen(fname, "wb") as wfh:
            salt.utils.msgpack.dump(data, wfh, encoding="utf-8")
            assert "encoding" not in mock_dump.call_args.kwargs

        with salt.utils.files.fopen(fname, "rb") as rfh:
            salt.utils.msgpack.load(rfh, **kwargs)
            assert "encoding" not in mock_load.call_args.kwargs


def test_sanitize_msgpack_unpack_kwargs():
    """
    Test helper function _sanitize_msgpack_unpack_kwargs
    """
    expected = {"raw": True, "strict_map_key": True, "use_bin_type": True}
    kwargs = {"strict_map_key": True, "use_bin_type": True, "encoding": "utf-8"}
    assert salt.utils.msgpack._sanitize_msgpack_unpack_kwargs(kwargs) == expected

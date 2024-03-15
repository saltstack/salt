import pytest

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
    with patch.object(salt.utils.msgpack, "version", (1, 0, 0)):
        with salt.utils.files.fopen(fname, "wb") as wfh:
            salt.utils.msgpack.dump(data, wfh)
        with salt.utils.files.fopen(fname, "rb") as rfh:
            ret = salt.utils.msgpack.load(rfh, **kwargs)

        assert ret == data


@pytest.mark.parametrize(
    "version",
    [
        (2, 1, 3),
        (1, 0, 0),
    ],
)
def test_load_multiple_versions(version, tmp_path):
    """
    test when using msgpack on multiple versions that
    we only remove encoding on >= 1.0.0
    """
    fname = str(tmp_path / "test_load_multipl_versions.txt")
    with patch.object(salt.utils.msgpack, "version", version):
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


@pytest.mark.parametrize(
    "version,exp_kwargs",
    [
        ((1, 0, 0), {"raw": True, "strict_map_key": True, "use_bin_type": True}),
        ((0, 6, 0), {"raw": True, "strict_map_key": True, "use_bin_type": True}),
    ],
)
def test_sanitize_msgpack_kwargs(version, exp_kwargs):
    """
    Test helper function _sanitize_msgpack_kwargs
    """
    kwargs = {"strict_map_key": True, "raw": True, "use_bin_type": True}

    with patch.object(salt.utils.msgpack, "version", version):
        assert salt.utils.msgpack._sanitize_msgpack_kwargs(kwargs.copy()) == exp_kwargs


@pytest.mark.parametrize(
    "version,exp_kwargs",
    [
        ((2, 0, 0), {"raw": True, "strict_map_key": True, "use_bin_type": True}),
        ((1, 0, 0), {"raw": True, "strict_map_key": True, "use_bin_type": True}),
    ],
)
def test_sanitize_msgpack_unpack_kwargs(version, exp_kwargs):
    """
    Test helper function _sanitize_msgpack_unpack_kwargs
    """
    kwargs = {"strict_map_key": True, "use_bin_type": True, "encoding": "utf-8"}
    with patch.object(salt.utils.msgpack, "version", version):
        assert (
            salt.utils.msgpack._sanitize_msgpack_unpack_kwargs(kwargs.copy())
            == exp_kwargs
        )

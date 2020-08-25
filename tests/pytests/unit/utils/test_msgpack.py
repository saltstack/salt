import os

import pytest
import salt.utils.msgpack
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture
def test_fn():
    fn_ = os.path.join(RUNTIME_VARS.TMP, "test_msgpack")
    yield fn_
    if os.path.exists(fn_):
        os.remove(fn_)


def test_load_encoding(test_fn):
    """
    test when using msgpack version >= 1.0.0 we
    can still load/dump when using unsupported
    encoding kwarg. This kwarg has been removed
    in this version.

    https://github.com/msgpack/msgpack-python/blob/master/ChangeLog.rst
    """
    salt.utils.msgpack.version = (1, 0, 0)

    kwargs = {"encoding": "utf-8"}
    data = [1, 2, 3]
    with salt.utils.files.fopen(test_fn, "wb") as fh_:
        salt.utils.msgpack.dump(data, fh_)
    with salt.utils.files.fopen(test_fn, "rb") as fh_:
        ret = salt.utils.msgpack.load(fh_, **kwargs)

    assert ret == data


@pytest.mark.parametrize(
    "version,encoding", [((2, 1, 3), False), ((1, 0, 0), False), ((0, 6, 2), True)]
)
def test_load_multiple_versions(version, encoding, test_fn):
    """
    test when using msgpack on multiple versions that
    we only remove encoding on >= 1.0.0
    """
    salt.utils.msgpack.version = version
    data = [1, 2, 3]

    mock_dump = MagicMock(return_value=data)
    patch_dump = patch("msgpack.pack", mock_dump)

    mock_load = MagicMock(return_value=data)
    patch_load = patch("msgpack.unpack", mock_load)

    kwargs = {"encoding": "utf-8"}
    with patch_dump, patch_load:
        with salt.utils.files.fopen(test_fn, "wb") as fh_:
            salt.utils.msgpack.dump(data, fh_, encoding="utf-8")
            if encoding:
                assert "encoding" in mock_dump.call_args.kwargs
            else:
                assert "encoding" not in mock_dump.call_args.kwargs

        with salt.utils.files.fopen(test_fn, "rb") as fh_:
            salt.utils.msgpack.load(fh_, **kwargs)
            if encoding:
                assert "encoding" in mock_load.call_args.kwargs
            else:
                assert "encoding" not in mock_load.call_args.kwargs

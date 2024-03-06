import inspect
import io
import os
import struct
import sys

import msgpack
import pytest

import salt.utils.msgpack
import salt.utils.odict
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
    "version,encoding", [((2, 1, 3), False), ((1, 0, 0), False), ((0, 6, 2), True)]
)
def test_load_multiple_versions(version, encoding, tmp_path):
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
                if encoding:
                    assert "encoding" in mock_dump.call_args.kwargs
                else:
                    assert "encoding" not in mock_dump.call_args.kwargs

            with salt.utils.files.fopen(fname, "rb") as rfh:
                salt.utils.msgpack.load(rfh, **kwargs)
                if encoding:
                    assert "encoding" in mock_load.call_args.kwargs
                else:
                    assert "encoding" not in mock_load.call_args.kwargs


@pytest.mark.parametrize(
    "version,exp_kwargs",
    [
        ((0, 6, 0), {"raw": True, "strict_map_key": True, "use_bin_type": True}),
        ((0, 5, 2), {"raw": True, "use_bin_type": True}),
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
        ((1, 0, 0), {"raw": True, "strict_map_key": True, "use_bin_type": True}),
        (
            (0, 6, 0),
            {"strict_map_key": True, "use_bin_type": True, "encoding": "utf-8"},
        ),
        ((0, 5, 2), {"use_bin_type": True, "encoding": "utf-8"}),
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


def test_version():
    """
    Verify that the version exists and returns a value in the expected format
    """
    version = salt.utils.msgpack.version
    assert isinstance(version, tuple)
    assert version > (0, 0, 0)


def test_packer():
    data = os.urandom(1024)
    packer = salt.utils.msgpack.Packer()
    unpacker = msgpack.Unpacker(None)

    packed = packer.pack(data)
    # Sanity Check
    assert packed
    assert data != packed

    # Reverse the packing and the result should be equivalent to the original data
    unpacker.feed(packed)
    unpacked = msgpack.unpackb(packed)
    assert data == unpacked


def test_unpacker():
    data = os.urandom(1024)
    packer = msgpack.Packer()
    unpacker = salt.utils.msgpack.Unpacker(None)

    packed = packer.pack(data)
    # Sanity Check
    assert packed
    assert data != packed

    # Reverse the packing and the result should be equivalent to the original data
    unpacker.feed(packed)
    unpacked = msgpack.unpackb(packed)
    assert data == unpacked


def test_array_size():
    sizes = [0, 5, 50, 1000]
    bio = io.BytesIO()
    packer = salt.utils.msgpack.Packer()
    for size in sizes:
        bio.write(packer.pack_array_header(size))
        for i in range(size):
            bio.write(packer.pack(i))

    bio.seek(0)
    unpacker = salt.utils.msgpack.Unpacker(bio, use_list=True)
    for size in sizes:
        assert unpacker.unpack() == list(range(size))


def test_manual_reset():
    sizes = [0, 5, 50, 1000]
    packer = salt.utils.msgpack.Packer(autoreset=False)
    for size in sizes:
        packer.pack_array_header(size)
        for i in range(size):
            packer.pack(i)

    bio = io.BytesIO(packer.bytes())
    unpacker = salt.utils.msgpack.Unpacker(bio, use_list=True)
    for size in sizes:
        assert unpacker.unpack() == list(range(size))

    packer.reset()
    assert packer.bytes() == b""


def test_map_size():
    sizes = [0, 5, 50, 1000]
    bio = io.BytesIO()
    packer = salt.utils.msgpack.Packer()
    for size in sizes:
        bio.write(packer.pack_map_header(size))
        for i in range(size):
            bio.write(packer.pack(i))  # key
            bio.write(packer.pack(i * 2))  # value

    bio.seek(0)
    if salt.utils.msgpack.version > (0, 6, 0):
        unpacker = salt.utils.msgpack.Unpacker(bio, strict_map_key=False)
    else:
        unpacker = salt.utils.msgpack.Unpacker(bio)
    for size in sizes:
        assert unpacker.unpack() == {i: i * 2 for i in range(size)}


def test_max_buffer_size():
    """
    Test if max buffer size allows at least 100MiB
    """
    bio = io.BytesIO()
    bio.write(salt.utils.msgpack.packb("0" * (100 * 1024 * 1024)))
    bio.seek(0)
    unpacker = salt.utils.msgpack.Unpacker(bio)
    try:
        unpacker.unpack()
    except ValueError:
        pytest.fail("ValueError should not be raised")


def test_exceptions():
    # Verify that this exception exists
    assert salt.utils.msgpack.exceptions.PackValueError
    assert salt.utils.msgpack.exceptions.UnpackValueError
    assert salt.utils.msgpack.exceptions.PackValueError
    assert salt.utils.msgpack.exceptions.UnpackValueError


def test_function_aliases():
    """
    Fail if core functionality from msgpack is missing in the utility
    """

    def sanitized(item):
        if inspect.isfunction(getattr(msgpack, item)):
            # Only check objects that exist in the same file as msgpack
            return inspect.getfile(getattr(msgpack, item)) == inspect.getfile(msgpack)

    msgpack_items = {x for x in dir(msgpack) if not x.startswith("_") and sanitized(x)}
    msgpack_util_items = set(dir(salt.utils.msgpack))
    assert (
        not msgpack_items - msgpack_util_items
    ), "msgpack functions with no alias in `salt.utils.msgpack`"


def check_base(pack_func, unpack_func):
    """
    In msgpack, 'dumps' is an alias for 'packb' and 'loads' is an alias for 'unpackb'.
    Verify that both salt.utils.msgpack function variations pass the exact same test
    """
    data = os.urandom(1024)

    packed = pack_func(data)
    # Sanity Check
    assert packed
    assert isinstance(packed, bytes)
    assert data != packed

    # Reverse the packing and the result should be equivalent to the original data
    unpacked = unpack_func(packed)
    assert data == unpacked


def check_buffered_base(pack_func, unpack_func):
    data = os.urandom(1024).decode(errors="ignore")
    buffer = io.BytesIO()
    # Sanity check, we are not borking the BytesIO read function
    assert io.BytesIO.read != buffer.read
    buffer.read = buffer.getvalue
    pack_func(data, buffer)
    # Sanity Check
    assert buffer.getvalue()
    assert isinstance(buffer.getvalue(), bytes)
    assert data != buffer.getvalue()

    # Reverse the packing and the result should be equivalent to the original data
    unpacked = unpack_func(buffer)

    if isinstance(unpacked, bytes):
        unpacked = unpacked.decode()

    assert data == unpacked


def check_unpack_array_header_from_file(pack_func, **kwargs):
    f = io.BytesIO(pack_func([1, 2, 3, 4]))
    unpacker = salt.utils.msgpack.Unpacker(f)
    assert unpacker.read_array_header() == 4
    assert unpacker.unpack() == 1
    assert unpacker.unpack() == 2
    assert unpacker.unpack() == 3
    assert unpacker.unpack() == 4
    with pytest.raises(salt.utils.msgpack.exceptions.OutOfData):
        unpacker.unpack()


def check_unpacker_hook_refcnt(pack_func, **kwargs):
    result = []

    def hook(x):
        result.append(x)
        return x

    basecnt = sys.getrefcount(hook)

    up = salt.utils.msgpack.Unpacker(object_hook=hook, list_hook=hook)

    assert sys.getrefcount(hook) >= basecnt + 2

    up.feed(pack_func([{}]))
    up.feed(pack_func([{}]))
    assert up.unpack() == [{}]
    assert up.unpack() == [{}]
    assert result == [{}, [{}], {}, [{}]]

    del up

    assert sys.getrefcount(hook) == basecnt


def check_unpacker_ext_hook(pack_func, **kwargs):
    class MyUnpacker(salt.utils.msgpack.Unpacker):
        def __init__(self):
            super().__init__(ext_hook=self._hook, **raw)

        def _hook(self, code, data):
            if code == 1:
                return int(data)
            else:
                return salt.utils.msgpack.ExtType(code, data)

    unpacker = MyUnpacker()
    unpacker.feed(pack_func({"a": 1}))
    assert unpacker.unpack() == {"a": 1}
    unpacker.feed(pack_func({"a": salt.utils.msgpack.ExtType(1, b"123")}))
    assert unpacker.unpack() == {"a": 123}
    unpacker.feed(pack_func({"a": salt.utils.msgpack.ExtType(2, b"321")}))
    assert unpacker.unpack() == {"a": salt.utils.msgpack.ExtType(2, b"321")}


def check_pack_unicode(pack_func, unpack_func):
    test_data = ["", "abcd", ["defgh"], "Русский текст"]
    for td in test_data:
        ret = unpack_func(pack_func(td), use_list=True, **raw)
        assert ret == td
        packer = salt.utils.msgpack.Packer()
        data = packer.pack(td)
        ret = salt.utils.msgpack.Unpacker(
            io.BytesIO(data), use_list=True, **raw
        ).unpack()
        assert ret == td


def check_pack_bytes(pack_func, unpack_func):
    test_data = [
        b"",
        b"abcd",
        (b"defgh",),
    ]
    for td in test_data:
        ret = unpack_func(pack_func(test_data), use_list=False, strict_map=True)
        assert list(ret) == test_data


def check_pack_byte_arrays(pack_func, unpack_func):
    test_data = [
        bytearray(b""),
        bytearray(b"abcd"),
        (bytearray(b"defgh"),),
    ]
    for td in test_data:
        ret = unpack_func(pack_func(test_data), use_list=False, strict_map_key=False)
        assert ret == test_data


raw = {"raw": False} if msgpack.version > (0, 5, 2) else {}


def check_ignore_unicode_errors(pack_func, unpack_func):
    ret = unpack_func(
        pack_func(b"abc\xeddef", use_bin_type=False), unicode_errors="ignore", **raw
    )
    assert "abcdef" == ret


def check_strict_unicode_unpack(pack_func, unpack_func):
    packed = pack_func(b"abc\xeddef", use_bin_type=False)
    with pytest.raises(UnicodeDecodeError):
        unpack_func(packed, use_list=True, **raw)


def check_ignore_errors_pack(pack_func, unpack_func):
    ret = unpack_func(
        pack_func("abc\uDC80\uDCFFdef", use_bin_type=True, unicode_errors="ignore"),
        use_list=True,
        **raw,
    )
    assert "abcdef" == ret


def check_decode_binary(pack_func, unpack_func):
    ret = unpack_func(pack_func(b"abc"), use_list=True)
    assert b"abc" == ret


def check_pack_float(pack_func, **kwargs):
    assert b"\xca" + struct.pack(">f", 1.0) == pack_func(1.0, use_single_float=True)
    assert b"\xcb" + struct.pack(">d", 1.0) == pack_func(1.0, use_single_float=False)


def check_odict(pack_func, unpack_func):
    seq = [(b"one", 1), (b"two", 2), (b"three", 3), (b"four", 4)]

    od = salt.utils.odict.OrderedDict(seq)
    assert dict(seq) == unpack_func(pack_func(od), use_list=True)

    def pair_hook(seq):
        return list(seq)

    assert seq == unpack_func(pack_func(od), object_pairs_hook=pair_hook, use_list=True)


def check_pair_list(unpack_func, **kwargs):
    pairlist = [(b"a", 1), (2, b"b"), (b"foo", b"bar")]
    packer = salt.utils.msgpack.Packer()
    packed = packer.pack_map_pairs(pairlist)
    unpacked = unpack_func(packed, object_pairs_hook=list, strict_map_key=False)
    assert pairlist == unpacked


def check_get_buffer(pack_func, **kwargs):
    packer = msgpack.Packer(autoreset=False, use_bin_type=True)
    packer.pack([1, 2])
    strm = io.BytesIO()
    strm.write(packer.getbuffer())
    written = strm.getvalue()

    expected = pack_func([1, 2], use_bin_type=True)
    assert expected == written


functions_to_test = [
    {"pack_func": salt.utils.msgpack.packb, "unpack_func": msgpack.unpackb},
    {"pack_func": msgpack.packb, "unpack_func": salt.utils.msgpack.unpackb},
]
# These functions are equivalent but could potentially be overwritten
if salt.utils.msgpack.dumps is not salt.utils.msgpack.packb:
    functions_to_test.append(
        {"pack_func": salt.utils.msgpack.dumps, "unpack_func": msgpack.unpackb}
    )
if salt.utils.msgpack.loads is not salt.utils.msgpack.unpackb:
    functions_to_test.append(
        {"pack_func": msgpack.packb, "unpack_func": salt.utils.msgpack.loads}
    )


@pytest.mark.parametrize(
    "test_func",
    [
        check_base,
        check_buffered_base,
        check_unpack_array_header_from_file,
        check_unpacker_hook_refcnt,
        check_unpacker_ext_hook,
        check_pack_unicode,
        check_pack_bytes,
        check_pack_byte_arrays,
        check_ignore_unicode_errors,
        check_strict_unicode_unpack,
        check_ignore_errors_pack,
        check_decode_binary,
        check_pack_float,
        check_odict,
        check_pair_list,
        check_get_buffer,
    ],
)
@pytest.mark.parametrize("func_args", functions_to_test)
def test_binary_function_compatibility(test_func, func_args):
    try:
        vanilla_run = test_func(
            pack_func=msgpack.packb,
            unpack_func=msgpack.unpackb,
        )
    except Exception as exc:  # pylint: disable=broad-except
        vanilla_run = exc
    func_name = (
        func_args["pack_func"]
        if func_args["pack_func"].__module__.startswith("salt.utils")
        else func_args["unpack_func"]
    )
    try:
        run = test_func(**func_args)
    except Exception as exc:  # pylint: disable=broad-except
        run = exc
    if run:
        if str(vanilla_run) == str(run):
            pytest.mark.skip(
                f"Failed the same way as the vanilla msgpack" f" module: {run}"
            )
        else:
            raise run


def test_buffered_base_pack():
    check_buffered_base(pack_func=salt.utils.msgpack.pack, unpack_func=msgpack.unpack)


def test_buffered_base_unpack():
    check_buffered_base(pack_func=msgpack.pack, unpack_func=salt.utils.msgpack.unpack)

"""
Test the MessagePack utility
"""
import inspect
import os
import pprint
import struct
import sys
from io import BytesIO

import salt.utils.msgpack
from salt.ext.six.moves import range
from salt.utils.odict import OrderedDict
from tests.support.unit import TestCase, skipIf

try:
    import msgpack
except ImportError:
    import msgpack_pure as msgpack  # pylint: disable=import-error


# A keyword to pass to tests that use `raw`, which was added in msgpack 0.5.2
raw = {"raw": False} if msgpack.version > (0, 5, 2) else {}


@skipIf(not salt.utils.msgpack.HAS_MSGPACK, "msgpack module required for these tests")
class TestMsgpack(TestCase):
    """
    In msgpack, the following aliases exist:
      load = unpack
      loads = unpackb
      dump = pack
      dumps = packb
    The salt.utils.msgpack versions of these functions are not aliases,
    verify that they pass the same relevant tests from:
        https://github.com/msgpack/msgpack-python/blob/master/test/
    """

    test_data = [
        0,
        1,
        127,
        128,
        255,
        256,
        65535,
        65536,
        4294967295,
        4294967296,
        -1,
        -32,
        -33,
        -128,
        -129,
        -32768,
        -32769,
        -4294967296,
        -4294967297,
        1.0,
        b"",
        b"a",
        b"a" * 31,
        b"a" * 32,
        None,
        True,
        False,
        (),
        ((),),
        ((), None,),
        {None: 0},
        (1 << 23),
    ]

    def test_version(self):
        """
        Verify that the version exists and returns a value in the expected format
        """
        version = salt.utils.msgpack.version
        self.assertTrue(isinstance(version, tuple))
        self.assertGreater(version, (0, 0, 0))

    def test_Packer(self):
        data = os.urandom(1024)
        packer = salt.utils.msgpack.Packer()
        unpacker = msgpack.Unpacker(None)

        packed = packer.pack(data)
        # Sanity Check
        self.assertTrue(packed)
        self.assertNotEqual(data, packed)

        # Reverse the packing and the result should be equivalent to the original data
        unpacker.feed(packed)
        unpacked = msgpack.unpackb(packed)
        self.assertEqual(data, unpacked)

    def test_Unpacker(self):
        data = os.urandom(1024)
        packer = msgpack.Packer()
        unpacker = salt.utils.msgpack.Unpacker(None)

        packed = packer.pack(data)
        # Sanity Check
        self.assertTrue(packed)
        self.assertNotEqual(data, packed)

        # Reverse the packing and the result should be equivalent to the original data
        unpacker.feed(packed)
        unpacked = msgpack.unpackb(packed)
        self.assertEqual(data, unpacked)

    def test_array_size(self):
        sizes = [0, 5, 50, 1000]
        bio = BytesIO()
        packer = salt.utils.msgpack.Packer()
        for size in sizes:
            bio.write(packer.pack_array_header(size))
            for i in range(size):
                bio.write(packer.pack(i))

        bio.seek(0)
        unpacker = salt.utils.msgpack.Unpacker(bio, use_list=True)
        for size in sizes:
            self.assertEqual(unpacker.unpack(), list(range(size)))

    def test_manual_reset(self):
        sizes = [0, 5, 50, 1000]
        packer = salt.utils.msgpack.Packer(autoreset=False)
        for size in sizes:
            packer.pack_array_header(size)
            for i in range(size):
                packer.pack(i)

        bio = BytesIO(packer.bytes())
        unpacker = salt.utils.msgpack.Unpacker(bio, use_list=True)
        for size in sizes:
            self.assertEqual(unpacker.unpack(), list(range(size)))

        packer.reset()
        self.assertEqual(packer.bytes(), b"")

    def test_map_size(self):
        sizes = [0, 5, 50, 1000]
        bio = BytesIO()
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
            self.assertEqual(unpacker.unpack(), {i: i * 2 for i in range(size)})

    def test_max_buffer_size(self):
        """
        Test if max buffer size allows at least 100MiB
        """
        bio = BytesIO()
        bio.write(salt.utils.msgpack.packb("0" * (100 * 1024 * 1024)))
        bio.seek(0)
        unpacker = salt.utils.msgpack.Unpacker(bio)
        raised = False
        try:
            unpacker.unpack()
        except ValueError:
            raised = True
        self.assertFalse(raised)

    def test_exceptions(self):
        # Verify that this exception exists
        self.assertTrue(salt.utils.msgpack.exceptions.PackValueError)
        self.assertTrue(salt.utils.msgpack.exceptions.UnpackValueError)
        self.assertTrue(salt.utils.msgpack.exceptions.PackValueError)
        self.assertTrue(salt.utils.msgpack.exceptions.UnpackValueError)

    def test_function_aliases(self):
        """
        Fail if core functionality from msgpack is missing in the utility
        """

        def sanitized(item):
            if inspect.isfunction(getattr(msgpack, item)):
                # Only check objects that exist in the same file as msgpack
                return inspect.getfile(getattr(msgpack, item)) == inspect.getfile(
                    msgpack
                )

        msgpack_items = {
            x for x in dir(msgpack) if not x.startswith("_") and sanitized(x)
        }
        msgpack_util_items = set(dir(salt.utils.msgpack))
        self.assertFalse(
            msgpack_items - msgpack_util_items,
            "msgpack functions with no alias in `salt.utils.msgpack`",
        )

    def _test_base(self, pack_func, unpack_func):
        """
        In msgpack, 'dumps' is an alias for 'packb' and 'loads' is an alias for 'unpackb'.
        Verify that both salt.utils.msgpack function variations pass the exact same test
        """
        data = os.urandom(1024)

        packed = pack_func(data)
        # Sanity Check
        self.assertTrue(packed)
        self.assertIsInstance(packed, bytes)
        self.assertNotEqual(data, packed)

        # Reverse the packing and the result should be equivalent to the original data
        unpacked = unpack_func(packed)
        self.assertEqual(data, unpacked)

    def _test_buffered_base(self, pack_func, unpack_func):
        data = os.urandom(1024).decode(errors="ignore")
        buffer = BytesIO()
        # Sanity check, we are not borking the BytesIO read function
        self.assertNotEqual(BytesIO.read, buffer.read)
        buffer.read = buffer.getvalue
        pack_func(data, buffer)
        # Sanity Check
        self.assertTrue(buffer.getvalue())
        self.assertIsInstance(buffer.getvalue(), bytes)
        self.assertNotEqual(data, buffer.getvalue())

        # Reverse the packing and the result should be equivalent to the original data
        unpacked = unpack_func(buffer)

        if isinstance(unpacked, bytes):
            unpacked = unpacked.decode()

        self.assertEqual(data, unpacked)

    def test_buffered_base_pack(self):
        self._test_buffered_base(
            pack_func=salt.utils.msgpack.pack, unpack_func=msgpack.unpack
        )

    def test_buffered_base_unpack(self):
        self._test_buffered_base(
            pack_func=msgpack.pack, unpack_func=salt.utils.msgpack.unpack
        )

    def _test_unpack_array_header_from_file(self, pack_func, **kwargs):
        f = BytesIO(pack_func([1, 2, 3, 4]))
        unpacker = salt.utils.msgpack.Unpacker(f)
        self.assertEqual(unpacker.read_array_header(), 4)
        self.assertEqual(unpacker.unpack(), 1)
        self.assertEqual(unpacker.unpack(), 2)
        self.assertEqual(unpacker.unpack(), 3)
        self.assertEqual(unpacker.unpack(), 4)
        self.assertRaises(salt.utils.msgpack.exceptions.OutOfData, unpacker.unpack)

    @skipIf(
        not hasattr(sys, "getrefcount"), "sys.getrefcount() is needed to pass this test"
    )
    def _test_unpacker_hook_refcnt(self, pack_func, **kwargs):
        result = []

        def hook(x):
            result.append(x)
            return x

        basecnt = sys.getrefcount(hook)

        up = salt.utils.msgpack.Unpacker(object_hook=hook, list_hook=hook)

        self.assertGreaterEqual(sys.getrefcount(hook), basecnt + 2)

        up.feed(pack_func([{}]))
        up.feed(pack_func([{}]))
        self.assertEqual(up.unpack(), [{}])
        self.assertEqual(up.unpack(), [{}])
        self.assertEqual(result, [{}, [{}], {}, [{}]])

        del up

        self.assertEqual(sys.getrefcount(hook), basecnt)

    def _test_unpacker_ext_hook(self, pack_func, **kwargs):
        class MyUnpacker(salt.utils.msgpack.Unpacker):
            def __init__(self):
                my_kwargs = {}
                super().__init__(ext_hook=self._hook, **raw)

            def _hook(self, code, data):
                if code == 1:
                    return int(data)
                else:
                    return salt.utils.msgpack.ExtType(code, data)

        unpacker = MyUnpacker()
        unpacker.feed(pack_func({"a": 1}))
        self.assertEqual(unpacker.unpack(), {"a": 1})
        unpacker.feed(pack_func({"a": salt.utils.msgpack.ExtType(1, b"123")}))
        self.assertEqual(unpacker.unpack(), {"a": 123})
        unpacker.feed(pack_func({"a": salt.utils.msgpack.ExtType(2, b"321")}))
        self.assertEqual(
            unpacker.unpack(), {"a": salt.utils.msgpack.ExtType(2, b"321")}
        )

    def _check(
        self, data, pack_func, unpack_func, use_list=False, strict_map_key=False
    ):
        my_kwargs = {}
        if salt.utils.msgpack.version >= (0, 6, 0):
            my_kwargs["strict_map_key"] = strict_map_key
        ret = unpack_func(pack_func(data), use_list=use_list, **my_kwargs)
        self.assertEqual(ret, data)

    def _test_pack_unicode(self, pack_func, unpack_func):
        test_data = ["", "abcd", ["defgh"], "Русский текст"]
        for td in test_data:
            ret = unpack_func(pack_func(td), use_list=True, **raw)
            self.assertEqual(ret, td)
            packer = salt.utils.msgpack.Packer()
            data = packer.pack(td)
            ret = salt.utils.msgpack.Unpacker(
                BytesIO(data), use_list=True, **raw
            ).unpack()
            self.assertEqual(ret, td)

    def _test_pack_bytes(self, pack_func, unpack_func):
        test_data = [
            b"",
            b"abcd",
            (b"defgh",),
        ]
        for td in test_data:
            self._check(td, pack_func, unpack_func)

    def _test_pack_byte_arrays(self, pack_func, unpack_func):
        test_data = [
            bytearray(b""),
            bytearray(b"abcd"),
            (bytearray(b"defgh"),),
        ]
        for td in test_data:
            self._check(td, pack_func, unpack_func)

    @skipIf(sys.version_info < (3, 0), "Python 2 passes invalid surrogates")
    def _test_ignore_unicode_errors(self, pack_func, unpack_func):
        ret = unpack_func(
            pack_func(b"abc\xeddef", use_bin_type=False), unicode_errors="ignore", **raw
        )
        self.assertEqual("abcdef", ret)

    def _test_strict_unicode_unpack(self, pack_func, unpack_func):
        packed = pack_func(b"abc\xeddef", use_bin_type=False)
        self.assertRaises(UnicodeDecodeError, unpack_func, packed, use_list=True, **raw)

    @skipIf(sys.version_info < (3, 0), "Python 2 passes invalid surrogates")
    def _test_ignore_errors_pack(self, pack_func, unpack_func):
        ret = unpack_func(
            pack_func("abc\uDC80\uDCFFdef", use_bin_type=True, unicode_errors="ignore"),
            use_list=True,
            **raw
        )
        self.assertEqual("abcdef", ret)

    def _test_decode_binary(self, pack_func, unpack_func):
        ret = unpack_func(pack_func(b"abc"), use_list=True)
        self.assertEqual(b"abc", ret)

    @skipIf(
        salt.utils.msgpack.version < (0, 2, 2),
        "use_single_float was added in msgpack==0.2.2",
    )
    def _test_pack_float(self, pack_func, **kwargs):
        self.assertEqual(
            b"\xca" + struct.pack(">f", 1.0), pack_func(1.0, use_single_float=True)
        )
        self.assertEqual(
            b"\xcb" + struct.pack(">d", 1.0), pack_func(1.0, use_single_float=False),
        )

    def _test_odict(self, pack_func, unpack_func):
        seq = [(b"one", 1), (b"two", 2), (b"three", 3), (b"four", 4)]

        od = OrderedDict(seq)
        self.assertEqual(dict(seq), unpack_func(pack_func(od), use_list=True))

        def pair_hook(seq):
            return list(seq)

        self.assertEqual(
            seq, unpack_func(pack_func(od), object_pairs_hook=pair_hook, use_list=True)
        )

    def _test_pair_list(self, unpack_func, **kwargs):
        pairlist = [(b"a", 1), (2, b"b"), (b"foo", b"bar")]
        packer = salt.utils.msgpack.Packer()
        packed = packer.pack_map_pairs(pairlist)
        if salt.utils.msgpack.version > (0, 6, 0):
            unpacked = unpack_func(packed, object_pairs_hook=list, strict_map_key=False)
        else:
            unpacked = unpack_func(packed, object_pairs_hook=list)
        self.assertEqual(pairlist, unpacked)

    @skipIf(
        salt.utils.msgpack.version < (0, 6, 0),
        "getbuffer() was added to Packer in msgpack 0.6.0",
    )
    def _test_get_buffer(self, pack_func, **kwargs):
        packer = msgpack.Packer(autoreset=False, use_bin_type=True)
        packer.pack([1, 2])
        strm = BytesIO()
        strm.write(packer.getbuffer())
        written = strm.getvalue()

        expected = pack_func([1, 2], use_bin_type=True)
        self.assertEqual(expected, written)

    @staticmethod
    def no_fail_run(test, *args, **kwargs):
        """
        Run a test without failure and return any exception it raises
        """
        try:
            test(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            return e

    def test_binary_function_compatibility(self):
        functions = [
            {"pack_func": salt.utils.msgpack.packb, "unpack_func": msgpack.unpackb},
            {"pack_func": msgpack.packb, "unpack_func": salt.utils.msgpack.unpackb},
        ]
        # These functions are equivalent but could potentially be overwritten
        if salt.utils.msgpack.dumps is not salt.utils.msgpack.packb:
            functions.append(
                {"pack_func": salt.utils.msgpack.dumps, "unpack_func": msgpack.unpackb}
            )
        if salt.utils.msgpack.loads is not salt.utils.msgpack.unpackb:
            functions.append(
                {"pack_func": msgpack.packb, "unpack_func": salt.utils.msgpack.loads}
            )

        test_funcs = (
            self._test_base,
            self._test_unpack_array_header_from_file,
            self._test_unpacker_hook_refcnt,
            self._test_unpacker_ext_hook,
            self._test_pack_unicode,
            self._test_pack_bytes,
            self._test_pack_byte_arrays,
            self._test_ignore_unicode_errors,
            self._test_strict_unicode_unpack,
            self._test_ignore_errors_pack,
            self._test_decode_binary,
            self._test_pack_float,
            self._test_odict,
            self._test_pair_list,
            self._test_get_buffer,
        )
        errors = {}
        for test_func in test_funcs:
            # Run the test without the salt.utils.msgpack module for comparison
            vanilla_run = self.no_fail_run(
                test_func,
                **{"pack_func": msgpack.packb, "unpack_func": msgpack.unpackb}
            )

            for func_args in functions:
                func_name = (
                    func_args["pack_func"]
                    if func_args["pack_func"].__module__.startswith("salt.utils")
                    else func_args["unpack_func"]
                )
                if hasattr(TestCase, "subTest"):
                    with self.subTest(test=test_func.__name__, func=func_name.__name__):
                        # Run the test with the salt.utils.msgpack module
                        run = self.no_fail_run(test_func, **func_args)
                        # If the vanilla msgpack module errored, then skip if we got the same error
                        if run:
                            if str(vanilla_run) == str(run):
                                self.skipTest(
                                    "Failed the same way as the vanilla msgpack module:\n{}".format(
                                        run
                                    )
                                )
                else:
                    # If subTest isn't available then run the tests collect the errors of all the tests before failing
                    run = self.no_fail_run(test_func, **func_args)
                    if run:
                        # If the vanilla msgpack module errored, then skip if we got the same error
                        if str(vanilla_run) == str(run):
                            self.skipTest(
                                "Test failed the same way the vanilla msgpack module fails:\n{}".format(
                                    run
                                )
                            )
                        else:
                            errors[(test_func.__name__, func_name.__name__)] = run

        if errors:
            self.fail(pprint.pformat(errors))

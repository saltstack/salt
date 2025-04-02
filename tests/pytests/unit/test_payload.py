"""
    tests.unit.payload_test
    ~~~~~~~~~~~~~~~~~~~~~~~
"""

import copy
import datetime
import logging

import zmq

import salt.exceptions
import salt.payload
import salt.utils.msgpack
from salt.defaults import _Constant
from salt.utils import immutabletypes
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)


def assert_no_ordered_dict(data):
    if isinstance(data, OrderedDict):
        raise AssertionError("Found an ordered dictionary")
    if isinstance(data, dict):
        for value in data.values():
            assert_no_ordered_dict(value)
    elif isinstance(data, (list, tuple)):
        for chunk in data:
            assert_no_ordered_dict(chunk)


def test_list_nested_odicts():
    idata = {"pillar": [OrderedDict(environment="dev")]}
    odata = salt.payload.loads(salt.payload.dumps(idata.copy()))
    assert_no_ordered_dict(odata)
    assert idata == odata


def test_datetime_dump_load():
    """
    Check the custom datetime handler can understand itself
    """
    dtvalue = datetime.datetime(2001, 2, 3, 4, 5, 6, 7)
    idata = {dtvalue: dtvalue}
    sdata = salt.payload.dumps(idata.copy())
    odata = salt.payload.loads(sdata)
    assert (
        sdata
        == b"\x81\xc7\x18N20010203T04:05:06.000007\xc7\x18N20010203T04:05:06.000007"
    )
    assert idata == odata


def test_verylong_dump_load():
    """
    Test verylong encoder/decoder
    """
    idata = {"jid": 20180227140750302662}
    sdata = salt.payload.dumps(idata.copy())
    odata = salt.payload.loads(sdata)
    idata["jid"] = "{}".format(idata["jid"])
    assert idata == odata


def test_immutable_dict_dump_load():
    """
    Test immutable dict encoder/decoder
    """
    idata = {"dict": {"key": "value"}}
    sdata = salt.payload.dumps({"dict": immutabletypes.ImmutableDict(idata["dict"])})
    odata = salt.payload.loads(sdata)
    assert idata == odata


def test_immutable_list_dump_load():
    """
    Test immutable list encoder/decoder
    """
    idata = {"list": [1, 2, 3]}
    sdata = salt.payload.dumps({"list": immutabletypes.ImmutableList(idata["list"])})
    odata = salt.payload.loads(sdata)
    assert idata == odata


def test_immutable_set_dump_load():
    """
    Test immutable set encoder/decoder
    """
    idata = {"set": ["red", "green", "blue"]}
    sdata = salt.payload.dumps({"set": immutabletypes.ImmutableSet(idata["set"])})
    odata = salt.payload.loads(sdata)
    assert idata == odata


def test_odict_dump_load():
    """
    Test odict just works. It wasn't until msgpack 0.2.0
    """
    data = OrderedDict()
    data["a"] = "b"
    data["y"] = "z"
    data["j"] = "k"
    data["w"] = "x"
    sdata = salt.payload.dumps({"set": data})
    odata = salt.payload.loads(sdata)
    assert {"set": dict(data)}, odata


def test_mixed_dump_load():
    """
    Test we can handle all exceptions at once
    """
    dtvalue = datetime.datetime(2001, 2, 3, 4, 5, 6, 7)
    od = OrderedDict()
    od["a"] = "b"
    od["y"] = "z"
    od["j"] = "k"
    od["w"] = "x"
    idata = {
        dtvalue: dtvalue,  # datetime
        "jid": 20180227140750302662,  # long int
        "dict": immutabletypes.ImmutableDict({"key": "value"}),  # immutable dict
        "list": immutabletypes.ImmutableList([1, 2, 3]),  # immutable list
        "set": immutabletypes.ImmutableSet(("red", "green", "blue")),  # immutable set
        "odict": od,  # odict
    }
    edata = {
        dtvalue: dtvalue,  # datetime, == input
        "jid": "20180227140750302662",  # string repr of long int
        "dict": {"key": "value"},  # builtin dict
        "list": [1, 2, 3],  # builtin list
        "set": ["red", "green", "blue"],  # builtin set
        "odict": dict(od),  # builtin dict
    }
    sdata = salt.payload.dumps(idata)
    odata = salt.payload.loads(sdata)
    assert edata == odata


def test_recursive_dump_load():
    """
    Test recursive payloads are (mostly) serialized
    """
    data = {"name": "roscivs"}
    data["data"] = data  # Data all the things!
    sdata = salt.payload.dumps(data)
    odata = salt.payload.loads(sdata)
    assert "recursion" in odata["data"].lower()


def test_recursive_dump_load_with_identical_non_recursive_types():
    """
    If identical objects are nested anywhere, they should not be
    marked recursive unless they're one of the types we iterate
    over.
    """
    repeating = "repeating element"
    data = {
        "a": "a",  # Test CPython implementation detail. Short
        "b": "a",  # strings are interned.
        "c": 13,  # So are small numbers.
        "d": 13,
        "fnord": repeating,
        # Let's go for broke and make a crazy nested structure
        "repeating": [
            [[[[{"one": repeating, "two": repeating}], repeating, 13, "a"]]],
            repeating,
            repeating,
            repeating,
        ],
    }
    # We need a nested dictionary to trigger the exception
    data["repeating"][0][0][0].append(data)
    # If we don't deepcopy the data it gets mutated
    sdata = salt.payload.dumps(copy.deepcopy(data))
    odata = salt.payload.loads(sdata)
    # Delete the recursive piece - it's served its purpose, and our
    # other test tests that it's actually marked as recursive.
    del odata["repeating"][0][0][0][-1], data["repeating"][0][0][0][-1]
    assert odata == data


def test_raw_vs_encoding_none():
    """
    Test that we handle the new raw parameter in 5.0.2 correctly based on
    encoding. When encoding is None loads should return bytes
    """
    dtvalue = datetime.datetime(2001, 2, 3, 4, 5, 6, 7)
    idata = {dtvalue: "strval"}
    sdata = salt.payload.dumps(idata.copy())
    odata = salt.payload.loads(sdata, encoding=None)
    assert isinstance(odata[dtvalue], str)


def test_raw_vs_encoding_utf8():
    """
    Test that we handle the new raw parameter in 5.0.2 correctly based on
    encoding. When encoding is utf-8 loads should return unicode
    """
    dtvalue = datetime.datetime(2001, 2, 3, 4, 5, 6, 7)
    idata = {dtvalue: "strval"}
    sdata = salt.payload.dumps(idata.copy())
    odata = salt.payload.loads(sdata, encoding="utf-8")
    assert isinstance(odata[dtvalue], str)


def test_constants():
    """
    That that we handle encoding and decoding of constants.
    """
    constant = _Constant("Foo", "bar")
    sdata = salt.payload.dumps(constant)
    odata = salt.payload.loads(sdata)
    assert odata == constant


def test_package():
    value = salt.utils.msgpack.dumps("test")
    assert salt.payload.package("test") == value


def test_unpackage():
    value = [b"test"]
    packed = salt.utils.msgpack.dumps(value)
    assert salt.payload.unpackage(packed) == value


def test_format_payload():
    expected = salt.utils.msgpack.dumps(
        {"enc": [b"test"], "load": {"kwargs": {"foo": "bar"}}}
    )
    enc = [b"test"]
    kwargs = {"foo": "bar"}
    payload = salt.payload.format_payload(enc=enc, kwargs=kwargs)
    assert payload == expected


def test_SREQ_init():
    req = salt.payload.SREQ(
        "tcp://salt:3434", id_=b"id", serial="msgpack", linger=1, opts=None
    )
    assert req.master == "tcp://salt:3434"
    assert req.id_ == b"id"
    assert req.linger == 1
    assert req.opts is None
    assert isinstance(req.context, zmq.Context)
    assert isinstance(req.poller, zmq.Poller)


def test_SREQ_socket():
    req = salt.payload.SREQ(
        "tcp://salt:3434", id_=b"id", serial="msgpack", linger=1, opts=None
    )
    # socket() is a property that auto creates a socket if a socket is wanted.
    socket = req.socket
    assert isinstance(socket, zmq.Socket)

    req = salt.payload.SREQ(
        "tcp://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:3434",
        id_=b"id",
        serial="msgpack",
        linger=1,
        opts=None,
    )
    # socket() is a property that auto creates a socket if a socket is wanted.
    socket = req.socket
    assert isinstance(socket, zmq.Socket)

    req = salt.payload.SREQ(
        "tcp://salt:3434", id_=None, serial="msgpack", linger=1, opts=None
    )
    # socket() is a property that auto creates a socket if a socket is wanted.
    socket = req.socket
    assert isinstance(socket, zmq.Socket)


def test_SREQ_set_tcp_keepalive():
    opts = {"tcp_keepalive": True}
    req = salt.payload.SREQ(
        "tcp://salt:3434", id_=b"id", serial="msgpack", linger=1, opts=opts
    )
    socket = req.socket
    assert req._socket.getsockopt(zmq.TCP_KEEPALIVE)

    opts = {"tcp_keepalive_idle": 100}
    req = salt.payload.SREQ(
        "tcp://salt:3434", id_=b"id", serial="msgpack", linger=1, opts=opts
    )
    socket = req.socket
    assert req._socket.getsockopt(zmq.TCP_KEEPALIVE_IDLE) == 100

    opts = {"tcp_keepalive_cnt": 100}
    req = salt.payload.SREQ(
        "tcp://salt:3434", id_=b"id", serial="msgpack", linger=1, opts=opts
    )
    socket = req.socket
    assert req._socket.getsockopt(zmq.TCP_KEEPALIVE_CNT) == 100

    opts = {"tcp_keepalive_intvl": 100}
    req = salt.payload.SREQ(
        "tcp://salt:3434", id_=b"id", serial="msgpack", linger=1, opts=opts
    )
    socket = req.socket
    assert req._socket.getsockopt(zmq.TCP_KEEPALIVE_INTVL) == 100

import inspect

import pytest

from salt.exceptions import SaltException
from salt.utils.object_filter import AddressPoint, object_filter, write, write_check


class DumbClass:
    def __init__(self, a, *args):
        self._a = a
        self._args = args

    def __hash__(self):
        return 0

    def a(self):
        return self._a

    def args(self):
        return self._args


class DumbDumb(DumbClass):
    pass


def test_object_filter_int():
    data = [
        1,
        "cats",
        "23",
        24,
        34.2,
        {None: DumbClass(2, 3, "data"), 88: (21, 43, 99)},
    ]
    address_list = object_filter(data, int, True, False)
    assert 8 == len(address_list)
    for data_point, _, supported in address_list:
        assert isinstance(data_point, int)
        assert supported
    address_list = object_filter(data, int, False, False)
    assert 7 == len(address_list)
    for data_point, _, supported in address_list:
        assert isinstance(data_point, int)
        assert supported


def test_object_filter_str_bytes():
    data = {
        "data": b"data",
        "d": frozenset(["c", 1, 2, b"int"]),
        45: [[2, [[[[[(b"bytes", "str", 3.2, None, {"a"})]]]]]]],
    }
    address_list = object_filter(data, (str, bytes), True, False)
    assert 8 == len(address_list)
    for data_point, _, supported in address_list:
        assert isinstance(data_point, (str, bytes))
        assert supported
    address_list = object_filter(data, (str, bytes), False, False)
    assert 6 == len(address_list)
    for data_point, _, supported in address_list:
        assert isinstance(data_point, (str, bytes))
        assert supported


def test_object_filter_dumb():
    data = [
        DumbClass(33),
        None,
        "cats",
        (1, DumbDumb(4), None, complex(23, 1), bytearray(10)),
    ]
    address_list = object_filter(data, DumbClass, True, False)
    assert 2 == len(address_list)
    for data_point, _, supported in address_list:
        assert isinstance(data_point, DumbClass)
        assert supported


def test_object_filter_dumb_dumb():
    data = [
        DumbClass(33),
        None,
        "cats",
        (1, DumbDumb(4), None, complex(23, 1), bytearray(10)),
    ]
    address_list = object_filter(data, DumbDumb, True, False)
    assert 1 == len(address_list)
    for data_point, _, supported in address_list:
        assert isinstance(data_point, DumbDumb)
        assert supported


def test_object_filter_unsupported():
    data = [1, 2, min, DumbDumb, (lambda a: a, b"s", {"len": len, True: False})]
    address_list = object_filter(data, (), True, True)
    assert 4 == len(address_list)
    assert address_list[0][0] is min
    assert address_list[1][0] is DumbDumb
    assert inspect.isfunction(address_list[2][0])
    assert address_list[3][0] is len


def test_object_filter_address():
    data = [[[[{(3,): "", None: 4}]]]]
    address_list = object_filter(data, (int,), True, False)
    assert 2 == len(address_list)
    assert address_list[0][1] == (
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=(3,), key=True, mutable=True),
        AddressPoint(point=0, key=False, mutable=False),
    )
    assert address_list[1][1] == (
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=0, key=False, mutable=True),
        AddressPoint(point=None, key=False, mutable=True),
    )


def test_write_base():
    data = 22
    address = ()
    assert write_check(address) is True
    data = write(b"data", data, address)
    assert data == b"data"


def test_write_simple():
    data = [5, 4, 3, 2, 1]
    address = (AddressPoint(point=3, key=False, mutable=True),)
    assert write_check(address) is True
    data = write("data", data, address)
    assert data[3] == "data"


def test_write_nested():
    data = [5, 4, {"cats": {1, 2, 4, 5, b"data"}}, 1]
    address_list = object_filter(data, (bytes,), True, False)
    assert 1 == len(address_list)
    address = address_list[0][1]
    assert write_check(address)
    data = write("data", data, address)
    assert "data" in data[2]["cats"]
    assert b"data" not in data[2]["cats"]


def test_write_key():
    data = [5, 4, {"cats": {1, 2, 4, 5, b"data"}}, 1]
    address_list = object_filter(data, (str,), True, False)
    assert 1 == len(address_list)
    address = address_list[0][1]
    assert write_check(address)
    data = write(44, data, address)
    assert 44 in data[2]
    assert "cats" not in data[2]


def test_write_obj():
    data = [[DumbClass(23)]]
    address_list = object_filter(data, (int,), True, False)
    assert 1 == len(address_list)
    address = address_list[0][1]
    assert write_check(address)
    data = write("test", data, address)
    assert data[0][0].a() == "test"


def test_bad_write_key():
    data = {DumbClass(1): "data"}
    address_list = object_filter(data, (int,), True, False)
    assert 1 == len(address_list)
    address = address_list[0][1]
    assert write_check(address) is False
    with pytest.raises(SaltException):
        write(44, data, address)


def test_bad_write_immutable():
    data = [(1,)]
    address_list = object_filter(data, (int,), True, False)
    assert 1 == len(address_list)
    address = address_list[0][1]
    assert write_check(address) is False
    with pytest.raises(SaltException):
        write(44, data, address)

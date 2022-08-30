# pylint: disable=pointless-statement,cell-var-from-loop

import functools
import sys

import pytest

from salt._compat import ipaddress


@functools.total_ordering
class _LARGEST:
    """
    Object that is greater than anything (except itself).
    """

    def __eq__(self, other):
        return isinstance(other, _LARGEST)

    def __lt__(self, other):
        return False


@pytest.fixture(scope="module")
def largest():
    return _LARGEST()


@functools.total_ordering
class _SMALLEST:
    """
    Object that is less than anything (except itself).
    """

    def __eq__(self, other):
        return isinstance(other, _SMALLEST)

    def __gt__(self, other):
        return False


@pytest.fixture(scope="module")
def smallest():
    return _SMALLEST()


pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


@pytest.fixture
def v4addr():
    return ipaddress.IPv4Address(1)


@pytest.fixture
def v4net():
    return ipaddress.IPv4Network(1)


@pytest.fixture
def v4intf():
    return ipaddress.IPv4Interface(1)


@pytest.fixture
def v6addr():
    return ipaddress.IPv6Address(1)


@pytest.fixture
def v6net():
    return ipaddress.IPv6Network(1)


@pytest.fixture
def v6intf():
    return ipaddress.IPv6Interface(1)


@pytest.fixture
def v6addr_scoped():
    return ipaddress.IPv6Address("::1%scope")


@pytest.fixture
def v6net_scoped():
    return ipaddress.IPv6Network("::1%scope")


@pytest.fixture
def v6intf_scoped():
    return ipaddress.IPv6Interface("::1%scope")


@pytest.fixture
def v4_addresses(v4addr, v4intf):
    return [v4addr, v4intf]


@pytest.fixture
def v4_objects(v4_addresses, v4net):
    return v4_addresses + [v4net]


@pytest.fixture
def v6_addresses(v6addr, v6intf):
    return [v6addr, v6intf]


@pytest.fixture
def v6_objects(v6_addresses, v6net):
    return v6_addresses + [v6net]


@pytest.fixture
def v6_scoped_addresses(v6addr_scoped, v6intf_scoped):
    return [v6addr_scoped, v6intf_scoped]


@pytest.fixture
def v6_scoped_objects(v6_scoped_addresses, v6net_scoped):
    return v6_scoped_addresses + [v6net_scoped]


@pytest.fixture
def objects(v4_objects, v6_objects):
    return v4_objects + v6_objects


@pytest.fixture
def objects_with_scoped(objects, v6_scoped_objects):
    return objects + v6_scoped_objects


@pytest.fixture
def v4addr2():
    return ipaddress.IPv4Address(2)


@pytest.fixture
def v4net2():
    return ipaddress.IPv4Network(2)


@pytest.fixture
def v4intf2():
    return ipaddress.IPv4Interface(2)


@pytest.fixture
def v6addr2():
    return ipaddress.IPv6Address(2)


@pytest.fixture
def v6net2():
    return ipaddress.IPv6Network(2)


@pytest.fixture
def v6intf2():
    return ipaddress.IPv6Interface(2)


@pytest.fixture
def v6addr2_scoped():
    return ipaddress.IPv6Address("::2%scope")


@pytest.fixture
def v6net2_scoped():
    return ipaddress.IPv6Network("::2%scope")


@pytest.fixture
def v6intf2_scoped():
    return ipaddress.IPv6Interface("::2%scope")


def test_foreign_type_equality(objects_with_scoped):
    # __eq__ should never raise TypeError directly
    other = object()
    for obj in objects_with_scoped:
        assert obj != other
        assert (obj == other) is False
        assert obj.__eq__(other) == NotImplemented
        assert obj.__ne__(other) == NotImplemented


def test_mixed_type_equality(objects):
    # Ensure none of the internal objects accidentally
    # expose the right set of attributes to become "equal"
    for lhs in objects:
        for rhs in objects:
            if lhs is rhs:
                continue
            assert lhs != rhs


def test_scoped_ipv6_equality(v6_objects, v6_scoped_objects):
    for lhs, rhs in zip(v6_objects, v6_scoped_objects):
        assert lhs != rhs


def test_v4_with_v6_scoped_equality(v4_objects, v6_scoped_objects):
    for lhs in v4_objects:
        for rhs in v6_scoped_objects:
            assert lhs != rhs


def test_same_type_equality(objects_with_scoped):
    for obj in objects_with_scoped:
        assert obj == obj
        assert obj <= obj
        assert obj >= obj


def test_same_type_ordering(
    v4addr,
    v4addr2,
    v4net,
    v4net2,
    v4intf,
    v4intf2,
    v6addr,
    v6addr2,
    v6net,
    v6net2,
    v6intf,
    v6intf2,
    v6addr_scoped,
    v6addr2_scoped,
    v6net_scoped,
    v6net2_scoped,
    v6intf_scoped,
    v6intf2_scoped,
):
    for lhs, rhs in (
        (v4addr, v4addr2),
        (v4net, v4net2),
        (v4intf, v4intf2),
        (v6addr, v6addr2),
        (v6net, v6net2),
        (v6intf, v6intf2),
        (v6addr_scoped, v6addr2_scoped),
        (v6net_scoped, v6net2_scoped),
        (v6intf_scoped, v6intf2_scoped),
    ):
        assert lhs != rhs
        assert lhs < rhs
        assert lhs <= rhs
        assert rhs > lhs
        assert rhs > lhs
        assert (lhs > rhs) is False
        assert (rhs < lhs) is False
        assert (lhs >= rhs) is False
        assert (rhs <= lhs) is False


def test_containment(
    v4_addresses,
    v4net,
    v6_addresses,
    v6_scoped_addresses,
    v6net,
    v6net_scoped,
    v6_scoped_objects,
    v4_objects,
    v6_objects,
):
    for obj in v4_addresses:
        assert obj in v4net
    for obj in v6_addresses + v6_scoped_addresses:
        assert obj in v6net
    for obj in v6_addresses + v6_scoped_addresses:
        assert obj in v6net_scoped

    for obj in v4_objects + [v6net, v6net_scoped]:
        assert obj not in v6net
    for obj in v4_objects + [v6net, v6net_scoped]:
        assert obj not in v6net_scoped
    for obj in v6_objects + v6_scoped_objects + [v4net]:
        assert obj not in v4net


def test_mixed_type_ordering(objects_with_scoped):
    for lhs in objects_with_scoped:
        for rhs in objects_with_scoped:
            if isinstance(lhs, type(rhs)) or isinstance(rhs, type(lhs)):
                continue
            pytest.raises(TypeError, lambda: lhs < rhs)
            pytest.raises(TypeError, lambda: lhs > rhs)
            pytest.raises(TypeError, lambda: lhs <= rhs)
            pytest.raises(TypeError, lambda: lhs >= rhs)


def test_foreign_type_ordering(objects_with_scoped, largest, smallest):
    other = object()
    for obj in objects_with_scoped:
        with pytest.raises(TypeError):
            obj < other
        with pytest.raises(TypeError):
            obj > other
        with pytest.raises(TypeError):
            obj <= other
        with pytest.raises(TypeError):
            obj >= other
        assert (obj < largest) is True
        assert (obj > largest) is False
        assert (obj <= largest) is True
        assert (obj >= largest) is False
        assert (obj < smallest) is False
        assert (obj > smallest) is True
        assert (obj <= smallest) is False
        assert (obj >= smallest) is True


def test_mixed_type_key(
    v4addr,
    v4net,
    v4intf,
    v6addr,
    v6net,
    v6intf,
    v6addr_scoped,
    v6net_scoped,
    v6intf_scoped,
    v4_objects,
    v6_objects,
    v6_scoped_objects,
):
    # with get_mixed_type_key, you can sort addresses and network.
    v4_ordered = [v4addr, v4net, v4intf]
    v6_ordered = [v6addr, v6net, v6intf]
    v6_scoped_ordered = [v6addr_scoped, v6net_scoped, v6intf_scoped]
    assert v4_ordered == sorted(v4_objects, key=ipaddress.get_mixed_type_key)
    assert v6_ordered == sorted(v6_objects, key=ipaddress.get_mixed_type_key)
    assert v6_scoped_ordered == sorted(
        v6_scoped_objects, key=ipaddress.get_mixed_type_key
    )
    assert v4_ordered + v6_scoped_ordered == sorted(
        v4_objects + v6_scoped_objects,
        key=ipaddress.get_mixed_type_key,
    )
    assert NotImplemented == ipaddress.get_mixed_type_key(object)


def test_incompatible_versions():
    # These should always raise TypeError
    v4addr = ipaddress.ip_address("1.1.1.1")
    v4net = ipaddress.ip_network("1.1.1.1")
    v6addr = ipaddress.ip_address("::1")
    v6net = ipaddress.ip_network("::1")
    v6addr_scoped = ipaddress.ip_address("::1%scope")
    v6net_scoped = ipaddress.ip_network("::1%scope")

    pytest.raises(TypeError, v4addr.__lt__, v6addr)
    pytest.raises(TypeError, v4addr.__gt__, v6addr)
    pytest.raises(TypeError, v4net.__lt__, v6net)
    pytest.raises(TypeError, v4net.__gt__, v6net)

    pytest.raises(TypeError, v6addr.__lt__, v4addr)
    pytest.raises(TypeError, v6addr.__gt__, v4addr)
    pytest.raises(TypeError, v6net.__lt__, v4net)
    pytest.raises(TypeError, v6net.__gt__, v4net)

    pytest.raises(TypeError, v4addr.__lt__, v6addr_scoped)
    pytest.raises(TypeError, v4addr.__gt__, v6addr_scoped)
    pytest.raises(TypeError, v4net.__lt__, v6net_scoped)
    pytest.raises(TypeError, v4net.__gt__, v6net_scoped)

    pytest.raises(TypeError, v6addr_scoped.__lt__, v4addr)
    pytest.raises(TypeError, v6addr_scoped.__gt__, v4addr)
    pytest.raises(TypeError, v6net_scoped.__lt__, v4net)
    pytest.raises(TypeError, v6net_scoped.__gt__, v4net)

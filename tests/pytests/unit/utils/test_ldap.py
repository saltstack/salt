import random

import pytest

from salt.utils.ldap import AttributeValueSet, LDAPError


def test_attribute_value_set_empty():
    assert len(AttributeValueSet("attr")) == 0


def test_attribute_value_set_no_duplicates():
    assert list(AttributeValueSet("attr", ["a", "a"])) == ["a"]


def test_attribute_value_set_ordered():
    # Filter the values through a set to avoid duplicates.
    v = list({str(random.getrandbits(32)) for x in range(100)})
    assert len(v) > 90
    # Avoid unintended correlation with set()'s iteration order.
    random.shuffle(v)
    assert list(AttributeValueSet("attr", v)) == v


def test_attribute_value_set_eq():
    s = AttributeValueSet("attr", ["a", "b"])
    assert s is not None
    assert s != []
    assert s != AttributeValueSet("attr")
    assert s != AttributeValueSet("attr", ["x", "y"])
    assert s == s
    assert s == ["a", "b"]
    assert s == {"a", "b"}
    assert s == AttributeValueSet("attr", ["a", "b"])


def test_attribute_value_set_eq_unordered():
    s = AttributeValueSet("attr", ["a", "b"])
    assert s == ["b", "a"]
    assert s == {"b", "a"}
    assert s == AttributeValueSet("attr", ["b", "a"])


# attr: Attribute Name.
# input: Input value.
# v: Wanted stored value.
# vx: Wanted encoded value.
@pytest.mark.parametrize(
    "attr,input,v,vx",
    [
        # str inputs are stored as-is.
        ("attr", "🚀", "🚀", b"\xf0\x9f\x9a\x80"),
        ("unicodePwd", "🚀", "🚀", b'"\x00=\xd8\x80\xde"\x00'),
        # bytes inputs that can be decoded are decoded.
        ("attr", b"\xf0\x9f\x9a\x80", "🚀", b"\xf0\x9f\x9a\x80"),
        ("unicodePwd", b'"\x00=\xd8\x80\xde"\x00', "🚀", b'"\x00=\xd8\x80\xde"\x00'),
        # bytes inputs that can't be decoded are stored as-is.
        ("attr", b"\x80", b"\x80", b"\x80"),
        ("unicodePwd", b"x", b"x", b"x"),
        ("unicodePwd", b'"x"', b'"x"', b'"x"'),  # Not utf-16-le encoded.
        ("unicodePwd", b"x\x00", b"x\x00", b"x\x00"),  # Missing double quotes.
        # Non-bytes, non-str inputs.
        ("attr", [], "", b""),
        ("attr", (), "", b""),
        ("attr", [112], "p", b"p"),
        ("attr", [128], b"\x80", b"\x80"),
        ("attr", bytearray(b"p"), "p", b"p"),
        ("attr", memoryview(b"p"), "p", b"p"),
    ],
)
def test_attribute_value_set_encode_decode(attr, input, v, vx):
    s = AttributeValueSet(attr, [input])
    assert v in s
    assert vx in s
    assert s == [v]
    assert s == [vx]
    assert list(s) == [v]
    assert s.encode() == [vx]


def test_ldap_error():
    cause = RuntimeError("cause")
    err = LDAPError("foo", cause)
    assert isinstance(err, Exception)
    assert err.cause is cause
    assert "foo" in str(err)

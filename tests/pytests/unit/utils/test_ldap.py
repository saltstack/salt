import random

from salt.utils.ldap import AttributeValueSet, LDAPError


def test_attribute_value_set_empty():
    assert len(AttributeValueSet()) == 0


def test_attribute_value_set_no_duplicates():
    assert list(AttributeValueSet(["a", "a"])) == ["a"]


def test_attribute_value_set_ordered():
    # Filter the values through a set to avoid duplicates.
    v = list({str(random.getrandbits(32)).encode() for x in range(100)})
    assert len(v) > 90
    # Avoid unintended correlation with set()'s iteration order.
    random.shuffle(v)
    assert list(AttributeValueSet(v)) == v


def test_attribute_value_set_eq():
    s = AttributeValueSet(["a", "b"])
    assert s is not None
    assert s != []
    assert s != AttributeValueSet()
    assert s != AttributeValueSet(["x", "y"])
    assert s == s
    assert s == ["a", "b"]
    assert s == {"a", "b"}
    assert s == AttributeValueSet(["a", "b"])


def test_attribute_value_set_eq_unordered():
    s = AttributeValueSet(["a", "b"])
    assert s == ["b", "a"]
    assert s == {"b", "a"}
    assert s == AttributeValueSet(["b", "a"])


def test_ldap_error():
    cause = RuntimeError("cause")
    err = LDAPError("foo", cause)
    assert isinstance(err, Exception)
    assert err.cause is cause
    assert "foo" in str(err)

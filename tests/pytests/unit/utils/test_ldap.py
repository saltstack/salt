from salt.utils.ldap import LDAPError


def test_ldap_error():
    cause = RuntimeError("cause")
    err = LDAPError("foo", cause)
    assert isinstance(err, Exception)
    assert err.cause is cause
    assert "foo" in str(err)

import pytest
import salt.modules.postgres as postgres

# 'md5' + md5('password' + 'username')
md5_pw = "md55a231fcdb710d73268c4f44283487ba2"

scram_pw = (
    "SCRAM-SHA-256$4096:wLr5nqC+3F+r7FdQPnB+nA==$"
    "0hn08ZdX8kirGaL4TM0j13digH9Wl365OOzCtAuF2pE=:"
    "LzAh/MGUdjYkdbDzcOKpfGwa3WwPUsyGcY+TEnSpcto="
)


def idfn(val):
    if val == md5_pw:
        return "md5_pw"
    if val == scram_pw:
        return "scram_pw"


@pytest.mark.parametrize(
    "role,password,verifier,method,result",
    [
        ("username", "password", md5_pw, "md5", True),
        ("another", "password", md5_pw, "md5", False),
        ("username", "another", md5_pw, "md5", False),
        ("username", md5_pw, md5_pw, "md5", True),
        ("username", "md5another", md5_pw, "md5", False),
        ("username", "password", md5_pw, True, True),
        ("another", "password", md5_pw, True, False),
        ("username", "another", md5_pw, True, False),
        ("username", md5_pw, md5_pw, True, True),
        ("username", "md5another", md5_pw, True, False),
        (None, "password", scram_pw, "scram-sha-256", True),
        (None, "another", scram_pw, "scram-sha-256", False),
        (None, scram_pw, scram_pw, "scram-sha-256", True),
        (None, "SCRAM-SHA-256$4096:AAAA$AAAA:AAAA", scram_pw, "scram-sha-256", False),
        (None, "SCRAM-SHA-256$foo", scram_pw, "scram-sha-256", False),
        (None, "password", "password", False, True),
        (None, "another", "password", False, False),
        (None, "password", "password", "foo", False),
        ("username", "password", md5_pw, "scram-sha-256", False),
        ("username", "password", scram_pw, "md5", False),
        # Code does not currently check role of pre-hashed md5 passwords
        pytest.param("another", md5_pw, md5_pw, "md5", False, marks=pytest.mark.xfail),
    ],
    ids=idfn,
)
def test_verify_password(role, password, verifier, method, result):
    assert postgres._verify_password(role, password, verifier, method) == result

from threading import Thread

from salt.utils.redact import redact


def target():
    pass


def test_redact_max_recursion_error():
    big_list = []
    big_list_child = big_list
    for _ in range(2000):
        child = []
        big_list_child.append(child)
        big_list_child = child
    big_list_child.append("cats")
    data = redact(big_list, ("cats",))
    assert data == "REDACTED-RecursionError"


def test_redact_type_error():
    data = [Thread(target=target), "cats"]
    data = redact(data, ("cats",))
    assert data == "REDACTED-TypeError"


def test_redact_defaults_simple():
    data = ["-----BEGIN RSA PRIVATE KEY-----", b"-----BEGIN PGP PRIVATE KEY-----"]
    data = redact(data)
    assert data == ["REDACTED", b"REDACTED"]


def test_redact_defaults_nested():
    data = [
        1,
        2,
        "cats",
        {
            "asdklfjasdfkj;l-----BEGIN RSA PRIVATE KEY-----23784095234095": [
                33,
                b"489032750-----BEGIN PGP PRIVATE KEY-----2345234523523452345",
            ],
            45: 66,
        },
    ]
    data = redact(data)
    assert data == [1, 2, "cats", {"REDACTED": [33, b"REDACTED"], 45: 66}]


def test_redact_tuple():
    data = [1, (1, 2, "cats", 5)]
    data = redact(data, ("cats",))
    assert data == [1, "REDACTED"]


def test_redact_frozenset():
    data = [1, frozenset((1, 2, b"cats", 5))]
    data = redact(data, ("cats",))
    assert data == [1, "REDACTED"]


def test_redact_key():
    data = {(1, (2, "cats")): None, "cats": 44, 5: True}
    data = redact(data, ("cats",))
    assert data == {"REDACTED": 44, 5: True}

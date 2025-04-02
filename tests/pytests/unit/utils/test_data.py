"""
Tests for salt.utils.data
"""

import builtins
import logging

import pytest

import salt.utils.data
import salt.utils.stringutils
from salt.exceptions import SaltException
from salt.utils.odict import OrderedDict as SaltOrderedDict
from tests.support.mock import patch
from tests.support.unit import LOREM_IPSUM

log = logging.getLogger(__name__)


def _b(x):
    return x.encode("utf-8")


def _s(x):
    return salt.utils.stringutils.to_str(x, normalize=True)


@pytest.fixture
def get_BYTES():
    # Some randomized data that will not decode
    return b"1\x814\x10"


@pytest.fixture
def get_EGGS():
    # This is an example of a unicode string with й constructed using two separate
    # code points. Do not modify it.
    return "\u044f\u0438\u0306\u0446\u0430"


@pytest.fixture
def get_test_data(get_BYTES, get_EGGS):
    return [
        "unicode_str",
        _b("питон"),
        123,
        456.789,
        True,
        False,
        None,
        get_EGGS,
        get_BYTES,
        [123, 456.789, _b("спам"), True, False, None, get_EGGS, get_BYTES],
        (987, 654.321, _b("яйца"), get_EGGS, None, (True, get_EGGS, get_BYTES)),
        {
            _b("str_key"): _b("str_val"),
            None: True,
            123: 456.789,
            get_EGGS: get_BYTES,
            _b("subdict"): {
                "unicode_key": get_EGGS,
                _b("tuple"): (123, "hello", _b("world"), True, get_EGGS, get_BYTES),
                _b("list"): [456, _b("спам"), False, get_EGGS, get_BYTES],
            },
        },
        SaltOrderedDict([(_b("foo"), "bar"), (123, 456), (get_EGGS, get_BYTES)]),
    ]


def test_sorted_ignorecase():
    test_list = ["foo", "Foo", "bar", "Bar"]
    expected_list = ["bar", "Bar", "foo", "Foo"]
    assert salt.utils.data.sorted_ignorecase(test_list) == expected_list


def test_mysql_to_dict():
    test_mysql_output = [
        "+----+------+-----------+------+---------+------+-------+------------------+",
        "| Id | User | Host      | db   | Command | Time | State | Info         "
        "    |",
        "+----+------+-----------+------+---------+------+-------+------------------+",
        "|  7 | root | localhost | NULL | Query   |    0 | init  | show"
        " processlist |",
        "+----+------+-----------+------+---------+------+-------+------------------+",
    ]

    ret = salt.utils.data.mysql_to_dict(test_mysql_output, "Info")
    expected_dict = {
        "show processlist": {
            "Info": "show processlist",
            "db": "NULL",
            "State": "init",
            "Host": "localhost",
            "Command": "Query",
            "User": "root",
            "Time": 0,
            "Id": 7,
        }
    }
    assert ret == expected_dict


def test_subdict_match():
    test_two_level_dict = {"foo": {"bar": "baz"}}
    test_two_level_comb_dict = {"foo": {"bar": "baz:woz"}}
    test_two_level_dict_and_list = {
        "abc": ["def", "ghi", {"lorem": {"ipsum": [{"dolor": "sit"}]}}],
    }
    test_three_level_dict = {"a": {"b": {"c": "v"}}}

    assert salt.utils.data.subdict_match(test_two_level_dict, "foo:bar:baz")
    # In test_two_level_comb_dict, 'foo:bar' corresponds to 'baz:woz', not
    # 'baz'. This match should return False.
    assert not salt.utils.data.subdict_match(test_two_level_comb_dict, "foo:bar:baz")
    # This tests matching with the delimiter in the value part (in other
    # words, that the path 'foo:bar' corresponds to the string 'baz:woz').
    assert salt.utils.data.subdict_match(test_two_level_comb_dict, "foo:bar:baz:woz")
    # This would match if test_two_level_comb_dict['foo']['bar'] was equal
    # to 'baz:woz:wiz', or if there was more deep nesting. But it does not,
    # so this should return False.
    assert not salt.utils.data.subdict_match(
        test_two_level_comb_dict, "foo:bar:baz:woz:wiz"
    )
    # This tests for cases when a key path corresponds to a list. The
    # value part 'ghi' should be successfully matched as it is a member of
    # the list corresponding to key path 'abc'. It is somewhat a
    # duplication of a test within test_traverse_dict_and_list, but
    # salt.utils.data.subdict_match() does more than just invoke
    # salt.utils.traverse_list_and_dict() so this particular assertion is a
    # sanity check.
    assert salt.utils.data.subdict_match(test_two_level_dict_and_list, "abc:ghi")
    # This tests the use case of a dict embedded in a list, embedded in a
    # list, embedded in a dict. This is a rather absurd case, but it
    # confirms that match recursion works properly.
    assert salt.utils.data.subdict_match(
        test_two_level_dict_and_list, "abc:lorem:ipsum:dolor:sit"
    )
    # Test four level dict match for reference
    assert salt.utils.data.subdict_match(test_three_level_dict, "a:b:c:v")
    # Test regression in 2015.8 where 'a:c:v' would match 'a:b:c:v'
    assert not salt.utils.data.subdict_match(test_three_level_dict, "a:c:v")
    # Test wildcard match
    assert salt.utils.data.subdict_match(test_three_level_dict, "a:*:c:v")


@pytest.mark.parametrize(
    "wildcard",
    [
        ("*:*:*:*"),
        ("a:*:*:*"),
        ("a:b:*:*"),
        ("a:b:ç:*"),
        ("a:b:*:d"),
        ("a:*:ç:d"),
        ("*:b:ç:d"),
        ("*:*:ç:d"),
        ("*:*:*:d"),
        ("a:*:*:d"),
        ("a:b:*:ef*"),
        ("a:b:*:g*"),
        ("a:b:*:j:*"),
        ("a:b:*:j:k"),
        ("a:b:*:*:k"),
        ("a:b:*:*:*"),
    ],
)
def test_subdict_match_with_wildcards(wildcard):
    """
    Tests subdict matching when wildcards are used in the expression
    """
    data = {"a": {"b": {"ç": "d", "é": ["eff", "gee", "8ch"], "ĩ": {"j": "k"}}}}
    assert salt.utils.data.subdict_match(data, wildcard)


def test_traverse_dict():
    test_two_level_dict = {"foo": {"bar": "baz"}}

    assert {"not_found": "nope"} == salt.utils.data.traverse_dict(
        test_two_level_dict, "foo:bar:baz", {"not_found": "nope"}
    )
    assert "baz" == salt.utils.data.traverse_dict(
        test_two_level_dict, "foo:bar", {"not_found": "not_found"}
    )


def test_traverse_dict_and_list():
    test_two_level_dict = {"foo": {"bar": "baz"}}
    test_two_level_dict_and_list = {
        "foo": ["bar", "baz", {"lorem": {"ipsum": [{"dolor": "sit"}]}}]
    }

    # Check traversing too far: salt.utils.data.traverse_dict_and_list() returns
    # the value corresponding to a given key path, and baz is a value
    # corresponding to the key path foo:bar.
    assert {"not_found": "nope"} == salt.utils.data.traverse_dict_and_list(
        test_two_level_dict, "foo:bar:baz", {"not_found": "nope"}
    )
    # Now check to ensure that foo:bar corresponds to baz
    assert "baz" == salt.utils.data.traverse_dict_and_list(
        test_two_level_dict, "foo:bar", {"not_found": "not_found"}
    )
    # Check traversing too far
    assert {"not_found": "nope"} == salt.utils.data.traverse_dict_and_list(
        test_two_level_dict_and_list, "foo:bar", {"not_found": "nope"}
    )
    # Check index 1 (2nd element) of list corresponding to path 'foo'
    assert "baz" == salt.utils.data.traverse_dict_and_list(
        test_two_level_dict_and_list, "foo:1", {"not_found": "not_found"}
    )
    # Traverse a couple times into dicts embedded in lists
    assert "sit" == salt.utils.data.traverse_dict_and_list(
        test_two_level_dict_and_list,
        "foo:lorem:ipsum:dolor",
        {"not_found": "not_found"},
    )

    # Traverse and match integer key in a nested dict
    # https://github.com/saltstack/salt/issues/56444
    assert "it worked" == salt.utils.data.traverse_dict_and_list(
        {"foo": {1234: "it worked"}},
        "foo:1234",
        "it didn't work",
    )
    # Make sure that we properly return the default value when the initial
    # attempt fails and YAML-loading the target key doesn't change its
    # value.
    assert "default" == salt.utils.data.traverse_dict_and_list(
        {"foo": {"baz": "didn't work"}},
        "foo:bar",
        "default",
    )


def test_issue_39709():
    test_two_level_dict_and_list = {
        "foo": ["bar", "baz", {"lorem": {"ipsum": [{"dolor": "sit"}]}}]
    }

    assert "sit" == salt.utils.data.traverse_dict_and_list(
        test_two_level_dict_and_list,
        ["foo", "lorem", "ipsum", "dolor"],
        {"not_found": "not_found"},
    )


def test_compare_dicts():
    ret = salt.utils.data.compare_dicts(old={"foo": "bar"}, new={"foo": "bar"})
    assert ret == {}

    ret = salt.utils.data.compare_dicts(old={"foo": "bar"}, new={"foo": "woz"})
    expected_ret = {"foo": {"new": "woz", "old": "bar"}}
    assert ret == expected_ret


def test_compare_lists_no_change():
    ret = salt.utils.data.compare_lists(
        old=[1, 2, 3, "a", "b", "c"], new=[1, 2, 3, "a", "b", "c"]
    )
    expected = {}
    assert ret == expected


def test_compare_lists_changes():
    ret = salt.utils.data.compare_lists(
        old=[1, 2, 3, "a", "b", "c"], new=[1, 2, 4, "x", "y", "z"]
    )
    expected = {"new": [4, "x", "y", "z"], "old": [3, "a", "b", "c"]}
    assert ret == expected


def test_compare_lists_changes_new():
    ret = salt.utils.data.compare_lists(old=[1, 2, 3], new=[1, 2, 3, "x", "y", "z"])
    expected = {"new": ["x", "y", "z"]}
    assert ret == expected


def test_compare_lists_changes_old():
    ret = salt.utils.data.compare_lists(old=[1, 2, 3, "a", "b", "c"], new=[1, 2, 3])
    expected = {"old": ["a", "b", "c"]}
    assert ret == expected


def test_decode(get_test_data, get_BYTES, get_EGGS):
    """
    Companion to test_decode_to_str, they should both be kept up-to-date
    with one another.

    NOTE: This uses the lambda "_b" defined above in the global scope,
    which encodes a string to a bytestring, assuming utf-8.
    """
    expected = [
        "unicode_str",
        "питон",
        123,
        456.789,
        True,
        False,
        None,
        "яйца",
        get_BYTES,
        [123, 456.789, "спам", True, False, None, "яйца", get_BYTES],
        (987, 654.321, "яйца", "яйца", None, (True, "яйца", get_BYTES)),
        {
            "str_key": "str_val",
            None: True,
            123: 456.789,
            "яйца": get_BYTES,
            "subdict": {
                "unicode_key": "яйца",
                "tuple": (123, "hello", "world", True, "яйца", get_BYTES),
                "list": [456, "спам", False, "яйца", get_BYTES],
            },
        },
        SaltOrderedDict([("foo", "bar"), (123, 456), ("яйца", get_BYTES)]),
    ]

    ret = salt.utils.data.decode(
        get_test_data,
        keep=True,
        normalize=True,
        preserve_dict_class=True,
        preserve_tuples=True,
    )
    assert ret == expected

    # The binary data in the data structure should fail to decode, even
    # using the fallback, and raise an exception.
    pytest.raises(
        UnicodeDecodeError,
        salt.utils.data.decode,
        get_test_data,
        keep=False,
        normalize=True,
        preserve_dict_class=True,
        preserve_tuples=True,
    )

    # Now munge the expected data so that we get what we would expect if we
    # disable preservation of dict class and tuples
    expected[10] = [987, 654.321, "яйца", "яйца", None, [True, "яйца", get_BYTES]]
    expected[11]["subdict"]["tuple"] = [123, "hello", "world", True, "яйца", get_BYTES]
    expected[12] = {"foo": "bar", 123: 456, "яйца": get_BYTES}

    ret = salt.utils.data.decode(
        get_test_data,
        keep=True,
        normalize=True,
        preserve_dict_class=False,
        preserve_tuples=False,
    )
    assert ret == expected

    # Now test single non-string, non-data-structure items, these should
    # return the same value when passed to this function
    for item in (123, 4.56, True, False, None):
        log.debug("Testing decode of %s", item)
        assert salt.utils.data.decode(item) == item

    # Test single strings (not in a data structure)
    assert salt.utils.data.decode("foo") == "foo"
    assert salt.utils.data.decode(_b("bar")) == "bar"
    assert salt.utils.data.decode(get_EGGS, normalize=True) == "яйца"
    assert salt.utils.data.decode(get_EGGS, normalize=False) == get_EGGS

    # Test binary blob
    assert salt.utils.data.decode(get_BYTES, keep=True) == get_BYTES
    pytest.raises(UnicodeDecodeError, salt.utils.data.decode, get_BYTES, keep=False)


def test_circular_refs_dicts():
    test_dict = {"key": "value", "type": "test1"}
    test_dict["self"] = test_dict
    ret = salt.utils.data._remove_circular_refs(ob=test_dict)
    assert ret == {"key": "value", "type": "test1", "self": None}


def test_circular_refs_lists():
    test_list = {
        "foo": [],
    }
    test_list["foo"].append((test_list,))
    ret = salt.utils.data._remove_circular_refs(ob=test_list)
    assert ret == {"foo": [(None,)]}


def test_circular_refs_tuple():
    test_dup = {"foo": "string 1", "bar": "string 1", "ham": 1, "spam": 1}
    ret = salt.utils.data._remove_circular_refs(ob=test_dup)
    assert ret == {"foo": "string 1", "bar": "string 1", "ham": 1, "spam": 1}


def test_decode_to_str(get_test_data, get_BYTES):
    """
    Companion to test_decode, they should both be kept up-to-date with one
    another.

    NOTE: This uses the lambda "_s" defined above in the global scope,
    which converts the string/bytestring to a str type.
    """
    expected = [
        _s("unicode_str"),
        _s("питон"),
        123,
        456.789,
        True,
        False,
        None,
        _s("яйца"),
        get_BYTES,
        [123, 456.789, _s("спам"), True, False, None, _s("яйца"), get_BYTES],
        (987, 654.321, _s("яйца"), _s("яйца"), None, (True, _s("яйца"), get_BYTES)),
        {
            _s("str_key"): _s("str_val"),
            None: True,
            123: 456.789,
            _s("яйца"): get_BYTES,
            _s("subdict"): {
                _s("unicode_key"): _s("яйца"),
                _s("tuple"): (
                    123,
                    _s("hello"),
                    _s("world"),
                    True,
                    _s("яйца"),
                    get_BYTES,
                ),
                _s("list"): [456, _s("спам"), False, _s("яйца"), get_BYTES],
            },
        },
        SaltOrderedDict([(_s("foo"), _s("bar")), (123, 456), (_s("яйца"), get_BYTES)]),
    ]

    ret = salt.utils.data.decode(
        get_test_data,
        keep=True,
        normalize=True,
        preserve_dict_class=True,
        preserve_tuples=True,
        to_str=True,
    )
    assert ret == expected

    # The binary data in the data structure should fail to decode, even
    # using the fallback, and raise an exception.
    pytest.raises(
        UnicodeDecodeError,
        salt.utils.data.decode,
        get_test_data,
        keep=False,
        normalize=True,
        preserve_dict_class=True,
        preserve_tuples=True,
        to_str=True,
    )

    # Now munge the expected data so that we get what we would expect if we
    # disable preservation of dict class and tuples
    expected[10] = [
        987,
        654.321,
        _s("яйца"),
        _s("яйца"),
        None,
        [True, _s("яйца"), get_BYTES],
    ]
    expected[11][_s("subdict")][_s("tuple")] = [
        123,
        _s("hello"),
        _s("world"),
        True,
        _s("яйца"),
        get_BYTES,
    ]
    expected[12] = {_s("foo"): _s("bar"), 123: 456, _s("яйца"): get_BYTES}

    ret = salt.utils.data.decode(
        get_test_data,
        keep=True,
        normalize=True,
        preserve_dict_class=False,
        preserve_tuples=False,
        to_str=True,
    )
    assert ret == expected

    # Now test single non-string, non-data-structure items, these should
    # return the same value when passed to this function
    for item in (123, 4.56, True, False, None):
        log.debug("Testing decode of %s", item)
        assert salt.utils.data.decode(item, to_str=True) == item

    # Test single strings (not in a data structure)
    assert salt.utils.data.decode("foo", to_str=True) == _s("foo")
    assert salt.utils.data.decode(_b("bar"), to_str=True) == _s("bar")

    # Test binary blob
    assert salt.utils.data.decode(get_BYTES, keep=True, to_str=True) == get_BYTES
    pytest.raises(
        UnicodeDecodeError,
        salt.utils.data.decode,
        get_BYTES,
        keep=False,
        to_str=True,
    )


def test_decode_fallback():
    """
    Test fallback to utf-8
    """
    with patch.object(builtins, "__salt_system_encoding__", "ascii"):
        assert salt.utils.data.decode(_b("яйца")) == "яйца"


def test_encode(get_test_data, get_BYTES, get_EGGS):
    """
    NOTE: This uses the lambda "_b" defined above in the global scope,
    which encodes a string to a bytestring, assuming utf-8.
    """
    expected = [
        _b("unicode_str"),
        _b("питон"),
        123,
        456.789,
        True,
        False,
        None,
        _b(get_EGGS),
        get_BYTES,
        [123, 456.789, _b("спам"), True, False, None, _b(get_EGGS), get_BYTES],
        (987, 654.321, _b("яйца"), _b(get_EGGS), None, (True, _b(get_EGGS), get_BYTES)),
        {
            _b("str_key"): _b("str_val"),
            None: True,
            123: 456.789,
            _b(get_EGGS): get_BYTES,
            _b("subdict"): {
                _b("unicode_key"): _b(get_EGGS),
                _b("tuple"): (
                    123,
                    _b("hello"),
                    _b("world"),
                    True,
                    _b(get_EGGS),
                    get_BYTES,
                ),
                _b("list"): [456, _b("спам"), False, _b(get_EGGS), get_BYTES],
            },
        },
        SaltOrderedDict(
            [(_b("foo"), _b("bar")), (123, 456), (_b(get_EGGS), get_BYTES)]
        ),
    ]

    # Both keep=True and keep=False should work because the get_BYTES data is
    # already bytes.
    ret = salt.utils.data.encode(
        get_test_data, keep=True, preserve_dict_class=True, preserve_tuples=True
    )
    assert ret == expected
    ret = salt.utils.data.encode(
        get_test_data, keep=False, preserve_dict_class=True, preserve_tuples=True
    )
    assert ret == expected

    # Now munge the expected data so that we get what we would expect if we
    # disable preservation of dict class and tuples
    expected[10] = [
        987,
        654.321,
        _b("яйца"),
        _b(get_EGGS),
        None,
        [True, _b(get_EGGS), get_BYTES],
    ]
    expected[11][_b("subdict")][  # pylint: disable=unsupported-assignment-operation
        _b("tuple")
    ] = [
        123,
        _b("hello"),
        _b("world"),
        True,
        _b(get_EGGS),
        get_BYTES,
    ]
    expected[12] = {_b("foo"): _b("bar"), 123: 456, _b(get_EGGS): get_BYTES}

    ret = salt.utils.data.encode(
        get_test_data, keep=True, preserve_dict_class=False, preserve_tuples=False
    )
    assert ret == expected
    ret = salt.utils.data.encode(
        get_test_data, keep=False, preserve_dict_class=False, preserve_tuples=False
    )
    assert ret == expected

    # Now test single non-string, non-data-structure items, these should
    # return the same value when passed to this function
    for item in (123, 4.56, True, False, None):
        log.debug("Testing encode of %s", item)
        assert salt.utils.data.encode(item) == item

    # Test single strings (not in a data structure)
    assert salt.utils.data.encode("foo") == _b("foo")
    assert salt.utils.data.encode(_b("bar")) == _b("bar")

    # Test binary blob, nothing should happen even when keep=False since
    # the data is already bytes
    assert salt.utils.data.encode(get_BYTES, keep=True) == get_BYTES
    assert salt.utils.data.encode(get_BYTES, keep=False) == get_BYTES


def test_encode_keep():
    """
    Whereas we tested the keep argument in test_decode, it is much easier
    to do a more comprehensive test of keep in its own function where we
    can force the encoding.
    """
    unicode_str = "питон"
    encoding = "ascii"

    # Test single string
    assert salt.utils.data.encode(unicode_str, encoding, keep=True) == unicode_str
    pytest.raises(
        UnicodeEncodeError,
        salt.utils.data.encode,
        unicode_str,
        encoding,
        keep=False,
    )

    data = [
        unicode_str,
        [b"foo", [unicode_str], {b"key": unicode_str}, (unicode_str,)],
        {
            b"list": [b"foo", unicode_str],
            b"dict": {b"key": unicode_str},
            b"tuple": (b"foo", unicode_str),
        },
        ([b"foo", unicode_str], {b"key": unicode_str}, (unicode_str,)),
    ]

    # Since everything was a bytestring aside from the bogus data, the
    # return data should be identical. We don't need to test recursive
    # decoding, that has already been tested in test_encode.
    assert (
        salt.utils.data.encode(data, encoding, keep=True, preserve_tuples=True) == data
    )
    pytest.raises(
        UnicodeEncodeError,
        salt.utils.data.encode,
        data,
        encoding,
        keep=False,
        preserve_tuples=True,
    )

    for index, _ in enumerate(data):
        assert (
            salt.utils.data.encode(
                data[index], encoding, keep=True, preserve_tuples=True
            )
            == data[index]
        )
        pytest.raises(
            UnicodeEncodeError,
            salt.utils.data.encode,
            data[index],
            encoding,
            keep=False,
            preserve_tuples=True,
        )


def test_encode_fallback():
    """
    Test fallback to utf-8
    """
    with patch.object(builtins, "__salt_system_encoding__", "ascii"):
        assert salt.utils.data.encode("яйца") == _b("яйца")
    with patch.object(builtins, "__salt_system_encoding__", "CP1252"):
        assert salt.utils.data.encode("Ψ") == _b("Ψ")


def test_repack_dict():
    list_of_one_element_dicts = [
        {"dict_key_1": "dict_val_1"},
        {"dict_key_2": "dict_val_2"},
        {"dict_key_3": "dict_val_3"},
    ]
    expected_ret = {
        "dict_key_1": "dict_val_1",
        "dict_key_2": "dict_val_2",
        "dict_key_3": "dict_val_3",
    }
    ret = salt.utils.data.repack_dictlist(list_of_one_element_dicts)
    assert ret == expected_ret

    # Try with yaml
    yaml_key_val_pair = "- key1: val1"
    ret = salt.utils.data.repack_dictlist(yaml_key_val_pair)
    assert ret == {"key1": "val1"}

    # Make sure we handle non-yaml junk data
    ret = salt.utils.data.repack_dictlist(LOREM_IPSUM)
    assert ret == {}


def test_stringify():
    pytest.raises(TypeError, salt.utils.data.stringify, 9)
    assert salt.utils.data.stringify(["one", "two", "three", 4, 5]) == [
        "one",
        "two",
        "three",
        "4",
        "5",
    ]


def test_to_entries():
    data = {"a": 1, "b": 2}
    entries = [{"key": "a", "value": 1}, {"key": "b", "value": 2}]
    assert salt.utils.data.to_entries(data) == entries

    data = ["monkey", "donkey"]
    entries = [{"key": 0, "value": "monkey"}, {"key": 1, "value": "donkey"}]
    assert salt.utils.data.to_entries(data) == entries

    with pytest.raises(SaltException):
        salt.utils.data.to_entries("RAISE ON THIS")


def test_from_entries():
    entries = [{"key": "a", "value": 1}, {"key": "b", "value": 2}]
    data = {"a": 1, "b": 2}
    assert salt.utils.data.from_entries(entries) == data


def test_json_query():
    # Raises exception if jmespath module is not found
    with patch("salt.utils.data.jmespath", None):
        with pytest.raises(RuntimeError, match="requires jmespath"):
            salt.utils.data.json_query({}, "@")

    # Test search
    user_groups = {
        "user1": {"groups": ["group1", "group2", "group3"]},
        "user2": {"groups": ["group1", "group2"]},
        "user3": {"groups": ["group3"]},
    }
    expression = "*.groups[0]"
    primary_groups = ["group1", "group1", "group3"]
    assert sorted(salt.utils.data.json_query(user_groups, expression)) == primary_groups


def test_nop():
    """
    Test cases where nothing will be done.
    """
    # Test with dictionary without recursion
    old_dict = {
        "foo": "bar",
        "bar": {"baz": {"qux": "quux"}},
        "baz": ["qux", {"foo": "bar"}],
    }
    new_dict = salt.utils.data.filter_falsey(old_dict)
    assert old_dict == new_dict
    # Check returned type equality
    assert type(old_dict) is type(new_dict)
    # Test dictionary with recursion
    new_dict = salt.utils.data.filter_falsey(old_dict, recurse_depth=3)
    assert old_dict == new_dict
    # Test with list
    old_list = ["foo", "bar"]
    new_list = salt.utils.data.filter_falsey(old_list)
    assert old_list == new_list
    # Check returned type equality
    assert type(old_list) is type(new_list)
    # Test with set
    old_set = {"foo", "bar"}
    new_set = salt.utils.data.filter_falsey(old_set)
    assert old_set == new_set
    # Check returned type equality
    assert type(old_set) is type(new_set)
    # Test with SaltOrderedDict
    old_dict = SaltOrderedDict(
        [
            ("foo", "bar"),
            ("bar", SaltOrderedDict([("qux", "quux")])),
            ("baz", ["qux", SaltOrderedDict([("foo", "bar")])]),
        ]
    )
    new_dict = salt.utils.data.filter_falsey(old_dict)
    assert old_dict == new_dict
    assert type(old_dict) is type(new_dict)
    # Test excluding int
    old_list = [0]
    new_list = salt.utils.data.filter_falsey(old_list, ignore_types=[int])
    assert old_list == new_list
    # Test excluding str (or unicode) (or both)
    old_list = [""]
    new_list = salt.utils.data.filter_falsey(old_list, ignore_types=[str])
    assert old_list == new_list
    # Test excluding list
    old_list = [[]]
    new_list = salt.utils.data.filter_falsey(old_list, ignore_types=[type([])])
    assert old_list == new_list
    # Test excluding dict
    old_list = [{}]
    new_list = salt.utils.data.filter_falsey(old_list, ignore_types=[type({})])
    assert old_list == new_list


def test_filter_dict_no_recurse():
    """
    Test filtering a dictionary without recursing.
    This will only filter out key-values where the values are falsey.
    """
    old_dict = {
        "foo": None,
        "bar": {"baz": {"qux": None, "quux": "", "foo": []}},
        "baz": ["qux"],
        "qux": {},
        "quux": [],
    }
    new_dict = salt.utils.data.filter_falsey(old_dict)
    expect_dict = {
        "bar": {"baz": {"qux": None, "quux": "", "foo": []}},
        "baz": ["qux"],
    }
    assert expect_dict == new_dict
    assert type(expect_dict) is type(new_dict)


def test_filter_dict_recurse():
    """
    Test filtering a dictionary with recursing.
    This will filter out any key-values where the values are falsey or when
    the values *become* falsey after filtering their contents (in case they
    are lists or dicts).
    """
    old_dict = {
        "foo": None,
        "bar": {"baz": {"qux": None, "quux": "", "foo": []}},
        "baz": ["qux"],
        "qux": {},
        "quux": [],
    }
    new_dict = salt.utils.data.filter_falsey(old_dict, recurse_depth=3)
    expect_dict = {"baz": ["qux"]}
    assert expect_dict == new_dict
    assert type(expect_dict) is type(new_dict)


def test_filter_list_no_recurse():
    """
    Test filtering a list without recursing.
    This will only filter out items which are falsey.
    """
    old_list = ["foo", None, [], {}, 0, ""]
    new_list = salt.utils.data.filter_falsey(old_list)
    expect_list = ["foo"]
    assert expect_list == new_list
    assert type(expect_list) is type(new_list)
    # Ensure nested values are *not* filtered out.
    old_list = [
        "foo",
        ["foo"],
        ["foo", None],
        {"foo": 0},
        {"foo": "bar", "baz": []},
        [{"foo": ""}],
    ]
    new_list = salt.utils.data.filter_falsey(old_list)
    assert old_list == new_list
    assert type(old_list) is type(new_list)


def test_filter_list_recurse():
    """
    Test filtering a list with recursing.
    This will filter out any items which are falsey, or which become falsey
    after filtering their contents (in case they are lists or dicts).
    """
    old_list = [
        "foo",
        ["foo"],
        ["foo", None],
        {"foo": 0},
        {"foo": "bar", "baz": []},
        [{"foo": ""}],
    ]
    new_list = salt.utils.data.filter_falsey(old_list, recurse_depth=3)
    expect_list = ["foo", ["foo"], ["foo"], {"foo": "bar"}]
    assert expect_list == new_list
    assert type(expect_list) is type(new_list)


def test_filter_set_no_recurse():
    """
    Test filtering a set without recursing.
    Note that a set cannot contain unhashable types, so recursion is not possible.
    """
    old_set = {"foo", None, 0, ""}
    new_set = salt.utils.data.filter_falsey(old_set)
    expect_set = {"foo"}
    assert expect_set == new_set
    assert type(expect_set) is type(new_set)


def test_filter_ordereddict_no_recurse():
    """
    Test filtering an SaltOrderedDict without recursing.
    """
    old_dict = SaltOrderedDict(
        [
            ("foo", None),
            (
                "bar",
                SaltOrderedDict(
                    [
                        (
                            "baz",
                            SaltOrderedDict([("qux", None), ("quux", ""), ("foo", [])]),
                        )
                    ]
                ),
            ),
            ("baz", ["qux"]),
            ("qux", {}),
            ("quux", []),
        ]
    )
    new_dict = salt.utils.data.filter_falsey(old_dict)
    expect_dict = SaltOrderedDict(
        [
            (
                "bar",
                SaltOrderedDict(
                    [
                        (
                            "baz",
                            SaltOrderedDict([("qux", None), ("quux", ""), ("foo", [])]),
                        )
                    ]
                ),
            ),
            ("baz", ["qux"]),
        ]
    )
    assert expect_dict == new_dict
    assert type(expect_dict) is type(new_dict)


def test_filter_ordereddict_recurse():
    """
    Test filtering an SaltOrderedDict with recursing.
    """
    old_dict = SaltOrderedDict(
        [
            ("foo", None),
            (
                "bar",
                SaltOrderedDict(
                    [
                        (
                            "baz",
                            SaltOrderedDict([("qux", None), ("quux", ""), ("foo", [])]),
                        )
                    ]
                ),
            ),
            ("baz", ["qux"]),
            ("qux", {}),
            ("quux", []),
        ]
    )
    new_dict = salt.utils.data.filter_falsey(old_dict, recurse_depth=3)
    expect_dict = SaltOrderedDict([("baz", ["qux"])])
    assert expect_dict == new_dict
    assert type(expect_dict) is type(new_dict)


def test_filter_list_recurse_limit():
    """
    Test filtering a list with recursing, but with a limited depth.
    Note that the top-level is always processed, so a recursion depth of 2
    means that two *additional* levels are processed.
    """
    old_list = [None, [None, [None, [None]]]]
    new_list = salt.utils.data.filter_falsey(old_list, recurse_depth=2)
    assert [[[[None]]]] == new_list


def test_filter_dict_recurse_limit():
    """
    Test filtering a dict with recursing, but with a limited depth.
    Note that the top-level is always processed, so a recursion depth of 2
    means that two *additional* levels are processed.
    """
    old_dict = {
        "one": None,
        "foo": {"two": None, "bar": {"three": None, "baz": {"four": None}}},
    }
    new_dict = salt.utils.data.filter_falsey(old_dict, recurse_depth=2)
    assert {"foo": {"bar": {"baz": {"four": None}}}} == new_dict


def test_filter_exclude_types():
    """
    Test filtering a list recursively, but also ignoring (i.e. not filtering)
    out certain types that can be falsey.
    """
    # Ignore int, unicode
    old_list = [
        "foo",
        ["foo"],
        ["foo", None],
        {"foo": 0},
        {"foo": "bar", "baz": []},
        [{"foo": ""}],
    ]
    new_list = salt.utils.data.filter_falsey(
        old_list, recurse_depth=3, ignore_types=[int, str]
    )
    assert [
        "foo",
        ["foo"],
        ["foo"],
        {"foo": 0},
        {"foo": "bar"},
        [{"foo": ""}],
    ] == new_list
    # Ignore list
    old_list = [
        "foo",
        ["foo"],
        ["foo", None],
        {"foo": 0},
        {"foo": "bar", "baz": []},
        [{"foo": ""}],
    ]
    new_list = salt.utils.data.filter_falsey(
        old_list, recurse_depth=3, ignore_types=[type([])]
    )
    assert ["foo", ["foo"], ["foo"], {"foo": "bar", "baz": []}, []] == new_list
    # Ignore dict
    old_list = [
        "foo",
        ["foo"],
        ["foo", None],
        {"foo": 0},
        {"foo": "bar", "baz": []},
        [{"foo": ""}],
    ]
    new_list = salt.utils.data.filter_falsey(
        old_list, recurse_depth=3, ignore_types=[type({})]
    )
    assert ["foo", ["foo"], ["foo"], {}, {"foo": "bar"}, [{}]] == new_list
    # Ignore NoneType
    old_list = [
        "foo",
        ["foo"],
        ["foo", None],
        {"foo": 0},
        {"foo": "bar", "baz": []},
        [{"foo": ""}],
    ]
    new_list = salt.utils.data.filter_falsey(
        old_list, recurse_depth=3, ignore_types=[type(None)]
    )
    assert ["foo", ["foo"], ["foo", None], {"foo": "bar"}] == new_list


def test_list_equality():
    """
    Test cases where equal lists are compared.
    """
    test_list = [0, 1, 2]
    assert {} == salt.utils.data.recursive_diff(test_list, test_list)

    test_list = [[0], [1], [0, 1, 2]]
    assert {} == salt.utils.data.recursive_diff(test_list, test_list)


def test_dict_equality():
    """
    Test cases where equal dicts are compared.
    """
    test_dict = {"foo": "bar", "bar": {"baz": {"qux": "quux"}}, "frop": 0}
    assert {} == salt.utils.data.recursive_diff(test_dict, test_dict)


def test_ordereddict_equality():
    """
    Test cases where equal SaltOrderedDicts are compared.
    """
    test_dict = SaltOrderedDict(
        [
            ("foo", "bar"),
            ("bar", SaltOrderedDict([("baz", SaltOrderedDict([("qux", "quux")]))])),
            ("frop", 0),
        ]
    )
    assert {} == salt.utils.data.recursive_diff(test_dict, test_dict)


def test_mixed_equality():
    """
    Test cases where mixed nested lists and dicts are compared.
    """
    test_data = {
        "foo": "bar",
        "baz": [0, 1, 2],
        "bar": {"baz": [{"qux": "quux"}, {"froop", 0}]},
    }
    assert {} == salt.utils.data.recursive_diff(test_data, test_data)


def test_set_equality():
    """
    Test cases where equal sets are compared.
    """
    test_set = {0, 1, 2, 3, "foo"}
    assert {} == salt.utils.data.recursive_diff(test_set, test_set)

    # This is a bit of an oddity, as python seems to sort the sets in memory
    # so both sets end up with the same ordering (0..3).
    set_one = {0, 1, 2, 3}
    set_two = {3, 2, 1, 0}
    assert {} == salt.utils.data.recursive_diff(set_one, set_two)


def test_tuple_equality():
    """
    Test cases where equal tuples are compared.
    """
    test_tuple = (0, 1, 2, 3, "foo")
    assert {} == salt.utils.data.recursive_diff(test_tuple, test_tuple)


def test_list_inequality():
    """
    Test cases where two inequal lists are compared.
    """
    list_one = [0, 1, 2]
    list_two = ["foo", "bar", "baz"]
    expected_result = {"old": list_one, "new": list_two}
    assert expected_result == salt.utils.data.recursive_diff(list_one, list_two)
    expected_result = {"new": list_one, "old": list_two}
    assert expected_result == salt.utils.data.recursive_diff(list_two, list_one)

    list_one = [0, "foo", 1, "bar"]
    list_two = [1, "foo", 1, "qux"]
    expected_result = {"old": [0, "bar"], "new": [1, "qux"]}
    assert expected_result == salt.utils.data.recursive_diff(list_one, list_two)
    expected_result = {"new": [0, "bar"], "old": [1, "qux"]}
    assert expected_result == salt.utils.data.recursive_diff(list_two, list_one)

    list_one = [0, 1, [2, 3]]
    list_two = [0, 1, ["foo", "bar"]]
    expected_result = {"old": [[2, 3]], "new": [["foo", "bar"]]}
    assert expected_result == salt.utils.data.recursive_diff(list_one, list_two)
    expected_result = {"new": [[2, 3]], "old": [["foo", "bar"]]}
    assert expected_result == salt.utils.data.recursive_diff(list_two, list_one)


def test_dict_inequality():
    """
    Test cases where two inequal dicts are compared.
    """
    dict_one = {"foo": 1, "bar": 2, "baz": 3}
    dict_two = {"foo": 2, 1: "bar", "baz": 3}
    expected_result = {"old": {"foo": 1, "bar": 2}, "new": {"foo": 2, 1: "bar"}}
    assert expected_result == salt.utils.data.recursive_diff(dict_one, dict_two)
    expected_result = {"new": {"foo": 1, "bar": 2}, "old": {"foo": 2, 1: "bar"}}
    assert expected_result == salt.utils.data.recursive_diff(dict_two, dict_one)

    dict_one = {"foo": {"bar": {"baz": 1}}}
    dict_two = {"foo": {"qux": {"baz": 1}}}
    expected_result = {"old": dict_one, "new": dict_two}
    assert expected_result == salt.utils.data.recursive_diff(dict_one, dict_two)
    expected_result = {"new": dict_one, "old": dict_two}
    assert expected_result == salt.utils.data.recursive_diff(dict_two, dict_one)


def test_ordereddict_inequality():
    """
    Test cases where two inequal SaltOrderedDicts are compared.
    """
    odict_one = SaltOrderedDict([("foo", "bar"), ("bar", "baz")])
    odict_two = SaltOrderedDict([("bar", "baz"), ("foo", "bar")])
    expected_result = {"old": odict_one, "new": odict_two}
    assert expected_result == salt.utils.data.recursive_diff(odict_one, odict_two)


def test_set_inequality():
    """
    Test cases where two inequal sets are compared.
    Tricky as the sets are compared zipped, so shuffled sets of equal values
    are considered different.
    """
    set_one = {0, 1, 2, 4}
    set_two = {0, 1, 3, 4}
    expected_result = {"old": {2}, "new": {3}}
    assert expected_result == salt.utils.data.recursive_diff(set_one, set_two)
    expected_result = {"new": {2}, "old": {3}}
    assert expected_result == salt.utils.data.recursive_diff(set_two, set_one)

    # It is unknown how different python versions will store sets in memory.
    # Python 2.7 seems to sort it (i.e. set_one below becomes {0, 1, 'foo', 'bar'}
    # However Python 3.6.8 stores it differently each run.
    # So just test for "not equal" here.
    set_one = {0, "foo", 1, "bar"}
    set_two = {"foo", 1, "bar", 2}
    expected_result = {}
    assert expected_result != salt.utils.data.recursive_diff(set_one, set_two)


def test_mixed_inequality():
    """
    Test cases where two mixed dicts/iterables that are different are compared.
    """
    dict_one = {"foo": [1, 2, 3]}
    dict_two = {"foo": [3, 2, 1]}
    expected_result = {"old": {"foo": [1, 3]}, "new": {"foo": [3, 1]}}
    assert expected_result == salt.utils.data.recursive_diff(dict_one, dict_two)
    expected_result = {"new": {"foo": [1, 3]}, "old": {"foo": [3, 1]}}
    assert expected_result == salt.utils.data.recursive_diff(dict_two, dict_one)

    list_one = [1, 2, {"foo": ["bar", {"foo": 1, "bar": 2}]}]
    list_two = [3, 4, {"foo": ["qux", {"foo": 1, "bar": 2}]}]
    expected_result = {
        "old": [1, 2, {"foo": ["bar"]}],
        "new": [3, 4, {"foo": ["qux"]}],
    }
    assert expected_result == salt.utils.data.recursive_diff(list_one, list_two)
    expected_result = {
        "new": [1, 2, {"foo": ["bar"]}],
        "old": [3, 4, {"foo": ["qux"]}],
    }
    assert expected_result == salt.utils.data.recursive_diff(list_two, list_one)

    mixed_one = {"foo": {0, 1, 2}, "bar": [0, 1, 2]}
    mixed_two = {"foo": {1, 2, 3}, "bar": [1, 2, 3]}
    expected_result = {
        "old": {"foo": {0}, "bar": [0, 1, 2]},
        "new": {"foo": {3}, "bar": [1, 2, 3]},
    }
    assert expected_result == salt.utils.data.recursive_diff(mixed_one, mixed_two)
    expected_result = {
        "new": {"foo": {0}, "bar": [0, 1, 2]},
        "old": {"foo": {3}, "bar": [1, 2, 3]},
    }
    assert expected_result == salt.utils.data.recursive_diff(mixed_two, mixed_one)


def test_tuple_inequality():
    """
    Test cases where two tuples that are different are compared.
    """
    tuple_one = (1, 2, 3)
    tuple_two = (3, 2, 1)
    expected_result = {"old": (1, 3), "new": (3, 1)}
    assert expected_result == salt.utils.data.recursive_diff(tuple_one, tuple_two)


def test_list_vs_set():
    """
    Test case comparing a list with a set, will be compared unordered.
    """
    mixed_one = [1, 2, 3]
    mixed_two = {3, 2, 1}
    expected_result = {}
    assert expected_result == salt.utils.data.recursive_diff(mixed_one, mixed_two)
    assert expected_result == salt.utils.data.recursive_diff(mixed_two, mixed_one)


def test_dict_vs_ordereddict():
    """
    Test case comparing a dict with an ordereddict, will be compared unordered.
    """
    test_dict = {"foo": "bar", "bar": "baz"}
    test_odict = SaltOrderedDict([("foo", "bar"), ("bar", "baz")])
    assert {} == salt.utils.data.recursive_diff(test_dict, test_odict)
    assert {} == salt.utils.data.recursive_diff(test_odict, test_dict)

    test_odict2 = SaltOrderedDict([("bar", "baz"), ("foo", "bar")])
    assert {} == salt.utils.data.recursive_diff(test_dict, test_odict2)
    assert {} == salt.utils.data.recursive_diff(test_odict2, test_dict)


def test_list_ignore_ignored():
    """
    Test case comparing two lists with ignore-list supplied (which is not used
    when comparing lists).
    """
    list_one = [1, 2, 3]
    list_two = [3, 2, 1]
    expected_result = {"old": [1, 3], "new": [3, 1]}
    assert expected_result == salt.utils.data.recursive_diff(
        list_one, list_two, ignore_keys=[1, 3]
    )


def test_dict_ignore():
    """
    Test case comparing two dicts with ignore-list supplied.
    """
    dict_one = {"foo": 1, "bar": 2, "baz": 3}
    dict_two = {"foo": 3, "bar": 2, "baz": 1}
    expected_result = {"old": {"baz": 3}, "new": {"baz": 1}}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, dict_two, ignore_keys=["foo"]
    )


def test_ordereddict_ignore():
    """
    Test case comparing two SaltOrderedDicts with ignore-list supplied.
    """
    odict_one = SaltOrderedDict([("foo", 1), ("bar", 2), ("baz", 3)])
    odict_two = SaltOrderedDict([("baz", 1), ("bar", 2), ("foo", 3)])
    # The key 'foo' will be ignored, which means the key from the other SaltOrderedDict
    # will always be considered "different" since SaltOrderedDicts are compared ordered.
    expected_result = {
        "old": SaltOrderedDict([("baz", 3)]),
        "new": SaltOrderedDict([("baz", 1)]),
    }
    assert expected_result == salt.utils.data.recursive_diff(
        odict_one, odict_two, ignore_keys=["foo"]
    )


def test_dict_vs_ordereddict_ignore():
    """
    Test case comparing a dict with an SaltOrderedDict with ignore-list supplied.
    """
    dict_one = {"foo": 1, "bar": 2, "baz": 3}
    odict_two = SaltOrderedDict([("foo", 3), ("bar", 2), ("baz", 1)])
    expected_result = {"old": {"baz": 3}, "new": SaltOrderedDict([("baz", 1)])}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, odict_two, ignore_keys=["foo"]
    )


def test_mixed_nested_ignore():
    """
    Test case comparing mixed, nested items with ignore-list supplied.
    """
    dict_one = {"foo": [1], "bar": {"foo": 1, "bar": 2}, "baz": 3}
    dict_two = {"foo": [2], "bar": {"foo": 3, "bar": 2}, "baz": 1}
    expected_result = {"old": {"baz": 3}, "new": {"baz": 1}}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, dict_two, ignore_keys=["foo"]
    )


def test_ordered_dict_unequal_length():
    """
    Test case comparing two SaltOrderedDicts of unequal length.
    """
    odict_one = SaltOrderedDict([("foo", 1), ("bar", 2), ("baz", 3)])
    odict_two = SaltOrderedDict([("foo", 1), ("bar", 2)])
    expected_result = {"old": SaltOrderedDict([("baz", 3)]), "new": {}}
    assert expected_result == salt.utils.data.recursive_diff(odict_one, odict_two)


def test_list_unequal_length():
    """
    Test case comparing two lists of unequal length.
    """
    list_one = [1, 2, 3]
    list_two = [1, 2, 3, 4]
    expected_result = {"old": [], "new": [4]}
    assert expected_result == salt.utils.data.recursive_diff(list_one, list_two)


def test_set_unequal_length():
    """
    Test case comparing two sets of unequal length.
    This does not do anything special, as it is unordered.
    """
    set_one = {1, 2, 3}
    set_two = {4, 3, 2, 1}
    expected_result = {"old": set(), "new": {4}}
    assert expected_result == salt.utils.data.recursive_diff(set_one, set_two)


def test_tuple_unequal_length():
    """
    Test case comparing two tuples of unequal length.
    This should be the same as comparing two ordered lists.
    """
    tuple_one = (1, 2, 3)
    tuple_two = (1, 2, 3, 4)
    expected_result = {"old": (), "new": (4,)}
    assert expected_result == salt.utils.data.recursive_diff(tuple_one, tuple_two)


def test_list_unordered():
    """
    Test case comparing two lists unordered.
    """
    list_one = [1, 2, 3, 4]
    list_two = [4, 3, 2]
    expected_result = {"old": [1], "new": []}
    assert expected_result == salt.utils.data.recursive_diff(
        list_one, list_two, ignore_order=True
    )


def test_mixed_nested_unordered():
    """
    Test case comparing nested dicts/lists unordered.
    """
    dict_one = {"foo": {"bar": [1, 2, 3]}, "bar": [{"foo": 4}, 0]}
    dict_two = {"foo": {"bar": [3, 2, 1]}, "bar": [0, {"foo": 4}]}
    expected_result = {}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, dict_two, ignore_order=True
    )
    expected_result = {
        "old": {"foo": {"bar": [1, 3]}, "bar": [{"foo": 4}, 0]},
        "new": {"foo": {"bar": [3, 1]}, "bar": [0, {"foo": 4}]},
    }
    assert expected_result == salt.utils.data.recursive_diff(dict_one, dict_two)


def test_ordered_dict_unordered():
    """
    Test case comparing SaltOrderedDicts unordered.
    """
    odict_one = SaltOrderedDict([("foo", 1), ("bar", 2), ("baz", 3)])
    odict_two = SaltOrderedDict([("baz", 3), ("bar", 2), ("foo", 1)])
    expected_result = {}
    assert expected_result == salt.utils.data.recursive_diff(
        odict_one, odict_two, ignore_order=True
    )


def test_ignore_missing_keys_dict():
    """
    Test case ignoring missing keys on a comparison of dicts.
    """
    dict_one = {"foo": 1, "bar": 2, "baz": 3}
    dict_two = {"bar": 3}
    expected_result = {"old": {"bar": 2}, "new": {"bar": 3}}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, dict_two, ignore_missing_keys=True
    )


def test_ignore_missing_keys_ordered_dict():
    """
    Test case not ignoring missing keys on a comparison of SaltOrderedDicts.
    """
    odict_one = SaltOrderedDict([("foo", 1), ("bar", 2), ("baz", 3)])
    odict_two = SaltOrderedDict([("bar", 3)])
    expected_result = {"old": odict_one, "new": odict_two}
    assert expected_result == salt.utils.data.recursive_diff(
        odict_one, odict_two, ignore_missing_keys=True
    )


def test_ignore_missing_keys_recursive():
    """
    Test case ignoring missing keys on a comparison of nested dicts.
    """
    dict_one = {"foo": {"bar": 2, "baz": 3}}
    dict_two = {"foo": {"baz": 3}}
    expected_result = {}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, dict_two, ignore_missing_keys=True
    )
    # Compare from dict-in-dict
    dict_two = {}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, dict_two, ignore_missing_keys=True
    )
    # Compare from dict-in-list
    dict_one = {"foo": ["bar", {"baz": 3}]}
    dict_two = {"foo": ["bar", {}]}
    assert expected_result == salt.utils.data.recursive_diff(
        dict_one, dict_two, ignore_missing_keys=True
    )

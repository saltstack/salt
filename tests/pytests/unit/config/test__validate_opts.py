"""
Test config option type enforcement
"""

import pytest

import salt.config


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], True),  # list
        ((1, 2, 3), True),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", False),  # str
        (True, False),  # bool
        (1, False),  # int
        (0.123, False),  # float
        (None, False),  # None
    ],
)
def test_list_types(option_value, expected):
    """
    List and tuple type config options return True when the value is a list. All
    other types return False
    modules_dirs is a list type config option
    """
    result = salt.config._validate_opts({"module_dirs": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", True),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, True),  # None
    ],
)
def test_str_types(option_value, expected):
    """
    Str, bool, int, float, and none type config options return True when the
    value is a str. All other types return False
    user is a str type config option
    """
    result = salt.config._validate_opts({"user": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, True),  # dict
        ("str", False),  # str
        (True, False),  # bool
        (1, False),  # int
        (0.123, False),  # float
        (None, False),  # None
    ],
)
def test_dict_types(option_value, expected):
    """
    Dict type config options return True when the value is a dict. All other
    types return False
    file_roots is a dict type config option
    """
    result = salt.config._validate_opts({"file_roots": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", False),  # str
        (True, True),  # bool
        (1, False),  # int
        (0.123, False),  # float
        (None, False),  # None
    ],
)
def test_bool_types(option_value, expected):
    """
    Bool type config options return True when the value is a bool. All other
    types return False
    local is a bool type config option
    """
    result = salt.config._validate_opts({"local": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", False),  # str
        (True, False),  # bool
        (1, True),  # int
        (0.123, False),  # float
        (None, False),  # None
    ],
)
def test_int_types(option_value, expected):
    """
    Int type config options return True when the value is an int. All other
    types return False
    publish_port is an int type config option
    """
    result = salt.config._validate_opts({"publish_port": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", False),  # str
        (True, False),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, False),  # None
    ],
)
def test_float_types(option_value, expected):
    """
    Float and int type config options return True when the value is a float. All
    other types return False
    ssh_timeout is a float type config option
    """
    result = salt.config._validate_opts({"ssh_timeout": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", True),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, True),  # None
    ],
)
def test_none_str_types(option_value, expected):
    """
    Some config settings have two types, None and str. In that case str, bool,
    int, float, and None type options should evaluate as True. All others should
    return False.
    saltenv is a None, str type config option
    """
    result = salt.config._validate_opts({"saltenv": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", False),  # str
        (True, False),  # bool
        (1, True),  # int
        (0.123, False),  # float
        (None, True),  # None
    ],
)
def test_none_int_types(option_value, expected):
    """
    Some config settings have two types, None and int, which should evaluate as
    True. All others should return False.
    retry_dns_count is a None, int type config option
    """
    result = salt.config._validate_opts({"retry_dns_count": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", False),  # str
        (True, True),  # bool
        (1, False),  # int
        (0.123, False),  # float
        (None, True),  # None
    ],
)
def test_none_bool_types(option_value, expected):
    """
    Some config settings have two types, None and bool which should evaluate as
    True. All others should return False.
    ipv6 is a None, bool type config option
    """
    result = salt.config._validate_opts({"ipv6": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], True),  # list
        ((1, 2, 3), True),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", True),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, True),  # None
    ],
)
def test_str_list_types(option_value, expected):
    """
    Some config settings have two types, str and list. In that case, list,
    tuple, str, bool, int, float, and None should evaluate as True. All others
    should return False.
    master is a str, list type config option
    """
    result = salt.config._validate_opts({"master": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", True),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, True),  # None
    ],
)
def test_str_int_types(option_value, expected):
    """
    Some config settings have two types, str and int. In that case, str, bool,
    int, float, and None should evaluate as True. All others should return
    False.
    master_port is a str, int type config option
    """
    result = salt.config._validate_opts({"master_port": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, True),  # dict
        ("str", True),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, True),  # None
    ],
)
def test_str_dict_types(option_value, expected):
    """
    Some config settings have two types, str and dict. In that case, dict, str,
    bool, int, float, and None should evaluate as True. All others should return
    False.
    id_function is a str, dict type config option
    """
    result = salt.config._validate_opts({"id_function": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], True),  # list
        ((1, 2, 3), True),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", True),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, True),  # None
    ],
)
def test_str_tuple_types(option_value, expected):
    """
    Some config settings have two types, str and tuple. In that case, list,
    tuple, str, bool, int, float, and None should evaluate as True. All others
    should return False.
    log_fmt_logfile is a str, tuple type config option
    """
    result = salt.config._validate_opts({"log_fmt_logfile": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", True),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, True),  # float
        (None, True),  # None
    ],
)
def test_str_bool_types(option_value, expected):
    """
    Some config settings have two types, str and bool. In that case, str, bool,
    int, float, and None should evaluate as True. All others should return
    False.
    update_url is a str, bool type config option
    """
    result = salt.config._validate_opts({"update_url": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, True),  # dict
        ("str", False),  # str
        (True, True),  # bool
        (1, False),  # int
        (0.123, False),  # float
        (None, False),  # None
    ],
)
def test_dict_bool_types(option_value, expected):
    """
    Some config settings have two types, dict and bool which should evaluate as
    True. All others should return False.
    token_expire_user_override is a dict, bool type config option
    """
    result = salt.config._validate_opts({"token_expire_user_override": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], True),  # list
        ((1, 2, 3), True),  # tuple
        ({"key": "value"}, True),  # dict
        ("str", False),  # str
        (True, False),  # bool
        (1, False),  # int
        (0.123, False),  # float
        (None, False),  # None
    ],
)
def test_dict_list_types(option_value, expected):
    """
    Some config settings have two types, dict and list. In that case, list,
    tuple, and dict should evaluate as True. All others should return False.
    nodegroups is a dict, list type config option
    """
    result = salt.config._validate_opts({"nodegroups": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, True),  # dict
        ("str", False),  # str
        (True, True),  # bool
        (1, False),  # int
        (0.123, False),  # float
        (None, True),  # None
    ],
)
def test_dict_bool_none_types(option_value, expected):
    """
    Some config settings have three types, dict, bool, and None which should
    evaluate as True. All others should return False.
    ssl is a dict, bool type config option
    """
    result = salt.config._validate_opts({"ssl": option_value})
    assert result is expected


@pytest.mark.parametrize(
    "option_value,expected",
    [
        ([1, 2, 3], False),  # list
        ((1, 2, 3), False),  # tuple
        ({"key": "value"}, False),  # dict
        ("str", False),  # str
        (True, True),  # bool
        (1, True),  # int
        (0.123, False),  # float
        (None, False),  # None
    ],
)
def test_bool_int_types(option_value, expected):
    """
    Some config settings have two types, bool and int. In that case, bool and
    int should evaluate as True. All others should return False.
    state_queue is a bool/int config option
    """
    result = salt.config._validate_opts({"state_queue": option_value})
    assert result is expected

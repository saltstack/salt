import salt.utils.data


def test_get_value_simple_path():
    data = {"a": {"b": {"c": "foo"}}}
    assert [{"value": "foo"}] == salt.utils.data.get_value(data, "a:b:c")


def test_get_value_placeholder_dict():
    data = {"a": {"b": {"name": "foo"}, "c": {"name": "bar"}}}
    assert [
        {"value": "foo", "id": "b"},
        {"value": "bar", "id": "c"},
    ] == salt.utils.data.get_value(data, "a:{id}:name")


def test_get_value_placeholder_list():
    data = {"a": [{"name": "foo"}, {"name": "bar"}]}
    assert [
        {"value": "foo", "id": 0},
        {"value": "bar", "id": 1},
    ] == salt.utils.data.get_value(data, "a:{id}:name")


def test_get_value_nested_placeholder():
    data = {
        "a": {
            "b": {"b1": {"name": "foo1"}, "b2": {"name": "foo2"}},
            "c": {"c1": {"name": "bar"}},
        }
    }
    assert [
        {"value": "foo1", "id": "b", "sub": "b1"},
        {"value": "foo2", "id": "b", "sub": "b2"},
        {"value": "bar", "id": "c", "sub": "c1"},
    ] == salt.utils.data.get_value(data, "a:{id}:{sub}:name")


def test_get_value_nested_notfound():
    data = {"a": {"b": {"c": "foo"}}}
    assert [{"value": []}] == salt.utils.data.get_value(data, "a:b:d", [])


def test_get_value_not_found():
    assert [{"value": []}] == salt.utils.data.get_value({}, "a", [])


def test_get_value_none():
    assert [{"value": None}] == salt.utils.data.get_value({"a": None}, "a")


def test_get_value_simple_type_path():
    assert [{"value": []}] == salt.utils.data.get_value({"a": 1024}, "a:b", [])


def test_get_value_None_path():
    assert [{"value": None}] == salt.utils.data.get_value({"a": None}, "a:b", [])

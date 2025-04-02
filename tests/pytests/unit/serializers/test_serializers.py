from textwrap import dedent

import jinja2
import pytest
import yaml as _yaml

import salt.serializers.configparser as configparser
import salt.serializers.json as json
import salt.serializers.msgpack as msgpack
import salt.serializers.tomlmod as tomlmod
import salt.serializers.yaml as yaml
import salt.serializers.yamlex as yamlex
import salt.utils.platform
from salt.serializers import SerializationError
from salt.serializers.yaml import EncryptedString
from salt.utils.odict import OrderedDict

SKIP_MESSAGE = "{} is unavailable, have prerequisites been met?"


@pytest.mark.skipif(json.available is False, reason=SKIP_MESSAGE.format("json"))
def test_serialize_json():
    data = {"foo": "bar"}
    serialized = json.serialize(data)
    assert serialized == '{"foo": "bar"}', serialized

    deserialized = json.deserialize(serialized)
    assert deserialized == data, deserialized


@pytest.mark.skipif(yaml.available is False, reason=SKIP_MESSAGE.format("yaml"))
def test_serialize_yaml():
    data = {"foo": "bar", "encrypted_data": EncryptedString("foo")}
    # The C dumper produces unquoted strings when serializing an
    # EncryptedString, while the non-C dumper produces quoted strings.
    expected = (
        "{encrypted_data: !encrypted foo, foo: bar}"
        if hasattr(_yaml, "CSafeDumper")
        else "{encrypted_data: !encrypted 'foo', foo: bar}"
    )
    serialized = yaml.serialize(data)
    assert serialized == expected, serialized

    deserialized = yaml.deserialize(serialized)
    assert deserialized == data, deserialized


@pytest.mark.skipif(yaml.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_serialize_sls():
    data = {"foo": "bar"}
    serialized = yamlex.serialize(data)
    assert serialized == "{foo: bar}", serialized

    serialized = yamlex.serialize(data, default_flow_style=False)
    assert serialized == "foo: bar", serialized

    deserialized = yamlex.deserialize(serialized)
    assert deserialized == data, deserialized

    serialized = yaml.serialize(data)
    assert serialized == "{foo: bar}", serialized

    deserialized = yaml.deserialize(serialized)
    assert deserialized == data, deserialized

    serialized = yaml.serialize(data, default_flow_style=False)
    assert serialized == "foo: bar", serialized

    deserialized = yaml.deserialize(serialized)
    assert deserialized == data, deserialized


@pytest.mark.skipif(yamlex.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_serialize_complex_sls():
    data = OrderedDict([("foo", 1), ("bar", 2), ("baz", True)])
    serialized = yamlex.serialize(data)
    assert serialized == "{foo: 1, bar: 2, baz: true}", serialized

    deserialized = yamlex.deserialize(serialized)
    assert deserialized == data, deserialized

    serialized = yaml.serialize(data)
    assert serialized == "{bar: 2, baz: true, foo: 1}", serialized

    deserialized = yaml.deserialize(serialized)
    assert deserialized == data, deserialized


@pytest.mark.skipif(yaml.available is False, reason=SKIP_MESSAGE.format("yaml"))
@pytest.mark.skipif(yamlex.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_compare_sls_vs_yaml():
    src = "{foo: 1, bar: 2, baz: {qux: true}}"
    sls_data = yamlex.deserialize(src)
    yml_data = yaml.deserialize(src)

    # ensure that sls & yaml have the same base
    assert isinstance(sls_data, dict)
    assert isinstance(yml_data, dict)
    assert sls_data == yml_data

    # ensure that sls is ordered, while yaml not
    assert isinstance(sls_data, OrderedDict)
    assert not isinstance(yml_data, OrderedDict)


@pytest.mark.skipif(yaml.available is False, reason=SKIP_MESSAGE.format("yaml"))
@pytest.mark.skipif(yamlex.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_compare_sls_vs_yaml_with_jinja():
    tpl = "{{ data }}"
    env = jinja2.Environment()
    src = "{foo: 1, bar: 2, baz: {qux: true}}"

    sls_src = env.from_string(tpl).render(data=yamlex.deserialize(src))
    yml_src = env.from_string(tpl).render(data=yaml.deserialize(src))

    sls_data = yamlex.deserialize(sls_src)
    yml_data = yaml.deserialize(yml_src)

    # ensure that sls & yaml have the same base
    assert isinstance(sls_data, dict)
    assert isinstance(yml_data, dict)
    # The below has been commented out because something the loader test
    # is modifying the yaml renderer to render things to unicode. Without
    # running the loader test, the below passes. Even reloading the module
    # from disk does not reset its internal state (per the Python docs).
    ##
    # assert sls_data == yml_data

    # ensure that sls is ordered, while yaml not
    assert isinstance(sls_data, OrderedDict)
    assert not isinstance(yml_data, OrderedDict)

    # prove that yaml does not handle well with OrderedDict
    # while sls is jinja friendly.
    obj = OrderedDict([("foo", 1), ("bar", 2), ("baz", {"qux": True})])

    sls_obj = yamlex.deserialize(yamlex.serialize(obj))
    try:
        yml_obj = yaml.deserialize(yaml.serialize(obj))
    except SerializationError:
        # BLAAM! yaml was unable to serialize OrderedDict,
        # but it's not the purpose of the current test.
        yml_obj = obj.copy()

    sls_src = env.from_string(tpl).render(data=sls_obj)
    yml_src = env.from_string(tpl).render(data=yml_obj)

    final_obj = yaml.deserialize(sls_src)
    assert obj == final_obj

    # BLAAM! yml_src is not valid !
    final_obj = OrderedDict(yaml.deserialize(yml_src))
    assert obj != final_obj, f"Objects matched! {obj} == {final_obj}"


@pytest.mark.skipif(yamlex.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_sls_aggregate():
    src = dedent(
        """
        a: lol
        foo: !aggregate hello
        bar: !aggregate [1, 2, 3]
        baz: !aggregate
          a: 42
          b: 666
          c: the beast
    """
    ).strip()

    # test that !aggregate is correctly parsed
    sls_obj = yamlex.deserialize(src)
    assert sls_obj == {
        "a": "lol",
        "foo": ["hello"],
        "bar": [1, 2, 3],
        "baz": {"a": 42, "b": 666, "c": "the beast"},
    }, sls_obj

    assert (
        dedent(
            """
        a: lol
        foo: [hello]
        bar: [1, 2, 3]
        baz: {a: 42, b: 666, c: the beast}
    """
        ).strip()
        == yamlex.serialize(sls_obj)
    ), sls_obj

    # test that !aggregate aggregates scalars
    src = dedent(
        """
        placeholder: !aggregate foo
        placeholder: !aggregate bar
        placeholder: !aggregate baz
    """
    ).strip()

    sls_obj = yamlex.deserialize(src)
    assert sls_obj == {"placeholder": ["foo", "bar", "baz"]}, sls_obj

    # test that !aggregate aggregates lists
    src = dedent(
        """
        placeholder: !aggregate foo
        placeholder: !aggregate [bar, baz]
        placeholder: !aggregate []
        placeholder: !aggregate ~
    """
    ).strip()

    sls_obj = yamlex.deserialize(src)
    assert sls_obj == {"placeholder": ["foo", "bar", "baz"]}, sls_obj

    # test that !aggregate aggregates dicts
    src = dedent(
        """
        placeholder: !aggregate {foo: 42}
        placeholder: !aggregate {bar: null}
        placeholder: !aggregate {baz: inga}
    """
    ).strip()

    sls_obj = yamlex.deserialize(src)
    assert sls_obj == {"placeholder": {"foo": 42, "bar": None, "baz": "inga"}}, sls_obj

    # test that !aggregate aggregates deep dicts
    src = dedent(
        """
        placeholder: {foo: !aggregate {foo: 42}}
        placeholder: {foo: !aggregate {bar: null}}
        placeholder: {foo: !aggregate {baz: inga}}
    """
    ).strip()

    sls_obj = yamlex.deserialize(src)
    assert sls_obj == {
        "placeholder": {"foo": {"foo": 42, "bar": None, "baz": "inga"}}
    }, sls_obj

    # test that {foo: !aggregate bar} and {!aggregate foo: bar}
    # are roughly equivalent.
    src = dedent(
        """
        placeholder: {!aggregate foo: {foo: 42}}
        placeholder: {!aggregate foo: {bar: null}}
        placeholder: {!aggregate foo: {baz: inga}}
    """
    ).strip()

    sls_obj = yamlex.deserialize(src)
    assert sls_obj == {
        "placeholder": {"foo": {"foo": 42, "bar": None, "baz": "inga"}}
    }, sls_obj


@pytest.mark.skipif(yamlex.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_sls_reset():
    src = dedent(
        """
        placeholder: {!aggregate foo: {foo: 42}}
        placeholder: {!aggregate foo: {bar: null}}
        !reset placeholder: {!aggregate foo: {baz: inga}}
    """
    ).strip()

    sls_obj = yamlex.deserialize(src)
    assert sls_obj == {"placeholder": {"foo": {"baz": "inga"}}}, sls_obj


@pytest.mark.skipif(yamlex.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_sls_repr():
    """
    Ensure that obj __repr__ and __str__ methods are yaml friendly.
    """

    def convert(obj):
        return yamlex.deserialize(yamlex.serialize(obj))

    sls_obj = convert(OrderedDict([("foo", "bar"), ("baz", "qux")]))

    # ensure that repr and str are yaml friendly
    assert str(sls_obj) == "{foo: bar, baz: qux}"
    assert repr(sls_obj) == "{foo: bar, baz: qux}"

    # ensure that repr and str are already quoted
    assert str(sls_obj["foo"]) == '"bar"'
    assert repr(sls_obj["foo"]) == '"bar"'


@pytest.mark.skipif(yamlex.available is False, reason=SKIP_MESSAGE.format("sls"))
def test_sls_micking_file_merging():
    def convert(obj):
        return yamlex.deserialize(yamlex.serialize(obj))

    # let say that we have 2 pillar files

    src1 = dedent(
        """
        a: first
        b: !aggregate first
        c:
          subkey1: first
          subkey2: !aggregate first
    """
    ).strip()

    src2 = dedent(
        """
        a: second
        b: !aggregate second
        c:
          subkey2: !aggregate second
          subkey3: second
    """
    ).strip()

    sls_obj1 = yamlex.deserialize(src1)
    sls_obj2 = yamlex.deserialize(src2)
    sls_obj3 = yamlex.merge_recursive(sls_obj1, sls_obj2)

    assert sls_obj3 == {
        "a": "second",
        "b": ["first", "second"],
        "c": {"subkey2": ["first", "second"], "subkey3": "second"},
    }, sls_obj3


@pytest.mark.skipif(msgpack.available is False, reason=SKIP_MESSAGE.format("msgpack"))
def test_msgpack():
    data = OrderedDict([("foo", 1), ("bar", 2), ("baz", True)])
    serialized = msgpack.serialize(data)
    deserialized = msgpack.deserialize(serialized)
    assert deserialized == data, deserialized


@pytest.mark.skip("Great module migration")
def test_serialize_python():
    data = {"foo": "bar"}
    serialized = python.serialize(data)  # pylint: disable=undefined-variable
    expected = repr({"foo": "bar"})
    assert serialized == expected, serialized


@pytest.mark.skipif(
    configparser.available is False, reason=SKIP_MESSAGE.format("configparser")
)
def test_configparser():
    data = {"foo": {"bar": "baz"}}
    # configparser appends empty lines
    serialized = configparser.serialize(data).strip()
    assert serialized == "[foo]\nbar = baz", serialized

    deserialized = configparser.deserialize(serialized)
    assert deserialized == data, deserialized


@pytest.mark.skipif(tomlmod.HAS_TOML is False, reason=SKIP_MESSAGE.format("toml"))
def test_serialize_toml():
    data = {"foo": "bar"}
    serialized = tomlmod.serialize(data)
    assert serialized == 'foo = "bar"\n', serialized

    deserialized = tomlmod.deserialize(serialized)
    assert deserialized == data, deserialized


@pytest.mark.skip("Great module migration")
def test_serialize_plist():
    data = {"foo": "bar"}
    serialized = plist.serialize(data)  # pylint: disable=undefined-variable
    expected = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
        b' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        b'<plist version="1.0">\n'
        b"<dict>\n"
        b"\t<key>foo</key>\n"
        b"\t<string>bar</string>\n"
        b"</dict>\n"
        b"</plist>\n"
    )
    assert serialized == expected, serialized

    deserialized = plist.deserialize(serialized)  # pylint: disable=undefined-variable
    assert deserialized == data, deserialized


@pytest.mark.skip("Great module migration")
def test_serialize_binary_plist():
    data = {"foo": "bar"}
    serialized = plist.serialize(  # pylint: disable=undefined-variable
        data, fmt="FMT_BINARY"
    )

    deserialized = plist.deserialize(serialized)  # pylint: disable=undefined-variable
    assert deserialized == data, deserialized


@pytest.mark.skip("Great module migration")
def test_serialize_keyvalue():
    data = {"foo": "bar baz"}
    serialized = keyvalue.serialize(data)  # pylint: disable=undefined-variable
    assert serialized == "foo=bar baz", serialized

    deserialized = keyvalue.deserialize(  # pylint: disable=undefined-variable
        serialized
    )
    assert deserialized == data, deserialized


@pytest.mark.skip("Great module migration")
def test_serialize_keyvalue_quoting():
    data = {"foo": "bar baz"}
    serialized = keyvalue.serialize(  # pylint: disable=undefined-variable
        data, quoting=True
    )
    assert serialized == "foo='bar baz'", serialized

    deserialized = keyvalue.deserialize(  # pylint: disable=undefined-variable
        serialized, quoting=False
    )
    assert deserialized == data, deserialized


@pytest.mark.skip("Great module migration")
def test_serialize_keyvalue_separator():
    data = {"foo": "bar baz"}
    serialized = keyvalue.serialize(  # pylint: disable=undefined-variable
        data, separator=" = "
    )
    assert serialized == "foo = bar baz", serialized

    deserialized = keyvalue.deserialize(  # pylint: disable=undefined-variable
        serialized, separator=" = "
    )
    assert deserialized == data, deserialized


@pytest.mark.skip("Great module migration")
def test_serialize_keyvalue_list_of_lists():
    if salt.utils.platform.is_windows():
        linend = "\r\n"
    else:
        linend = "\n"
    data = [["foo", "bar baz"], ["salt", "rocks"]]
    expected = {"foo": "bar baz", "salt": "rocks"}
    serialized = keyvalue.serialize(data)  # pylint: disable=undefined-variable
    assert serialized == f"foo=bar baz{linend}salt=rocks", serialized

    deserialized = keyvalue.deserialize(  # pylint: disable=undefined-variable
        serialized
    )
    assert deserialized == expected, deserialized

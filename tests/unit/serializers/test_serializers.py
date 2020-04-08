# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

from textwrap import dedent

# Import 3rd party libs
import jinja2

# Import salt libs
import salt.serializers.configparser as configparser
import salt.serializers.json as json
import salt.serializers.msgpack as msgpack
import salt.serializers.python as python
import salt.serializers.toml as toml
import salt.serializers.yaml as yaml
import salt.serializers.yamlex as yamlex
import yaml as _yaml  # future lint: disable=blacklisted-import
from salt.ext import six
from salt.serializers import SerializationError
from salt.serializers.yaml import EncryptedString
from salt.utils.odict import OrderedDict

# Import test support libs
from tests.support.helpers import flaky

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf

SKIP_MESSAGE = "%s is unavailable, have prerequisites been met?"


@flaky(condition=six.PY3)
class TestSerializers(TestCase):
    @skipIf(not json.available, SKIP_MESSAGE % "json")
    def test_serialize_json(self):
        data = {"foo": "bar"}
        serialized = json.serialize(data)
        assert serialized == '{"foo": "bar"}', serialized

        deserialized = json.deserialize(serialized)
        assert deserialized == data, deserialized

    @skipIf(not yaml.available, SKIP_MESSAGE % "yaml")
    def test_serialize_yaml(self):
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

    @skipIf(not yaml.available, SKIP_MESSAGE % "sls")
    def test_serialize_sls(self):
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

    @skipIf(not yamlex.available, SKIP_MESSAGE % "sls")
    def test_serialize_complex_sls(self):
        data = OrderedDict([("foo", 1), ("bar", 2), ("baz", True)])
        serialized = yamlex.serialize(data)
        assert serialized == "{foo: 1, bar: 2, baz: true}", serialized

        deserialized = yamlex.deserialize(serialized)
        assert deserialized == data, deserialized

        serialized = yaml.serialize(data)
        assert serialized == "{bar: 2, baz: true, foo: 1}", serialized

        deserialized = yaml.deserialize(serialized)
        assert deserialized == data, deserialized

    @skipIf(not yaml.available, SKIP_MESSAGE % "yaml")
    @skipIf(not yamlex.available, SKIP_MESSAGE % "sls")
    def test_compare_sls_vs_yaml(self):
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

    @skipIf(not yaml.available, SKIP_MESSAGE % "yaml")
    @skipIf(not yamlex.available, SKIP_MESSAGE % "sls")
    @skipIf(six.PY3, "Flaky on Python 3.")
    def test_compare_sls_vs_yaml_with_jinja(self):
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
        assert obj != final_obj, "Objects matched! {} == {}".format(obj, final_obj)

    @skipIf(not yamlex.available, SKIP_MESSAGE % "sls")
    def test_sls_aggregate(self):
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
        assert sls_obj == {
            "placeholder": {"foo": 42, "bar": None, "baz": "inga"}
        }, sls_obj

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

    @skipIf(not yamlex.available, SKIP_MESSAGE % "sls")
    def test_sls_reset(self):
        src = dedent(
            """
            placeholder: {!aggregate foo: {foo: 42}}
            placeholder: {!aggregate foo: {bar: null}}
            !reset placeholder: {!aggregate foo: {baz: inga}}
        """
        ).strip()

        sls_obj = yamlex.deserialize(src)
        assert sls_obj == {"placeholder": {"foo": {"baz": "inga"}}}, sls_obj

    @skipIf(not yamlex.available, SKIP_MESSAGE % "sls")
    def test_sls_repr(self):
        """
        Ensure that obj __repr__ and __str__ methods are yaml friendly.
        """

        def convert(obj):
            return yamlex.deserialize(yamlex.serialize(obj))

        sls_obj = convert(OrderedDict([("foo", "bar"), ("baz", "qux")]))

        # ensure that repr and str are yaml friendly
        assert sls_obj.__str__() == "{foo: bar, baz: qux}"
        assert sls_obj.__repr__() == "{foo: bar, baz: qux}"

        # ensure that repr and str are already quoted
        assert sls_obj["foo"].__str__() == '"bar"'
        assert sls_obj["foo"].__repr__() == '"bar"'

    @skipIf(not yamlex.available, SKIP_MESSAGE % "sls")
    def test_sls_micking_file_merging(self):
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

    @skipIf(not msgpack.available, SKIP_MESSAGE % "msgpack")
    def test_msgpack(self):
        data = OrderedDict([("foo", 1), ("bar", 2), ("baz", True)])
        serialized = msgpack.serialize(data)
        deserialized = msgpack.deserialize(serialized)
        assert deserialized == data, deserialized

    @skipIf(not python.available, SKIP_MESSAGE % "python")
    def test_serialize_python(self):
        data = {"foo": "bar"}
        serialized = python.serialize(data)
        expected = repr({"foo": "bar"})
        assert serialized == expected, serialized

    @skipIf(not configparser.available, SKIP_MESSAGE % "configparser")
    def test_configparser(self):
        data = {"foo": {"bar": "baz"}}
        # configparser appends empty lines
        serialized = configparser.serialize(data).strip()
        assert serialized == "[foo]\nbar = baz", serialized

        deserialized = configparser.deserialize(serialized)
        assert deserialized == data, deserialized

    @skipIf(not toml.available, SKIP_MESSAGE % "toml")
    def test_serialize_toml(self):
        data = {"foo": "bar"}
        serialized = toml.serialize(data)
        assert serialized == 'foo = "bar"\n', serialized

        deserialized = toml.deserialize(serialized)
        assert deserialized == data, deserialized

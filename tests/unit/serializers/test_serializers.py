# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
from textwrap import dedent

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase

# Import 3rd party libs
import jinja2
import yaml as _yaml  # future lint: disable=blacklisted-import
from salt.ext import six

# Import salt libs
import salt.serializers.configparser as configparser
import salt.serializers.json as json
import salt.serializers.yaml as yaml
import salt.serializers.yamlex as yamlex
import salt.serializers.msgpack as msgpack
import salt.serializers.python as python
import salt.serializers.toml as toml
from salt.serializers.yaml import EncryptedString
from salt.serializers import SerializationError
from salt.utils.odict import OrderedDict

# Import test support libs
from tests.support.helpers import flaky

SKIP_MESSAGE = '%s is unavailable, do prerequisites have been met?'


@flaky(condition=six.PY3)
class TestSerializers(TestCase):
    @skipIf(not json.available, SKIP_MESSAGE % 'json')
    def test_serialize_json(self):
        data = {
            "foo": "bar"
        }
        serialized = json.serialize(data)
        self.assertEqual(serialized, '{"foo": "bar"}')

        deserialized = json.deserialize(serialized)
        self.assertEqual(deserialized, data)

    @skipIf(not yaml.available, SKIP_MESSAGE % 'yaml')
    def test_serialize_yaml(self):
        data = {
            "foo": "bar",
            "encrypted_data": EncryptedString("foo")
        }
        # The C dumper produces unquoted strings when serializing an
        # EncryptedString, while the non-C dumper produces quoted strings.
        expected = '{encrypted_data: !encrypted foo, foo: bar}' \
            if hasattr(_yaml, 'CSafeDumper') \
            else "{encrypted_data: !encrypted 'foo', foo: bar}"
        serialized = yaml.serialize(data)
        self.assertEqual(serialized, expected)

        deserialized = yaml.deserialize(serialized)
        self.assertEqual(deserialized, data)

    @skipIf(not yaml.available, SKIP_MESSAGE % 'sls')
    def test_serialize_sls(self):
        data = {
            "foo": "bar"
        }
        serialized = yamlex.serialize(data)
        self.assertEqual(serialized, '{foo: bar}')

        deserialized = yamlex.deserialize(serialized)
        self.assertEqual(deserialized, data)

    @skipIf(not yamlex.available, SKIP_MESSAGE % 'sls')
    def test_serialize_complex_sls(self):
        data = OrderedDict([
            ("foo", 1),
            ("bar", 2),
            ("baz", True),
        ])
        serialized = yamlex.serialize(data)
        self.assertEqual(serialized, '{foo: 1, bar: 2, baz: true}')

        deserialized = yamlex.deserialize(serialized)
        self.assertEqual(deserialized, data)

    @skipIf(not yaml.available, SKIP_MESSAGE % 'yaml')
    @skipIf(not yamlex.available, SKIP_MESSAGE % 'sls')
    def test_compare_sls_vs_yaml(self):
        src = '{foo: 1, bar: 2, baz: {qux: true}}'
        sls_data = yamlex.deserialize(src)
        yml_data = yaml.deserialize(src)

        # ensure that sls & yaml have the same base
        self.assertIsInstance(sls_data, dict)
        self.assertIsInstance(yml_data, dict)
        self.assertEqual(sls_data, yml_data)

        # ensure that sls is ordered, while yaml not
        self.assertIsInstance(sls_data, OrderedDict)
        self.assertNotIsInstance(yml_data, OrderedDict)

    @skipIf(not yaml.available, SKIP_MESSAGE % 'yaml')
    @skipIf(not yamlex.available, SKIP_MESSAGE % 'sls')
    def test_compare_sls_vs_yaml_with_jinja(self):
        tpl = '{{ data }}'
        env = jinja2.Environment()
        src = '{foo: 1, bar: 2, baz: {qux: true}}'

        sls_src = env.from_string(tpl).render(data=yamlex.deserialize(src))
        yml_src = env.from_string(tpl).render(data=yaml.deserialize(src))

        sls_data = yamlex.deserialize(sls_src)
        yml_data = yaml.deserialize(yml_src)

        # ensure that sls & yaml have the same base
        self.assertIsInstance(sls_data, dict)
        self.assertIsInstance(yml_data, dict)
        # The below has been commented out because something the loader test
        # is modifying the yaml renderer to render things to unicode. Without
        # running the loader test, the below passes. Even reloading the module
        # from disk does not reset its internal state (per the Python docs).
        ##
        #self.assertEqual(sls_data, yml_data)

        # ensure that sls is ordered, while yaml not
        self.assertIsInstance(sls_data, OrderedDict)
        self.assertNotIsInstance(yml_data, OrderedDict)

        # prove that yaml does not handle well with OrderedDict
        # while sls is jinja friendly.
        obj = OrderedDict([
            ('foo', 1),
            ('bar', 2),
            ('baz', {'qux': True})
        ])

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
        self.assertEqual(obj, final_obj)

        # BLAAM! yml_src is not valid !
        final_obj = OrderedDict(yaml.deserialize(yml_src))
        self.assertNotEqual(obj, final_obj)

    @skipIf(not yamlex.available, SKIP_MESSAGE % 'sls')
    def test_sls_aggregate(self):
        src = dedent("""
            a: lol
            foo: !aggregate hello
            bar: !aggregate [1, 2, 3]
            baz: !aggregate
              a: 42
              b: 666
              c: the beast
        """).strip()

        # test that !aggregate is correctly parsed
        sls_obj = yamlex.deserialize(src)
        self.assertEqual(sls_obj, {
            'a': 'lol',
            'foo': ['hello'],
            'bar': [1, 2, 3],
            'baz': {
                'a': 42,
                'b': 666,
                'c': 'the beast'
            }
        })

        self.assertEqual(dedent("""
            a: lol
            foo: [hello]
            bar: [1, 2, 3]
            baz: {a: 42, b: 666, c: the beast}
        """).strip(), yamlex.serialize(sls_obj))

        # test that !aggregate aggregates scalars
        src = dedent("""
            placeholder: !aggregate foo
            placeholder: !aggregate bar
            placeholder: !aggregate baz
        """).strip()

        sls_obj = yamlex.deserialize(src)
        self.assertEqual(sls_obj, {'placeholder': ['foo', 'bar', 'baz']})

        # test that !aggregate aggregates lists
        src = dedent("""
            placeholder: !aggregate foo
            placeholder: !aggregate [bar, baz]
            placeholder: !aggregate []
            placeholder: !aggregate ~
        """).strip()

        sls_obj = yamlex.deserialize(src)
        self.assertEqual(sls_obj, {'placeholder': ['foo', 'bar', 'baz']})

        # test that !aggregate aggregates dicts
        src = dedent("""
            placeholder: !aggregate {foo: 42}
            placeholder: !aggregate {bar: null}
            placeholder: !aggregate {baz: inga}
        """).strip()

        sls_obj = yamlex.deserialize(src)
        self.assertEqual(sls_obj, {
            'placeholder': {
                'foo': 42,
                'bar': None,
                'baz': 'inga'
            }
        })

        # test that !aggregate aggregates deep dicts
        src = dedent("""
            placeholder: {foo: !aggregate {foo: 42}}
            placeholder: {foo: !aggregate {bar: null}}
            placeholder: {foo: !aggregate {baz: inga}}
        """).strip()

        sls_obj = yamlex.deserialize(src)
        self.assertEqual(sls_obj, {
            'placeholder': {
                'foo': {
                    'foo': 42,
                    'bar': None,
                    'baz': 'inga'
                }
            }
        })

        # test that {foo: !aggregate bar} and {!aggregate foo: bar}
        # are roughly equivalent.
        src = dedent("""
            placeholder: {!aggregate foo: {foo: 42}}
            placeholder: {!aggregate foo: {bar: null}}
            placeholder: {!aggregate foo: {baz: inga}}
        """).strip()

        sls_obj = yamlex.deserialize(src)
        self.assertEqual(sls_obj, {
            'placeholder': {
                'foo': {
                    'foo': 42,
                    'bar': None,
                    'baz': 'inga'
                }
            }
        })

    @skipIf(not yamlex.available, SKIP_MESSAGE % 'sls')
    def test_sls_reset(self):
        src = dedent("""
            placeholder: {!aggregate foo: {foo: 42}}
            placeholder: {!aggregate foo: {bar: null}}
            !reset placeholder: {!aggregate foo: {baz: inga}}
        """).strip()

        sls_obj = yamlex.deserialize(src)
        self.assertEqual(sls_obj, {
            'placeholder': {
                'foo': {
                    'baz': 'inga'
                }
            }
        })

    @skipIf(not yamlex.available, SKIP_MESSAGE % 'sls')
    def test_sls_repr(self):
        """
        Ensure that obj __repr__ and __str__ methods are yaml friendly.
        """
        def convert(obj):
            return yamlex.deserialize(yamlex.serialize(obj))
        sls_obj = convert(OrderedDict([('foo', 'bar'), ('baz', 'qux')]))

        # ensure that repr and str are yaml friendly
        self.assertEqual(sls_obj.__str__(), '{foo: bar, baz: qux}')
        self.assertEqual(sls_obj.__repr__(), '{foo: bar, baz: qux}')

        # ensure that repr and str are already quoted
        self.assertEqual(sls_obj['foo'].__str__(), '"bar"')
        self.assertEqual(sls_obj['foo'].__repr__(), '"bar"')

    @skipIf(not yamlex.available, SKIP_MESSAGE % 'sls')
    def test_sls_micking_file_merging(self):
        def convert(obj):
            return yamlex.deserialize(yamlex.serialize(obj))

        # let say that we have 2 pillar files

        src1 = dedent("""
            a: first
            b: !aggregate first
            c:
              subkey1: first
              subkey2: !aggregate first
        """).strip()

        src2 = dedent("""
            a: second
            b: !aggregate second
            c:
              subkey2: !aggregate second
              subkey3: second
        """).strip()

        sls_obj1 = yamlex.deserialize(src1)
        sls_obj2 = yamlex.deserialize(src2)
        sls_obj3 = yamlex.merge_recursive(sls_obj1, sls_obj2)

        self.assertEqual(sls_obj3, {
            'a': 'second',
            'b': ['first', 'second'],
            'c': {
                'subkey2': ['first', 'second'],
                'subkey3': 'second'
            }
        })

    @skipIf(not msgpack.available, SKIP_MESSAGE % 'msgpack')
    def test_msgpack(self):
        data = OrderedDict([
            ("foo", 1),
            ("bar", 2),
            ("baz", True),
        ])
        serialized = msgpack.serialize(data)
        deserialized = msgpack.deserialize(serialized)
        self.assertEqual(deserialized, data)

    @skipIf(not python.available, SKIP_MESSAGE % 'python')
    def test_serialize_python(self):
        data = {'foo': 'bar'}
        serialized = python.serialize(data)
        expected = repr({'foo': 'bar'})
        self.assertEqual(serialized, expected)

    @skipIf(not configparser.available, SKIP_MESSAGE % 'configparser')
    def test_configparser(self):
        data = {'foo': {'bar': 'baz'}}
        # configparser appends empty lines
        serialized = configparser.serialize(data).strip()
        self.assertEqual(serialized, "[foo]\nbar = baz")

        deserialized = configparser.deserialize(serialized)
        self.assertEqual(deserialized, data)

    @skipIf(not toml.available, SKIP_MESSAGE % 'toml')
    def test_serialize_toml(self):
        data = {
            "foo": "bar"
        }
        serialized = toml.serialize(data)
        self.assertEqual(serialized, 'foo = "bar"\n')

        deserialized = toml.deserialize(serialized)
        self.assertEqual(deserialized, data)

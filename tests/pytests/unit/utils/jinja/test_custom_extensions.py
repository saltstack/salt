"""
Tests for salt.utils.jinja
"""

import ast
import itertools
import os
import pprint
import re

import pytest
from jinja2 import DictLoader, Environment, exceptions

import salt.loader

# dateutils is needed so that the strftime jinja filter is loaded
import salt.modules.match as match
import salt.utils.dateutils  # pylint: disable=unused-import
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml
from salt.exceptions import SaltRenderError
from salt.utils.decorators.jinja import JinjaFilter
from salt.utils.jinja import SerializerExtension, ensure_sequence_filter
from salt.utils.odict import OrderedDict
from salt.utils.templates import render_jinja_tmpl

try:
    import timelib  # pylint: disable=W0611

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False


@pytest.fixture
def minion_opts(tmp_path, minion_opts):
    minion_opts.update(
        {
            "cachedir": str(tmp_path / "jinja-template-cache"),
            "file_buffer_size": 1048576,
            "file_client": "local",
            "file_ignore_regex": None,
            "file_ignore_glob": None,
            "file_roots": {"test": [str(tmp_path / "templates")]},
            "pillar_roots": {"test": [str(tmp_path / "templates")]},
            "fileserver_backend": ["roots"],
            "extension_modules": os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "extmods"
            ),
        }
    )
    return minion_opts


@pytest.fixture()
def configure_loader_modules(minion_opts):
    return {match: {"__opts__": minion_opts}}


@pytest.fixture
def local_salt():
    return {}


def test_regex_escape():
    dataset = "foo?:.*/\\bar"
    env = Environment(extensions=[SerializerExtension])
    env.filters.update(JinjaFilter.salt_jinja_filters)
    rendered = env.from_string("{{ dataset|regex_escape }}").render(dataset=dataset)
    assert rendered == re.escape(dataset)


def test_unique_string():
    dataset = "foo"
    unique = set(dataset)
    env = Environment(extensions=[SerializerExtension])
    env.filters.update(JinjaFilter.salt_jinja_filters)
    rendered = (
        env.from_string("{{ dataset|unique }}")
        .render(dataset=dataset)
        .strip("'{}")
        .split("', '")
    )
    assert sorted(rendered) == sorted(list(unique))


def test_unique_tuple():
    dataset = ("foo", "foo", "bar")
    unique = set(dataset)
    env = Environment(extensions=[SerializerExtension])
    env.filters.update(JinjaFilter.salt_jinja_filters)
    rendered = (
        env.from_string("{{ dataset|unique }}")
        .render(dataset=dataset)
        .strip("'{}")
        .split("', '")
    )
    assert sorted(rendered) == sorted(list(unique))


def test_unique_list():
    dataset = ["foo", "foo", "bar"]
    unique = ["foo", "bar"]
    env = Environment(extensions=[SerializerExtension])
    env.filters.update(JinjaFilter.salt_jinja_filters)
    rendered = (
        env.from_string("{{ dataset|unique }}")
        .render(dataset=dataset)
        .strip("'[]")
        .split("', '")
    )
    assert rendered == unique


def test_serialize_json():
    dataset = {"foo": True, "bar": 42, "baz": [1, 2, 3], "qux": 2.0}
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string("{{ dataset|json }}").render(dataset=dataset)
    assert dataset == salt.utils.json.loads(rendered)


def test_serialize_yaml():
    dataset = {
        "foo": True,
        "bar": 42,
        "baz": [1, 2, 3],
        "qux": 2.0,
        "spam": OrderedDict([("foo", OrderedDict([("bar", "baz"), ("qux", 42)]))]),
    }
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string("{{ dataset|yaml }}").render(dataset=dataset)
    assert dataset == salt.utils.yaml.safe_load(rendered)


def test_serialize_yaml_str():
    dataset = "str value"
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string("{{ dataset|yaml }}").render(dataset=dataset)
    assert dataset == rendered


def test_serialize_yaml_unicode():
    dataset = "str value"
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string("{{ dataset|yaml }}").render(dataset=dataset)
    assert "str value" == rendered


def test_serialize_python():
    dataset = {"foo": True, "bar": 42, "baz": [1, 2, 3], "qux": 2.0}
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string("{{ dataset|python }}").render(dataset=dataset)
    assert rendered == pprint.pformat(dataset)


def test_load_yaml():
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string(
        '{% set document = "{foo: it works}"|load_yaml %}{{ document.foo }}'
    ).render()
    assert rendered == "it works"

    rendered = env.from_string(
        "{% set document = document|load_yaml %}{{ document.foo }}"
    ).render(document="{foo: it works}")
    assert rendered == "it works"

    with pytest.raises((TypeError, exceptions.TemplateRuntimeError)):
        env.from_string(
            "{% set document = document|load_yaml %}{{ document.foo }}"
        ).render(document={"foo": "it works"})


def test_load_tag():
    env = Environment(extensions=[SerializerExtension])

    source = (
        "{{ bar }}, "
        + "{% load_yaml as docu %}{foo: it works, {{ bar }}: baz}{% endload %}"
        + "{{ docu.foo }}"
    )

    rendered = env.from_string(source).render(bar="barred")
    assert rendered == "barred, it works"

    source = (
        '{{ bar }}, {% load_json as docu %}{"foo": "it works", "{{ bar }}":'
        ' "baz"}{% endload %}' + "{{ docu.foo }}"
    )

    rendered = env.from_string(source).render(bar="barred")
    assert rendered == "barred, it works"

    with pytest.raises(exceptions.TemplateSyntaxError):
        env.from_string(
            "{% load_yamle as document %}{foo, bar: it works}{% endload %}"
        ).render()

    with pytest.raises(exceptions.TemplateRuntimeError):
        env.from_string(
            "{% load_json as document %}{foo, bar: it works}{% endload %}"
        ).render()


def test_load_json():
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string(
        """{% set document = '{"foo": "it works"}'|load_json %}{{ document.foo }}"""
    ).render()
    assert rendered == "it works"

    rendered = env.from_string(
        "{% set document = document|load_json %}{{ document.foo }}"
    ).render(document='{"foo": "it works"}')
    assert rendered == "it works"

    # bad quotes
    with pytest.raises(exceptions.TemplateRuntimeError):
        env.from_string("{{ document|load_json }}").render(
            document="{'foo': 'it works'}"
        )

    # not a string
    with pytest.raises(exceptions.TemplateRuntimeError):
        env.from_string("{{ document|load_json }}").render(document={"foo": "it works"})


def test_load_yaml_template():
    loader = DictLoader({"foo": '{bar: "my god is blue", foo: [1, 2, 3]}'})
    env = Environment(extensions=[SerializerExtension], loader=loader)
    rendered = env.from_string('{% import_yaml "foo" as doc %}{{ doc.bar }}').render()
    assert rendered == "my god is blue"

    with pytest.raises(exceptions.TemplateNotFound):
        env.from_string('{% import_yaml "does not exists" as doc %}').render()


def test_load_json_template():
    loader = DictLoader({"foo": '{"bar": "my god is blue", "foo": [1, 2, 3]}'})
    env = Environment(extensions=[SerializerExtension], loader=loader)
    rendered = env.from_string('{% import_json "foo" as doc %}{{ doc.bar }}').render()
    assert rendered == "my god is blue"

    with pytest.raises(exceptions.TemplateNotFound):
        env.from_string('{% import_json "does not exists" as doc %}').render()


def test_load_text_template():
    loader = DictLoader({"foo": "Foo!"})
    env = Environment(extensions=[SerializerExtension], loader=loader)

    rendered = env.from_string('{% import_text "foo" as doc %}{{ doc }}').render()
    assert rendered == "Foo!"

    with pytest.raises(exceptions.TemplateNotFound):
        env.from_string('{% import_text "does not exists" as doc %}').render()


def test_profile():
    env = Environment(extensions=[SerializerExtension])

    source = (
        "{%- profile as 'profile test' %}"
        "{% set var = 'val' %}"
        "{%- endprofile %}"
        "{{ var }}"
    )

    rendered = env.from_string(source).render()
    assert rendered == "val"


def test_catalog():
    loader = DictLoader(
        {
            "doc1": '{bar: "my god is blue"}',
            "doc2": '{% import_yaml "doc1" as local2 %} never exported',
            "doc3": (
                '{% load_yaml as local3 %}{"foo": "it works"}{% endload %} me'
                " neither"
            ),
            "main1": '{% from "doc2" import local2 %}{{ local2.bar }}',
            "main2": '{% from "doc3" import local3 %}{{ local3.foo }}',
            "main3": """
            {% import "doc2" as imported2 %}
            {% import "doc3" as imported3 %}
            {{ imported2.local2.bar }}
        """,
            "main4": """
            {% import "doc2" as imported2 %}
            {% import "doc3" as imported3 %}
            {{ imported3.local3.foo }}
        """,
            "main5": """
            {% from "doc2" import local2 as imported2 %}
            {% from "doc3" import local3 as imported3 %}
            {{ imported2.bar }}
        """,
            "main6": """
            {% from "doc2" import local2 as imported2 %}
            {% from "doc3" import local3 as imported3 %}
            {{ imported3.foo }}
        """,
        }
    )

    env = Environment(extensions=[SerializerExtension], loader=loader)
    rendered = env.get_template("main1").render()
    assert rendered == "my god is blue"

    rendered = env.get_template("main2").render()
    assert rendered == "it works"

    rendered = env.get_template("main3").render().strip()
    assert rendered == "my god is blue"

    rendered = env.get_template("main4").render().strip()
    assert rendered == "it works"

    rendered = env.get_template("main5").render().strip()
    assert rendered == "my god is blue"

    rendered = env.get_template("main6").render().strip()
    assert rendered == "it works"


def test_nested_structures():
    env = Environment(extensions=[SerializerExtension])
    rendered = env.from_string("{{ data }}").render(data="foo")
    assert rendered == "foo"

    data = OrderedDict([("foo", OrderedDict([("bar", "baz"), ("qux", 42)]))])

    rendered = env.from_string("{{ data }}").render(data=data)
    assert rendered == "{'foo': {'bar': 'baz', 'qux': 42}}"

    rendered = env.from_string("{{ data }}").render(
        data=[
            OrderedDict(
                foo="bar",
            ),
            OrderedDict(
                baz=42,
            ),
        ]
    )
    assert rendered == "[{'foo': 'bar'}, {'baz': 42}]"


def test_set_dict_key_value(minion_opts, local_salt):
    """
    Test the `set_dict_key_value` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ {} | set_dict_key_value('foo:bar:baz', 42) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "{'foo': {'bar': {'baz': 42}}}"

    rendered = render_jinja_tmpl(
        "{{ {} | set_dict_key_value('foo.bar.baz', 42, delimiter='.') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "{'foo': {'bar': {'baz': 42}}}"


def test_update_dict_key_value(minion_opts, local_salt):
    """
    Test the `update_dict_key_value` Jinja filter.
    """
    # Use OrderedDicts to avoid random key-order-switches in the rendered string.
    expected = OrderedDict(
        [("bar", OrderedDict([("baz", OrderedDict([("qux", 1), ("quux", 3)]))]))]
    )
    dataset = OrderedDict([("bar", OrderedDict([("baz", OrderedDict([("qux", 1)]))]))])
    dataset_exp = OrderedDict([("quux", 3)])
    rendered = render_jinja_tmpl(
        "{{ foo | update_dict_key_value('bar:baz', exp) }}",
        dict(
            foo=dataset,
            exp=dataset_exp,
            opts=minion_opts,
            saltenv="test",
            salt=local_salt,
        ),
    )
    assert rendered == "{'bar': {'baz': {'qux': 1, 'quux': 3}}}"

    # Test incorrect usage
    for update_with in [42, "foo", [42]]:
        template = "{{ {} | update_dict_key_value('bar:baz', update_with) }}"
        expected = rf"Cannot update {type({})} with a {type(update_with)}."
        with pytest.raises(SaltRenderError, match=expected):
            render_jinja_tmpl(
                template,
                dict(
                    update_with=update_with,
                    opts=minion_opts,
                    saltenv="test",
                    salt=local_salt,
                ),
            )


def test_append_dict_key_value(minion_opts, local_salt):
    """
    Test the `append_dict_key_value` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ {} | append_dict_key_value('foo:bar:baz', 42) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "{'foo': {'bar': {'baz': [42]}}}"

    rendered = render_jinja_tmpl(
        "{{ foo | append_dict_key_value('bar:baz', 42) }}",
        dict(
            foo={"bar": {"baz": [1, 2]}},
            opts=minion_opts,
            saltenv="test",
            salt=local_salt,
        ),
    )
    assert rendered == "{'bar': {'baz': [1, 2, 42]}}"


def test_extend_dict_key_value(minion_opts, local_salt):
    """
    Test the `extend_dict_key_value` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ {} | extend_dict_key_value('foo:bar:baz', [42]) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "{'foo': {'bar': {'baz': [42]}}}"

    rendered = render_jinja_tmpl(
        "{{ foo | extend_dict_key_value('bar:baz', [42, 43]) }}",
        dict(
            foo={"bar": {"baz": [1, 2]}},
            opts=minion_opts,
            saltenv="test",
            salt=local_salt,
        ),
    )
    assert rendered == "{'bar': {'baz': [1, 2, 42, 43]}}"
    # Edge cases
    rendered = render_jinja_tmpl(
        "{{ {} | extend_dict_key_value('foo:bar:baz', 'quux') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "{'foo': {'bar': {'baz': ['q', 'u', 'u', 'x']}}}"
    # Beware! When supplying a dict, the list gets extended with the dict coerced to a list,
    # which will only contain the keys of the dict.
    rendered = render_jinja_tmpl(
        "{{ {} | extend_dict_key_value('foo:bar:baz', {'foo': 'bar'}) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "{'foo': {'bar': {'baz': ['foo']}}}"

    # Test incorrect usage
    template = "{{ {} | extend_dict_key_value('bar:baz', 42) }}"
    expected = rf"Cannot extend {type([])} with a {int}."
    with pytest.raises(SaltRenderError, match=expected):
        render_jinja_tmpl(
            template, dict(opts=minion_opts, saltenv="test", salt=local_salt)
        )


def test_sequence():
    env = Environment()
    env.filters["sequence"] = ensure_sequence_filter

    rendered = env.from_string("{{ data | sequence | length }}").render(data="foo")
    assert rendered == "1"

    rendered = env.from_string("{{ data | sequence | length }}").render(
        data=["foo", "bar"]
    )
    assert rendered == "2"

    rendered = env.from_string("{{ data | sequence | length }}").render(
        data=("foo", "bar")
    )
    assert rendered == "2"

    rendered = env.from_string("{{ data | sequence | length }}").render(
        data={"foo", "bar"}
    )
    assert rendered == "2"

    rendered = env.from_string("{{ data | sequence | length }}").render(
        data={"foo": "bar"}
    )
    assert rendered == "1"


def test_camel_to_snake_case(minion_opts, local_salt):
    """
    Test the `to_snake_case` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'abcdEfghhIjkLmnoP' | to_snake_case }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "abcd_efghh_ijk_lmno_p"


def test_snake_to_camel_case(minion_opts, local_salt):
    """
    Test the `to_camelcase` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'the_fox_jumped_over_the_lazy_dog' | to_camelcase }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "theFoxJumpedOverTheLazyDog"

    rendered = render_jinja_tmpl(
        "{{ 'the_fox_jumped_over_the_lazy_dog' | to_camelcase(uppercamel=True) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "TheFoxJumpedOverTheLazyDog"


def test_is_ip(minion_opts, local_salt):
    """
    Test the `is_ip` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | is_ip }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"

    rendered = render_jinja_tmpl(
        "{{ 'FE80::' | is_ip }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"

    rendered = render_jinja_tmpl(
        "{{ 'random' | is_ip }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"


def test_is_ipv4(minion_opts, local_salt):
    """
    Test the `is_ipv4` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | is_ipv4 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"

    rendered = render_jinja_tmpl(
        "{{ 'FE80::' | is_ipv4 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"

    rendered = render_jinja_tmpl(
        "{{ 'random' | is_ipv4 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"


def test_is_ipv6(minion_opts):
    """
    Test the `is_ipv6` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | is_ipv6 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"

    rendered = render_jinja_tmpl(
        "{{ 'fe80::20d:b9ff:fe01:ea8%eth0' | is_ipv6 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"

    rendered = render_jinja_tmpl(
        "{{ 'FE80::' | is_ipv6 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"

    rendered = render_jinja_tmpl(
        "{{ 'random' | is_ipv6 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"


def test_ipaddr(minion_opts, local_salt):
    """
    Test the `ipaddr` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '::' | ipaddr }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "::"

    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | ipaddr }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "192.168.0.1"

    # provides a list with valid IP addresses only
    rendered = render_jinja_tmpl(
        "{{ ['192.168.0.1', '172.17.17.1', 'foo', 'bar', '::'] | ipaddr | join(',"
        " ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "192.168.0.1, 172.17.17.1, ::"

    # return only multicast addresses
    rendered = render_jinja_tmpl(
        "{{ ['224.0.0.1', 'FF01::1', '::'] | ipaddr(options='multicast') | join(',"
        " ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "224.0.0.1, ff01::1"


def test_ipv4(minion_opts, local_salt):
    """
    Test the `ipv4` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | ipv4 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "192.168.0.1"

    rendered = render_jinja_tmpl(
        "{{ ['192.168.0.1', '172.17.17.1'] | ipv4 | join(', ')}}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "192.168.0.1, 172.17.17.1"

    rendered = render_jinja_tmpl(
        "{{ 'fe80::' | ipv4 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"

    rendered = render_jinja_tmpl(
        "{{ 'random' | ipv4 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"

    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | ipv4(options='lo') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"

    rendered = render_jinja_tmpl(
        "{{ '127.0.0.1' | ipv4(options='lo') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "127.0.0.1"


def test_ipv6(minion_opts, local_salt):
    """
    Test the `ipv6` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | ipv6 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"

    rendered = render_jinja_tmpl(
        "{{ 'random' | ipv6 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"

    # returns the standard format value
    rendered = render_jinja_tmpl(
        "{{ 'FE80:0:0::0' | ipv6 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "fe80::"

    # fe80:: is link local therefore will be returned
    rendered = render_jinja_tmpl(
        "{{ 'fe80::' | ipv6(options='ll') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "fe80::"

    # fe80:: is not loopback
    rendered = render_jinja_tmpl(
        "{{ 'fe80::' | ipv6(options='lo') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"

    # returns only IPv6 addresses in the list
    rendered = render_jinja_tmpl(
        "{{ ['fe80::', '192.168.0.1'] | ipv6 | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "fe80::"

    rendered = render_jinja_tmpl(
        "{{ ['fe80::', '::'] | ipv6 | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "fe80::, ::"


def test_ipwrap(minion_opts, local_salt):
    """
    Test the `ipwrap` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | ipwrap }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "192.168.0.1"

    rendered = render_jinja_tmpl(
        "{{ 'random' | ipwrap }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "random"

    # returns the standard format value
    rendered = render_jinja_tmpl(
        "{{ 'FE80:0:0::0' | ipwrap }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[fe80::]"

    rendered = render_jinja_tmpl(
        "{{ ['fe80::', '::'] | ipwrap | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[fe80::], [::]"

    rendered = render_jinja_tmpl(
        "{{ ['fe80::', 'ham', 'spam', '2001:db8::1', 'eggs', '::'] | ipwrap | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[fe80::], ham, spam, [2001:db8::1], eggs, [::]"

    rendered = render_jinja_tmpl(
        "{{ ('fe80::', 'ham', 'spam', '2001:db8::1', 'eggs', '::') | ipwrap | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[fe80::], ham, spam, [2001:db8::1], eggs, [::]"


def test_network_hosts(minion_opts, local_salt):
    """
    Test the `network_hosts` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1/30' | network_hosts | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "192.168.0.1, 192.168.0.2"


def test_network_size(minion_opts, local_salt):
    """
    Test the `network_size` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1' | network_size }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "1"

    rendered = render_jinja_tmpl(
        "{{ '192.168.0.1/8' | network_size }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "16777216"


@pytest.mark.requires_network
@pytest.mark.parametrize("backend", ["requests", "tornado", "urllib2"])
def test_http_query(minion_opts, local_salt, backend, httpserver):
    """
    Test the `http_query` Jinja filter.
    """
    urls = (
        # These cannot be HTTPS urls since urllib2 chokes on those
        "http://saltproject.io",
        "http://google.com",
        "http://duckduckgo.com",
    )
    response = {
        "backend": backend,
        "body": "Hey, this isn't http://google.com!",
    }
    httpserver.expect_request(f"/{backend}").respond_with_data(
        salt.utils.json.dumps(response), content_type="text/plain"
    )
    rendered = render_jinja_tmpl(
        "{{ '"
        + httpserver.url_for(f"/{backend}")
        + "' | http_query(backend='"
        + backend
        + "') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert isinstance(rendered, str), "Failed with rendered template: {}".format(
        rendered
    )
    dict_reply = ast.literal_eval(rendered)
    assert isinstance(dict_reply, dict), "Failed with rendered template: {}".format(
        rendered
    )
    assert (
        "body" in dict_reply
    ), "'body' not found in request response({}). Rendered template: {!r}".format(
        dict_reply, rendered
    )
    assert isinstance(
        dict_reply["body"], str
    ), f"Failed with rendered template: {rendered}"


def test_to_bool(minion_opts, local_salt):
    """
    Test the `to_bool` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 1 | to_bool }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"

    rendered = render_jinja_tmpl(
        "{{ 'True' | to_bool }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"

    rendered = render_jinja_tmpl(
        "{{ 0 | to_bool }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"

    rendered = render_jinja_tmpl(
        "{{ 'Yes' | to_bool }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"


def test_quote(minion_opts, local_salt):
    """
    Test the `quote` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'random' | quote }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "random"


def test_regex_search(minion_opts, local_salt):
    """
    Test the `regex_search` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'abcdefabcdef' | regex_search('BC(.*)', ignorecase=True) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "('defabcdef',)"  # because search looks only at the beginning


def test_regex_match(minion_opts, local_salt):
    """
    Test the `regex_match` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'abcdefabcdef' | regex_match('BC(.*)', ignorecase=True)}}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"


def test_regex_replace(minion_opts, local_salt):
    """
    Test the `regex_replace` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        r"{{ 'lets replace spaces' | regex_replace('\s+', '__') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "lets__replace__spaces"


def test_uuid(minion_opts, local_salt):
    """
    Test the `uuid` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'random' | uuid }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "3652b285-26ad-588e-a5dc-c2ee65edc804"


def test_min(minion_opts, local_salt):
    """
    Test the `min` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | min }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "1"


def test_max(minion_opts, local_salt):
    """
    Test the `max` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | max }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "3"


def test_avg(minion_opts, local_salt):
    """
    Test the `avg` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | avg }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "2.0"


def test_union(minion_opts, local_salt):
    """
    Test the `union` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | union([2, 3, 4]) | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "1, 2, 3, 4"


def test_intersect(minion_opts, local_salt):
    """
    Test the `intersect` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | intersect([2, 3, 4]) | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "2, 3"


def test_difference(minion_opts, local_salt):
    """
    Test the `difference` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | difference([2, 3, 4]) | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "1"


def test_symmetric_difference(minion_opts, local_salt):
    """
    Test the `symmetric_difference` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | symmetric_difference([2, 3, 4]) | join(', ') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "1, 4"


def test_method_call(minion_opts, local_salt):
    """
    Test the `method_call` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 6|method_call('bit_length') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "3"
    rendered = render_jinja_tmpl(
        "{{ 6.7|method_call('is_integer') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"
    rendered = render_jinja_tmpl(
        "{{ 'absaltba'|method_call('strip', 'ab') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "salt"
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 1, 3, 4]|method_call('index', 1, 1, 3) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "2"

    # have to use `dictsort` to keep test result deterministic
    rendered = render_jinja_tmpl(
        "{{ {}|method_call('fromkeys', ['a', 'b', 'c'], 0)|dictsort }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[('a', 0), ('b', 0), ('c', 0)]"

    # missing object method test
    rendered = render_jinja_tmpl(
        "{{ 6|method_call('bit_width') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "None"


@pytest.mark.skip_on_fips_enabled_platform
def test_md5(minion_opts, local_salt):
    """
    Test the `md5` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'random' | md5 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "7ddf32e17a6ac5ce04a8ecbf782ca509"


def test_sha256(minion_opts, local_salt):
    """
    Test the `sha256` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'random' | sha256 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert (
        rendered == "a441b15fe9a3cf56661190a0b93b9dec7d04127288cc87250967cf3b52894d11"
    )


def test_sha512(minion_opts, local_salt):
    """
    Test the `sha512` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'random' | sha512 }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == str(
        "811a90e1c8e86c7b4c0eef5b2c0bf0ec1b19c4b1b5a242e6455be93787cb473cb7bc"
        "9b0fdeb960d00d5c6881c2094dd63c5c900ce9057255e2a4e271fc25fef1"
    )


def test_hmac(minion_opts, local_salt):
    """
    Test the `hmac` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'random' | hmac('secret', 'blah') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "False"

    rendered = render_jinja_tmpl(
        "{{ 'get salted' | "
        "hmac('shared secret', 'eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ=') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "True"


def test_base64_encode(minion_opts, local_salt):
    """
    Test the `base64_encode` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'random' | base64_encode }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "cmFuZG9t"


def test_base64_decode(minion_opts, local_salt):
    """
    Test the `base64_decode` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ 'cmFuZG9t' | base64_decode }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "random"


def test_json_query(minion_opts, local_salt):
    """
    Test the `json_query` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, 3] | json_query('[1]')}}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "2"


def test_flatten_simple(minion_opts, local_salt):
    """
    Test the `flatten` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, [3]] | flatten }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[1, 2, 3]"


def test_flatten_single_level(minion_opts, local_salt):
    """
    Test the `flatten` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, [None, 3, [4]]] | flatten(levels=1) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[1, 2, 3, [4]]"


def test_flatten_preserve_nulls(minion_opts, local_salt):
    """
    Test the `flatten` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ [1, 2, [None, 3, [4]]] | flatten(preserve_nulls=True) }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "[1, 2, None, 3, 4]"


def test_dict_to_sls_yaml_params(minion_opts, local_salt):
    """
    Test the `dict_to_sls_yaml_params` Jinja filter.
    """
    expected = [
        "- name: donkey",
        "- list:\n  - one\n  - two",
        "- dict:\n    one: two",
        "- nested:\n  - one\n  - two: three",
    ]
    source = (
        "{% set myparams = {'name': 'donkey', 'list': ['one', 'two'], 'dict': {'one': 'two'}, 'nested': ['one', {'two': 'three'}]} %}"
        + "{{ myparams | dict_to_sls_yaml_params }}"
    )
    rendered = render_jinja_tmpl(
        source, dict(opts=minion_opts, saltenv="test", salt=local_salt)
    )
    assert rendered in ["\n".join(combo) for combo in itertools.permutations(expected)]


def test_combinations(minion_opts, local_salt):
    """
    Test the `combinations` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{% for one, two in 'ABCD' | combinations(2) %}{{ one~two }} {% endfor %}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "AB AC AD BC BD CD "


def test_combinations_with_replacement(minion_opts, local_salt):
    """
    Test the `combinations_with_replacement` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{% for one, two in 'ABC' | combinations_with_replacement(2) %}{{ one~two }} {% endfor %}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "AA AB AC BB BC CC "


def test_compress(minion_opts, local_salt):
    """
    Test the `compress` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{% for val in 'ABCDEF' | compress([1,0,1,0,1,1]) %}{{ val }} {% endfor %}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "A C E F "


def test_permutations(minion_opts, local_salt):
    """
    Test the `permutations` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{% for one, two in 'ABCD' | permutations(2) %}{{ one~two }} {% endfor %}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "AB AC AD BA BC BD CA CB CD DA DB DC "


def test_product(minion_opts, local_salt):
    """
    Test the `product` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{% for one, two in 'ABCD' | product('xy') %}{{ one~two }} {% endfor %}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "Ax Ay Bx By Cx Cy Dx Dy "


def test_zip(minion_opts, local_salt):
    """
    Test the `zip` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{% for one, two in 'ABCD' | zip('xy') %}{{ one~two }} {% endfor %}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "Ax By "


def test_zip_longest(minion_opts, local_salt):
    """
    Test the `zip_longest` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{% for one, two in 'ABCD' | zip_longest('xy', fillvalue='-') %}{{ one~two }} {% endfor %}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "Ax By C- D- "


def test_random_sample(minion_opts, local_salt):
    """
    Test the `random_sample` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ ['one', 'two', 'three', 'four'] | random_sample(2, seed='static') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "['four', 'two']"


def test_random_shuffle(minion_opts, local_salt):
    """
    Test the `random_shuffle` Jinja filter.
    """
    rendered = render_jinja_tmpl(
        "{{ ['one', 'two', 'three', 'four'] | random_shuffle(seed='static') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == "['four', 'two', 'three', 'one']"


def test_ifelse(minion_opts, local_salt):
    """
    Test the `ifelse` Jinja global function.
    """
    rendered = render_jinja_tmpl(
        "{{ ifelse('default') }}\n"
        "{{ ifelse('foo*', 'fooval', 'bar*', 'barval', 'default', minion_id='foo03') }}\n"
        "{{ ifelse('foo*', 'fooval', 'bar*', 'barval', 'default', minion_id='bar03') }}\n"
        "{{ ifelse(False, 'fooval', True, 'barval', 'default', minion_id='foo03') }}\n"
        "{{ ifelse('foo*', 'fooval', 'bar*', 'barval', 'default', minion_id='baz03') }}",
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert rendered == ("default\n" "fooval\n" "barval\n" "barval\n" "default")

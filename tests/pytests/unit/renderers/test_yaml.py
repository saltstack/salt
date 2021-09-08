import collections
import textwrap

import pytest
import salt.renderers.yaml as yaml
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {yaml: {}}


def assert_unicode(value):
    """
    Make sure the entire data structure is unicode
    """
    if isinstance(value, str):
        if not isinstance(value, str):
            raise value
    elif isinstance(value, collections.Mapping):
        for k, v in value.items():
            assert_unicode(k)
            assert_unicode(v)
    elif isinstance(value, collections.Iterable):
        for item in value:
            assert_unicode(item)


def assert_matches(ret, expected):
    assert ret == expected
    assert_unicode(ret)


def test_yaml_render_string():
    data = "string"
    result = yaml.render(data)

    assert result == data


def test_yaml_render_unicode():
    data = "!!python/unicode python unicode string"
    result = yaml.render(data)

    assert result == "python unicode string"


def test_yaml_render_old_unicode():
    config = {"use_yamlloader_old": True}
    with patch.dict(yaml.__opts__, config):  # pylint: disable=no-member
        assert_matches(
            yaml.render(
                textwrap.dedent(
                    """\
                foo:
                  a: Д
                  b: {'a': u'\\u0414'}"""
                )
            ),
            {"foo": {"a": "\u0414", "b": {"a": "\u0414"}}},
        )

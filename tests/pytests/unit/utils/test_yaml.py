import textwrap

import pytest
import yaml
from yaml.constructor import ConstructorError

import salt.utils.files
import salt.utils.yaml as salt_yaml
from tests.support.mock import mock_open, patch


def test_dump():
    data = {"foo": "bar"}
    assert salt_yaml.dump(data) == "{foo: bar}\n"
    assert salt_yaml.dump(data, default_flow_style=False) == "foo: bar\n"


def test_safe_dump():
    data = {"foo": "bar"}
    assert salt_yaml.safe_dump(data) == "{foo: bar}\n"
    assert salt_yaml.safe_dump(data, default_flow_style=False) == "foo: bar\n"


def render_yaml(data):
    """
    Takes a YAML string, puts it into a mock file, passes that to the YAML
    SaltYamlSafeLoader and then returns the rendered/parsed YAML data
    """
    with patch("salt.utils.files.fopen", mock_open(read_data=data)) as mocked_file:
        with salt.utils.files.fopen(mocked_file) as mocked_stream:
            return salt_yaml.SaltYamlSafeLoader(mocked_stream).get_data()


def test_load_basics():
    """
    Test parsing an ordinary path
    """
    assert (
        render_yaml(
            textwrap.dedent(
                """\
                    p1:
                      - alpha
                      - beta
                """
            )
        )
        == {"p1": ["alpha", "beta"]}
    )


def test_load_merge():
    """
    Test YAML anchors
    """
    # Simple merge test
    assert (
        render_yaml(
            textwrap.dedent(
                """\
                    p1: &p1
                      v1: alpha
                    p2:
                      <<: *p1
                      v2: beta
                """
            )
        )
        == {"p1": {"v1": "alpha"}, "p2": {"v1": "alpha", "v2": "beta"}}
    )

    # Test that keys/nodes are overwritten
    assert (
        render_yaml(
            textwrap.dedent(
                """\
                    p1: &p1
                      v1: alpha
                    p2:
                      <<: *p1
                      v1: new_alpha
                """
            )
        )
        == {"p1": {"v1": "alpha"}, "p2": {"v1": "new_alpha"}}
    )

    # Test merging of lists
    assert (
        render_yaml(
            textwrap.dedent(
                """\
                    p1: &p1
                      v1: &v1
                        - t1
                        - t2
                    p2:
                      v2: *v1
                """
            )
        )
        == {"p2": {"v2": ["t1", "t2"]}, "p1": {"v1": ["t1", "t2"]}}
    )


def test_load_duplicates():
    """
    Test that duplicates still throw an error
    """
    with pytest.raises(ConstructorError):
        render_yaml(
            textwrap.dedent(
                """\
                    p1: alpha
                    p1: beta
                """
            )
        )

    with pytest.raises(ConstructorError):
        render_yaml(
            textwrap.dedent(
                """\
                    p1: &p1
                      v1: alpha
                    p2:
                      <<: *p1
                      v2: beta
                      v2: betabeta
                """
            )
        )


def test_load_with_plain_scalars():
    """
    Test that plain (i.e. unqoted) string and non-string scalars are
    properly handled
    """
    assert (
        render_yaml(
            textwrap.dedent(
                """\
                    foo:
                      b: {foo: bar, one: 1, list: [1, two, 3]}
                """
            )
        )
        == {"foo": {"b": {"foo": "bar", "one": 1, "list": [1, "two", 3]}}}
    )


def test_load_binary_unpadded():
    """
    Test that !!binary values without base64 padding are accepted.
    Regression test for https://github.com/saltstack/salt/issues/69207
    """
    # 'a1b2c3' is 6 chars; valid only after adding '==' padding
    result = render_yaml("vdata: !!binary a1b2c3")
    assert result == {"vdata": b"\x6b\x56\xf6\x73"}


def test_load_binary_padded():
    """
    Test that !!binary values with correct base64 padding still work.
    """
    result = render_yaml("vdata: !!binary a1b2c3==")
    assert result == {"vdata": b"\x6b\x56\xf6\x73"}


def test_load_binary_invalid():
    """
    Test that invalid data in a !!binary value still raises ConstructorError.

    Non-ASCII characters are used here because they reliably trigger the
    UnicodeEncodeError path across all Python versions. Testing via the
    binascii.Error path is not reliable: Python 3.10 silently discards
    unrecognized ASCII characters in base64 data, while Python 3.14 is
    stricter. The padding fix itself is covered by test_load_binary_unpadded.
    """
    with pytest.raises(ConstructorError):
        render_yaml("vdata: !!binary \xc3\xb1")


def test_not_yaml_monkey_patching():
    if hasattr(yaml, "CSafeLoader"):
        assert yaml.SafeLoader != yaml.CSafeLoader

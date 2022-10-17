import re
import textwrap
import warnings

import pytest
import yaml
from yaml.constructor import ConstructorError

import salt.utils._yaml_common as _yc
import salt.utils.files
import salt.utils.yaml as salt_yaml
from salt.version import SaltStackVersion
from tests.support.mock import mock_open, patch


@pytest.mark.parametrize(
    "yaml_compatibility,want",
    [
        (None, SaltStackVersion(3006)),
        (3005, SaltStackVersion(3006)),
        (3006, SaltStackVersion(3006)),
        ("3006", SaltStackVersion(3006)),
        ("3006.0", SaltStackVersion(3006)),
        ("v3006.0", SaltStackVersion(3006)),
        ("sulfur", SaltStackVersion(3006)),
        ("Sulfur", SaltStackVersion(3006)),
        ("SULFUR", SaltStackVersion(3006)),
        (3007, SaltStackVersion(3007)),
    ],
    indirect=["yaml_compatibility"],
)
def test_compat_ver(yaml_compatibility, want):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=_yc.UnsupportedValueWarning, module=_yc.__name__
        )
        got = _yc.compat_ver()
    assert got == want


@pytest.mark.show_yaml_compatibility_warnings
@pytest.mark.parametrize(
    "yaml_compatibility,want",
    [
        (None, [(FutureWarning, r"behavior will change in version 3007(?:\.0)?")]),
        (
            3005,
            [
                (FutureWarning, r"less than 3007(?:\.0)? will be removed in Salt 3011(?:\.0)?"),
                (_yc.UnsupportedValueWarning, r"minimum supported value 3006(?:\.0)?"),
                (_yc.OverrideNotice, r"3006(?:\.0)?"),
            ],
        ),
        (
            3006,
            [
                (FutureWarning, r"less than 3007(?:\.0)? will be removed in Salt 3011(?:\.0)?"),
                (_yc.OverrideNotice, r"3006(?:\.0)?"),
            ],
        ),
        (3007, [(_yc.OverrideNotice, r"3007(?:\.0)?")]),
    ],
    indirect=["yaml_compatibility"],
)
def test_compat_ver_warnings(yaml_compatibility, want):
    with warnings.catch_warnings(record=True) as got:
        _yc.compat_ver()
    for category, regexp in want:
        found = False
        for warn in got:
            if warn.category is not category:
                continue
            if not re.search(regexp, str(warn.message)):
                continue
            found = True
            break
        assert found, f"no {category.__name__} warning with message matching {regexp!r}; all warnings: {[warn.message for warn in got]!r}"
    assert len(got) == len(want)


def test_dump():
    data = {"foo": "bar"}
    assert salt_yaml.dump(data) == "{foo: bar}\n"
    assert salt_yaml.dump(data, default_flow_style=False) == "foo: bar\n"


def test_safe_dump():
    data = {"foo": "bar"}
    assert salt_yaml.safe_dump(data) == "{foo: bar}\n"
    assert salt_yaml.safe_dump(data, default_flow_style=False) == "foo: bar\n"


@pytest.mark.parametrize(
    "yaml_compatibility,input_dumper,want_dumper",
    [
        (3006, None, None),
        (3006, yaml.Dumper, yaml.Dumper),
        (3007, None, salt_yaml.OrderedDumper),
        (3007, yaml.Dumper, yaml.Dumper),
    ],
    indirect=["yaml_compatibility"],
)
def test_dump_default_dumper(yaml_compatibility, input_dumper, want_dumper):
    with patch.object(yaml, "dump") as mock:
        kwargs = {}
        if input_dumper is not None:
            kwargs["Dumper"] = input_dumper
        salt_yaml.dump([], **kwargs)
        mock.assert_called_once()
        got_kwargs = mock.mock_calls[0].kwargs
        if want_dumper is None:
            assert "Dumper" not in got_kwargs
        else:
            assert got_kwargs["Dumper"] is want_dumper


@pytest.mark.parametrize(
    "yaml_compatibility,want",
    [
        # With v3006, sometimes it indents and sometimes it doesn't depending on
        # whether yaml.CSafeDumper exists on the system.
        (3006, re.compile(r"foo:\n(?:  )?- bar\n")),
        (3007, "foo:\n  - bar\n"),
    ],
    indirect=["yaml_compatibility"],
)
def test_dump_indented(yaml_compatibility, want):
    data = {"foo": ["bar"]}
    got = salt_yaml.dump(
        data,
        Dumper=salt_yaml.IndentedSafeOrderedDumper,
        default_flow_style=False,
    )
    try:
        assert want.fullmatch(got)
    except AttributeError:
        assert got == want


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


def test_not_yaml_monkey_patching():
    if hasattr(yaml, "CSafeLoader"):
        assert yaml.SafeLoader != yaml.CSafeLoader

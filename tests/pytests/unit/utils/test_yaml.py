import collections
import datetime
import random
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


def test_dump_indented():
    data = {"foo": ["bar"]}
    got = salt_yaml.dump(
        data,
        Dumper=salt_yaml.IndentedSafeOrderedDumper,
        default_flow_style=False,
    )
    want = "foo:\n  - bar\n"
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


@pytest.mark.parametrize("dictclass", [dict, collections.OrderedDict])
def test_load_dictclass(dictclass):
    l = salt_yaml.SaltYamlSafeLoader("k1: v1\nk2: v2\n", dictclass=dictclass)
    try:
        d = l.get_single_data()
    finally:
        l.dispose()
    assert isinstance(d, dictclass)
    assert d == dictclass([("k1", "v1"), ("k2", "v2")])


def test_load_omap():
    """Test OrderedDict values via the YAML ``!!omap`` tag.

    This test uses random keys to ensure that iteration order does not
    coincidentally match.  The generated YAML looks like this:

    .. code-block:: yaml

        !!omap
        - k3334244338: 0
        - k3444116829: 1
        - k2072366017: 2
        # ... omitted for brevity ...
        - k1638299831: 19
    """
    # Filter the random keys through a set to avoid duplicates.
    keys = list({f"k{random.getrandbits(32)}" for _ in range(20)})
    # Avoid unintended correlation with set()'s iteration order.
    random.shuffle(keys)
    want_items = [(k, i) for i, k in enumerate(keys)]
    yaml = "!!omap\n" + "".join(f"- {k}: {v}\n" for k, v in want_items)
    got = salt_yaml.load(yaml)
    assert isinstance(got, collections.OrderedDict)
    assert got == collections.OrderedDict(want_items)
    assert list(got.items()) == want_items


def test_load_omap_empty():
    got = salt_yaml.load("!!omap []\n")
    assert isinstance(got, collections.OrderedDict)
    assert got == collections.OrderedDict()
    assert list(got.items()) == []


@pytest.mark.parametrize(
    "input",
    [
        "!!omap {}\n",  # Not a sequence node.
        "!!omap\n- this is not a mapping node\n",
        "!!omap\n- k1: 0\n  k2: multiple entries in mapping node\n",
        "!!omap [{}]\n",  # Mapping node has no entries.
        "!!omap\n- duplicate key: 0\n- duplicate key: 1\n",
    ],
)
def test_load_omap_invalid(input):
    with pytest.raises(ConstructorError):
        salt_yaml.load(input)


def test_load_untagged_omaplike_is_seq():
    # The YAML spec allows the loader to interpret something that looks like an
    # !!omap but doesn't actually have an !!omap tag as an !!omap.  (If the user
    # intends to express a sequence of single-entry maps and not an ordered map,
    # the user must explicitly tag the sequence node with !seq.)  Out of concern
    # for backwards compatibility, and to avoid ambiguity with an empty
    # sequence, implicit !!omap behavior is currently not supported.  That may
    # change in the future, but for now make sure that sequences are not
    # interpreted as ordered maps.
    got = salt_yaml.load("- a: 0\n- b: 1\n")
    assert not isinstance(got, collections.OrderedDict)
    assert got == [{"a": 0}, {"b": 1}]


@pytest.mark.parametrize(
    "input_yaml,want",
    [
        (
            "!!timestamp 2022-10-21T18:16:03.1-04:00",
            datetime.datetime(
                *(2022, 10, 21, 18, 16, 3, 100000),
                tzinfo=datetime.timezone(datetime.timedelta(hours=-4)),
            ),
        ),
        ("2022-10-21T18:16:03.1-04:00", "2022-10-21T18:16:03.1-04:00"),
    ],
)
def test_load_timestamp(input_yaml, want):
    got = salt_yaml.load(input_yaml)
    assert got == want


def test_load_tuple():
    input = "!!python/tuple\n- foo\n- bar\n"
    got = salt_yaml.load(input)
    want = ("foo", "bar")
    assert got == want


def test_not_yaml_monkey_patching():
    if hasattr(yaml, "CSafeLoader"):
        assert yaml.SafeLoader != yaml.CSafeLoader

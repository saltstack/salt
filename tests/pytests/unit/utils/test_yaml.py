import collections
import datetime
import random
import re
import textwrap
import warnings

import pytest
import yaml
from yaml.constructor import ConstructorError

import salt.utils._yaml_common as _yc
import salt.utils.files
import salt.utils.yaml as salt_yaml
from salt.utils.odict import OrderedDict
from salt.version import SaltStackVersion
from tests.support.mock import mock_open, patch


class _OrderedDictLoader(salt_yaml.SaltYamlSafeLoader):
    def __init__(self, stream):
        super().__init__(stream, dictclass=collections.OrderedDict)


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


@pytest.mark.parametrize("yaml_compatibility", [3006, 3007], indirect=True)
@pytest.mark.parametrize("dictcls", [OrderedDict, collections.OrderedDict])
@pytest.mark.parametrize(
    "dumpercls",
    [
        salt_yaml.OrderedDumper,
        salt_yaml.SafeOrderedDumper,
        salt_yaml.IndentedSafeOrderedDumper,
    ],
)
def test_dump_omap(yaml_compatibility, dictcls, dumpercls):
    # The random keys are filtered through a set to avoid duplicates.
    keys = list({f"random key {random.getrandbits(32)}" for _ in range(20)})
    # Avoid unintended correlation with set()'s iteration order.
    random.shuffle(keys)
    items = [(k, i) for i, k in enumerate(keys)]
    d = dictcls(items)
    if yaml_compatibility == 3006 and dictcls is collections.OrderedDict:
        # Buggy behavior preserved for backwards compatibility.
        if dumpercls is salt_yaml.OrderedDumper:
            want = (
                "!!python/object/apply:collections.OrderedDict\n-"
                + "".join(f"  - - {k}\n    - {v}\n" for k, v in items)[1:]
            )
        else:
            # With v3006, sometimes it prints "..." on a new line as an end of
            # document indicator depending on whether yaml.CSafeDumper is
            # available on the system or not (yaml.CSafeDumper and
            # yaml.SafeDumper do not always behave the same).
            want = re.compile(r"NULL\n(?:\.\.\.\n)?")
    else:
        want = "".join(f"{k}: {v}\n" for k, v in items)
    got = salt_yaml.dump(d, Dumper=dumpercls, default_flow_style=False)
    try:
        assert want.fullmatch(got)
    except AttributeError:
        assert got == want


@pytest.mark.parametrize(
    "dumpercls",
    [
        salt_yaml.OrderedDumper,
        salt_yaml.SafeOrderedDumper,
        salt_yaml.IndentedSafeOrderedDumper,
    ],
)
@pytest.mark.parametrize(
    "yaml_compatibility,want_tag",
    [(3006, False), (3007, True)],
    indirect=["yaml_compatibility"],
)
def test_dump_timestamp(yaml_compatibility, want_tag, dumpercls):
    dt = datetime.datetime(
        *(2022, 10, 21, 18, 16, 3, 100000),
        tzinfo=datetime.timezone(datetime.timedelta(hours=-4)),
    )
    got = salt_yaml.dump(dt, Dumper=dumpercls)
    want_re = r"""(['"]?)2022-10-21[T ]18:16:03.10*-04:00\1\n(?:\.\.\.\n)?"""
    if want_tag:
        want_re = f"!!timestamp {want_re}"
    assert re.fullmatch(want_re, got)


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


@pytest.mark.parametrize(
    # Parameters:
    #   - yaml_compatibility: Force the YAML loader to be compatible with this
    #     version of Salt.
    #   - seq_input: Boolean.  True if the input YAML node should be a sequence
    #     of single-entry mappings, False if it should be a mapping.
    #   - Loader: YAML Loader class.
    #   - wantclass: Expected return type.
    "yaml_compatibility,seq_input,Loader,wantclass",
    [
        # Salt v3006 and earlier required !!omap nodes to be mapping nodes if
        # the SaltYamlSafeLoader dictclass argument is not dict.  To preserve
        # compatibility, that erroneous behavior is preserved if
        # yaml_compatibility is set to 3006.
        (3006, False, _OrderedDictLoader, collections.OrderedDict),
        # However, with dictclass=dict (the default), an !!omap node was
        # correctly required to be a sequence of mapping nodes.  Unfortunately,
        # the return value was not a Mapping type -- it was a list of (key,
        # value) tuples (PyYAML's default behavior for !!omap nodes).
        (3006, True, None, list),
        # Starting with Salt v3007, an !!omap node is always required to be a
        # sequence of mapping nodes, and always returns an OrderedDict.
        (3007, True, _OrderedDictLoader, collections.OrderedDict),
        (3007, True, None, collections.OrderedDict),
    ],
    indirect=["yaml_compatibility"],
)
def test_load_omap(yaml_compatibility, seq_input, Loader, wantclass):
    """Test loading of `!!omap` YAML nodes.

    This test uses random keys to ensure that iteration order does not
    coincidentally match.  The generated items look like this:

    .. code-block:: python

        [
            ("k3334244338", 0),
            ("k3444116829", 1),
            ("k2072366017", 2),
            # ... omitted for brevity ...
            ("k1638299831", 19),
        ]
    """
    # Filter the random keys through a set to avoid duplicates.
    keys = list({f"k{random.getrandbits(32)}" for _ in range(20)})
    # Avoid unintended correlation with set()'s iteration order.
    random.shuffle(keys)
    items = [(k, i) for i, k in enumerate(keys)]
    input_yaml = "!!omap\n"
    if seq_input:
        input_yaml += "".join(f"- {k}: {v}\n" for k, v in items)
    else:
        input_yaml += "".join(f"{k}: {v}\n" for k, v in items)
    kwargs = {}
    if Loader is not None:
        kwargs["Loader"] = Loader
    got = salt_yaml.load(input_yaml, **kwargs)
    assert isinstance(got, wantclass)
    if isinstance(got, list):
        assert got == items
    else:
        assert got == collections.OrderedDict(items)
        assert list(got.items()) == items


@pytest.mark.parametrize(
    "yaml_compatibility,input_yaml,Loader,want",
    [
        # See comments in test_load_omap() above for the differences in !!omap
        # loading behavior between Salt v3006 and v3007.
        (3006, "!!omap {}\n", _OrderedDictLoader, collections.OrderedDict()),
        (3006, "!!omap []\n", None, []),
        (3007, "!!omap []\n", _OrderedDictLoader, collections.OrderedDict()),
        (3007, "!!omap []\n", None, collections.OrderedDict()),
    ],
    indirect=["yaml_compatibility"],
)
def test_load_omap_empty(yaml_compatibility, input_yaml, Loader, want):
    kwargs = {}
    if Loader is not None:
        kwargs["Loader"] = Loader
    got = salt_yaml.load(input_yaml, **kwargs)
    assert isinstance(got, type(want))
    assert got == want


@pytest.mark.parametrize(
    "yaml_compatibility,input_yaml,Loader",
    [
        # Buggy v3006 behavior kept for compatibility.  See comments in
        # test_load_omap() above for details.
        (3006, "!!omap []\n", _OrderedDictLoader),  # Not a mapping node.
        (3006, "!!omap\ndup key: 0\ndup key: 1\n", _OrderedDictLoader),
        # Invald because the !!omap node is not a sequence node.
        (3006, "!!omap {}\n", None),
        (3007, "!!omap {}\n", _OrderedDictLoader),
        (3007, "!!omap {}\n", None),
        # Invalid because a sequence entry is not a mapping node.
        (3006, "!!omap\n- this is a str not a map\n", None),
        (3007, "!!omap\n- this is a str not a map\n", _OrderedDictLoader),
        (3007, "!!omap\n- this is a str not a map\n", None),
        # Invalid because a sequence entry's mapping has multiple entries.
        (3006, "!!omap\n- k1: v\n  k2: v\n", None),
        (3007, "!!omap\n- k1: v\n  k2: v\n", _OrderedDictLoader),
        (3007, "!!omap\n- k1: v\n  k2: v\n", None),
        # Invalid because a sequence entry's mapping has no entries.
        (3006, "!!omap [{}]\n", None),
        (3007, "!!omap [{}]\n", _OrderedDictLoader),
        (3007, "!!omap [{}]\n", None),
        # Invalid because there are duplicate keys.  Note that the Loader=None
        # case for v3006 is missing here; this is because the default v3006
        # Loader matches PyYAML's behavior, and PyYAML permits duplicate keys in
        # !!omap nodes.
        (3007, "!!omap\n- dup key: 0\n- dup key: 1\n", _OrderedDictLoader),
        (3007, "!!omap\n- dup key: 0\n- dup key: 1\n", None),
    ],
    indirect=["yaml_compatibility"],
)
def test_load_omap_invalid(yaml_compatibility, input_yaml, Loader):
    kwargs = {}
    if Loader is not None:
        kwargs["Loader"] = Loader
    with pytest.raises(ConstructorError):
        salt_yaml.load(input_yaml, **kwargs)


@pytest.mark.parametrize("yaml_compatibility", [3006, 3007], indirect=True)
@pytest.mark.parametrize("Loader", [_OrderedDictLoader, None])
def test_load_untagged_omaplike_is_seq(yaml_compatibility, Loader):
    # The YAML spec allows the loader to interpret something that looks like an
    # !!omap but doesn't actually have an !!omap tag as an !!omap.  (If the user
    # intends to express a sequence of single-entry maps and not an ordered map,
    # the user must explicitly tag the sequence node with !seq.)  Out of concern
    # for backwards compatibility, and to avoid ambiguity with an empty
    # sequence, implicit !!omap behavior is currently not supported.  That may
    # change in the future, but for now make sure that sequences are not
    # interpreted as ordered maps.
    kwargs = {}
    if Loader is not None:
        kwargs["Loader"] = Loader
    got = salt_yaml.load("- a: 0\n- b: 1\n", **kwargs)
    assert not isinstance(got, collections.OrderedDict)
    assert got == [{"a": 0}, {"b": 1}]


@pytest.mark.parametrize(
    "yaml_compatibility,input_yaml,want",
    [
        (
            3006,
            "!!timestamp 2022-10-21T18:16:03.1-04:00",
            "2022-10-21T18:16:03.1-04:00",
        ),
        (
            3007,
            "!!timestamp 2022-10-21T18:16:03.1-04:00",
            datetime.datetime(
                *(2022, 10, 21, 18, 16, 3, 100000),
                tzinfo=datetime.timezone(datetime.timedelta(hours=-4)),
            ),
        ),
        (3006, "2022-10-21T18:16:03.1-04:00", "2022-10-21T18:16:03.1-04:00"),
        (3007, "2022-10-21T18:16:03.1-04:00", "2022-10-21T18:16:03.1-04:00"),
    ],
    indirect=["yaml_compatibility"],
)
def test_load_timestamp(yaml_compatibility, input_yaml, want):
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

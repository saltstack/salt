import logging
from io import StringIO

import pytest

import salt.exceptions
import salt.modules.slsutil as slsutil
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules(master_dirs, master_files, minion_opts):
    return {
        slsutil: {
            "__opts__": minion_opts,
            "__salt__": {
                "cp.list_master": MagicMock(return_value=master_files),
                "cp.list_master_dirs": MagicMock(return_value=master_dirs),
            },
        }
    }


@pytest.fixture
def master_dirs():
    return ["red", "red/files", "blue", "blue/files"]


@pytest.fixture
def master_files():
    return [
        "top.sls",
        "red/init.sls",
        "red/files/default.conf",
        "blue/init.sls",
        "blue/files/default.conf",
    ]


def test_banner():
    """
    Test banner function
    """
    check_banner()
    check_banner(width=81)
    check_banner(width=20)
    check_banner(commentchar="//", borderchar="-")
    check_banner(title="title here", text="text here")
    check_banner(commentchar=" *")
    check_banner(commentchar=" *", newline=False)

    # Test when width result in a raised exception
    with pytest.raises(salt.exceptions.ArgumentValueError):
        slsutil.banner(width=4)

    ret = slsutil.banner(
        title="title here", text="text here", blockstart="/*", blockend="*/"
    )
    lines = ret.splitlines()
    # test blockstart
    assert lines[0] == "/*"

    # test blockend
    assert lines[-1] == "*/"


def check_banner(
    width=72,
    commentchar="#",
    borderchar="#",
    blockstart=None,
    blockend=None,
    title=None,
    text=None,
    newline=True,
):

    result = slsutil.banner(
        width=width,
        commentchar=commentchar,
        borderchar=borderchar,
        blockstart=blockstart,
        blockend=blockend,
        title=title,
        text=text,
        newline=newline,
    ).splitlines()
    for line in result:
        assert len(line) == width
        assert line.startswith(commentchar)
        assert line.endswith(commentchar.strip())


def test_boolstr():
    """
    Test boolstr function
    """
    assert "yes" == slsutil.boolstr(True, true="yes", false="no")
    assert "no" == slsutil.boolstr(False, true="yes", false="no")


def test_file_exists():
    """
    Test file_exists function
    """
    assert slsutil.file_exists("red/init.sls")
    assert not slsutil.file_exists("green/init.sls")


def test_dir_exists():
    """
    Test dir_exists function
    """
    assert slsutil.dir_exists("red")
    assert not slsutil.dir_exists("green")


def test_path_exists():
    """
    Test path_exists function
    """
    assert slsutil.path_exists("red")
    assert not slsutil.path_exists("green")
    assert slsutil.path_exists("red/init.sls")
    assert not slsutil.path_exists("green/init.sls")


def test_findup():
    """
    Test findup function
    """
    assert "red/init.sls" == slsutil.findup("red/files", "init.sls")
    assert "top.sls" == slsutil.findup("red/files", ["top.sls"])
    assert "top.sls" == slsutil.findup("", "top.sls")
    assert "top.sls" == slsutil.findup(None, "top.sls")
    assert "red/init.sls" == slsutil.findup("red/files", ["top.sls", "init.sls"])

    with pytest.raises(salt.exceptions.CommandExecutionError):
        slsutil.findup("red/files", "notfound")

    with pytest.raises(salt.exceptions.CommandExecutionError):
        slsutil.findup("red", "default.conf")

    with pytest.raises(salt.exceptions.SaltInvocationError):
        with patch.object(slsutil, "path_exists", return_value=False):
            slsutil.findup("red", "default.conf")

    with pytest.raises(salt.exceptions.SaltInvocationError):
        slsutil.findup("red", {"file": "default.conf"})


def test_update():
    """
    Test update function
    """

    ret = slsutil.update({"foo": "Foo"}, {"bar": "Bar"})
    assert ret == {"foo": "Foo", "bar": "Bar"}

    ret = slsutil.update({"foo": "Foo"}, {"foo": "Bar"}, merge_lists=False)
    assert ret == {"foo": "Bar"}


def test_merge():
    """
    Test merge function
    """

    ret = slsutil.merge({"foo": "Foo"}, {"bar": "Bar"}, strategy="smart")
    assert ret == {"foo": "Foo", "bar": "Bar"}

    ret = slsutil.merge({"foo": "Foo"}, {"foo": "Bar"}, strategy="aggregate")
    assert ret == {"foo": "Bar"}

    ret = slsutil.merge({"foo": "Foo"}, {"foo": "Bar"}, strategy="list")
    assert ret == {"foo": ["Foo", "Bar"]}

    ret = slsutil.merge({"foo": "Foo"}, {"foo": "Bar"}, strategy="overwrite")
    assert ret == {"foo": "Bar"}

    ret = slsutil.merge(
        {"foo": {"Foo": "Bar"}}, {"foo": {"Foo": "Baz"}}, strategy="recurse"
    )
    assert ret == {"foo": {"Foo": "Baz"}}


def test_merge_all():
    """
    Test merge_all function
    """

    ret = slsutil.merge_all([{"foo": "Foo"}, {"bar": "Bar"}], strategy="smart")
    assert ret == {"foo": "Foo", "bar": "Bar"}

    ret = slsutil.merge_all([{"foo": "Foo"}, {"foo": "Bar"}], strategy="aggregate")
    assert ret == {"foo": "Bar"}

    ret = slsutil.merge_all([{"foo": "Foo"}, {"foo": "Bar"}], strategy="overwrite")
    assert ret == {"foo": "Bar"}

    ret = slsutil.merge_all(
        [{"foo": {"Foo": "Bar"}}, {"foo": {"Foo": "Baz"}}], strategy="recurse"
    )
    assert ret == {"foo": {"Foo": "Baz"}}


def test_renderer():
    """
    Test renderer function
    """
    with patch.dict(
        slsutil.__utils__, {"stringio.is_readable": MagicMock(return_value=False)}
    ):
        ret = slsutil.renderer(string="Hello, {{ name }}.", name="world")
        assert ret == "Hello, world."

    with pytest.raises(salt.exceptions.SaltInvocationError) as exc:
        slsutil.renderer()
    assert str(exc.value) == "Must pass path or string."

    with pytest.raises(salt.exceptions.SaltInvocationError) as exc:
        slsutil.renderer(path="/path/to/file", string="Hello world")
    assert str(exc.value) == "Must not pass both path and string."

    with patch.dict(
        slsutil.__salt__, {"cp.get_url": MagicMock(return_value="/path/to/file")}
    ):
        with patch.dict(
            slsutil.__utils__, {"stringio.is_readable": MagicMock(return_value=True)}
        ):
            rendered_file = "Hello, world."
            with patch(
                "salt.template.compile_template",
                MagicMock(return_value=StringIO(rendered_file)),
            ):
                ret = slsutil.renderer(path="/path/to/file")
                assert ret == "Hello, world."


def test_serialize():
    """
    Test serialize function
    """
    ret = slsutil.serialize("json", obj={"foo": "Foo!"})
    assert ret == '{"foo": "Foo!"}'


def test_deserialize():
    """
    Test serialize function
    """
    ret = slsutil.deserialize("json", '{"foo": "Foo!"}')
    assert ret == {"foo": "Foo!"}


def dummy_function(args=None, kwargs=None):
    return True


def test__set_context():
    """
    Test _set_context
    """
    with patch.dict(slsutil.__context__, {}):

        slsutil._set_context(
            ["level_one", "level_two", "level_three"], dummy_function, force=True
        )
        assert slsutil.__context__ == {
            "level_one": {"level_two": {"level_three": True}}
        }

    with patch.dict(slsutil.__context__, {}):

        slsutil._set_context(
            ["level_one", "level_two", "level_three"],
            dummy_function,
            fun_kwargs={"key_one": "arg_one"},
            force=True,
        )
        assert slsutil.__context__ == {
            "level_one": {"level_two": {"level_three": True}}
        }


def test__get_serializer_fn():
    """
    Test _set_context
    """
    # Invalid serializer
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        slsutil._get_serialize_fn("bad_yaml", "badfunc")
        assert str(exc.value) == "Serializer 'bad_yaml' not found."

    # Invalid serializer function
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        slsutil._get_serialize_fn("yaml", "foobar")
        assert str(exc.value) == "Serializer 'yaml' does not implement foobar."

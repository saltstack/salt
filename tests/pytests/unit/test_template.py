import io

import pytest

import salt.state
from salt import template
from tests.support.mock import MagicMock, patch


@pytest.fixture
def render_dict():
    return {
        "jinja": "fake_jinja_func",
        "json": "fake_json_func",
        "mako": "fake_make_func",
    }


def test_compile_template_str_mkstemp_cleanup(minion_opts):
    minion_opts["file_client"] = "local"
    with patch("os.unlink", MagicMock()) as unlinked:
        _state = salt.state.State(minion_opts)
        ret = template.compile_template_str(
            "{'val':'test'}",
            _state.rend,
            _state.opts["renderer"],
            _state.opts["renderer_blacklist"],
            _state.opts["renderer_whitelist"],
        )
        assert ret == {"val": "test"}
        unlinked.assert_called_once()


def test_compile_template_bad_type():
    """
    Test to ensure that unsupported types cannot be passed to the template compiler
    """
    ret = template.compile_template(["1", "2", "3"], None, None, None, None)
    assert ret == {}


def test_compile_template_preserves_windows_newlines():
    """
    Test to ensure that a file with Windows newlines, when rendered by a
    template renderer, does not eat the CR character.
    """

    def _get_rend(renderer, value):
        """
        We need a new MagicMock each time since we're dealing with StringIO
        objects which are read like files.
        """
        return {renderer: MagicMock(return_value=io.StringIO(value))}

    input_data_windows = "foo\r\nbar\r\nbaz\r\n"
    input_data_non_windows = input_data_windows.replace("\r\n", "\n")
    renderer = "test"
    blacklist = whitelist = []

    ret = template.compile_template(
        ":string:",
        _get_rend(renderer, input_data_non_windows),
        renderer,
        blacklist,
        whitelist,
        input_data=input_data_windows,
    ).read()
    # Even though the mocked renderer returned a string without the windows
    # newlines, the compiled template should still have them.
    assert ret == input_data_windows

    # Now test that we aren't adding them in unnecessarily.
    ret = template.compile_template(
        ":string:",
        _get_rend(renderer, input_data_non_windows),
        renderer,
        blacklist,
        whitelist,
        input_data=input_data_non_windows,
    ).read()
    assert ret == input_data_non_windows

    # Finally, ensure that we're not unnecessarily replacing the \n with
    # \r\n in the event that the renderer returned a string with the
    # windows newlines intact.
    ret = template.compile_template(
        ":string:",
        _get_rend(renderer, input_data_windows),
        renderer,
        blacklist,
        whitelist,
        input_data=input_data_windows,
    ).read()
    assert ret == input_data_windows


def test_check_render_pipe_str(render_dict):
    """
    Check that all renderers specified in the pipe string are available.
    """
    ret = template.check_render_pipe_str("jinja|json", render_dict, None, None)
    assert ("fake_jinja_func", "") in ret
    assert ("fake_json_func", "") in ret
    assert ("OBVIOUSLY_NOT_HERE", "") not in ret


def test_check_renderer_blacklisting(render_dict):
    """
    Check that all renderers specified in the pipe string are available.
    """
    ret = template.check_render_pipe_str("jinja|json", render_dict, ["jinja"], None)
    assert ret == [("fake_json_func", "")]
    ret = template.check_render_pipe_str("jinja|json", render_dict, None, ["jinja"])
    assert ret == [("fake_jinja_func", "")]
    ret = template.check_render_pipe_str(
        "jinja|json", render_dict, ["jinja"], ["jinja"]
    )
    assert ret == []
    ret = template.check_render_pipe_str(
        "jinja|json", render_dict, ["jinja"], ["jinja", "json"]
    )
    assert ret == [("fake_json_func", "")]

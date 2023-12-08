"""
Tests for salt.utils.jinja
"""

import builtins
import datetime
import logging
import os

import pytest

import salt.loader

# dateutils is needed so that the strftime jinja filter is loaded
import salt.utils.dateutils  # pylint: disable=unused-import
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml
from salt.exceptions import SaltRenderError
from salt.utils.jinja import SaltCacheLoader
from salt.utils.templates import JINJA, render_jinja_tmpl
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


try:
    import timelib  # pylint: disable=W0611

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False


class MockFileClient:
    """
    Does not download files but records any file request for testing
    """

    def __init__(self, loader=None):
        if loader:
            loader._file_client = self
        self.requests = []

    def get_file(self, template, dest="", makedirs=False, saltenv="base"):
        self.requests.append(
            {"path": template, "dest": dest, "makedirs": makedirs, "saltenv": saltenv}
        )


@pytest.fixture
def minion_opts(tmp_path, minion_opts):
    minion_opts.update(
        {
            "cachedir": str(tmp_path),
            "file_buffer_size": 1048576,
            "file_client": "local",
            "file_ignore_regex": None,
            "file_ignore_glob": None,
            "file_roots": {"test": [str(tmp_path / "files" / "test")]},
            "pillar_roots": {"test": [str(tmp_path / "files" / "test")]},
            "fileserver_backend": ["roots"],
            "extension_modules": os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "extmods"
            ),
        }
    )
    return minion_opts


@pytest.fixture
def local_salt():
    return {}


@pytest.fixture
def non_ascii(template_dir):
    contents = b"""Assun\xc3\xa7\xc3\xa3o""" + salt.utils.stringutils.to_bytes(
        os.linesep
    )

    non_ascii_file = template_dir / "non-ascii"
    non_ascii_file.write_bytes(contents)
    return non_ascii_file


def test_fallback(minion_opts, local_salt, template_dir):
    """
    A Template with a filesystem loader is returned as fallback
    if the file is not contained in the searchpath
    """

    with pytest.helpers.temp_file(
        "hello_simple", directory=template_dir, contents="world\n"
    ) as hello_simple:
        with salt.utils.files.fopen(str(hello_simple)) as fp_:
            out = render_jinja_tmpl(
                salt.utils.stringutils.to_unicode(fp_.read()),
                dict(opts=minion_opts, saltenv="test", salt=local_salt),
            )
        assert out == "world" + os.linesep


def test_fallback_noloader(minion_opts, local_salt, hello_import):
    """
    A Template with a filesystem loader is returned as fallback
    if the file is not contained in the searchpath
    """
    with salt.utils.files.fopen(str(hello_import)) as fp_:
        out = render_jinja_tmpl(
            salt.utils.stringutils.to_unicode(fp_.read()),
            dict(opts=minion_opts, saltenv="test", salt=local_salt),
        )
    assert out == "Hey world !a b !" + os.linesep


def test_saltenv(minion_opts, local_salt, mock_file_client, hello_import):
    """
    If the template is within the searchpath it can
    import, include and extend other templates.
    The initial template is expected to be already cached
    get_template does not request it from the master again.
    """
    fc = MockFileClient()
    opts = {
        "cachedir": minion_opts["cachedir"],
        "file_client": "remote",
        "file_roots": minion_opts["file_roots"],
        "pillar_roots": minion_opts["pillar_roots"],
    }
    with patch.object(SaltCacheLoader, "file_client", MagicMock(return_value=fc)):
        with salt.utils.files.fopen(str(hello_import)) as fp_:
            out = render_jinja_tmpl(
                salt.utils.stringutils.to_unicode(fp_.read()),
                dict(
                    opts=opts,
                    a="Hi",
                    b="Salt",
                    saltenv="test",
                    salt=local_salt,
                ),
            )
        assert out == "Hey world !Hi Salt !" + os.linesep
        assert fc.requests[0]["path"] == "salt://macro"


def test_macro_additional_log_for_generalexc(
    minion_opts, local_salt, hello_import, mock_file_client, template_dir
):
    """
    If we failed in a macro because of e.g. a TypeError, get
    more output from trace.
    """
    expected = r"""Jinja error:.*division.*
.*macrogeneral\(2\):
---
\{% macro mymacro\(\) -%\}
\{\{ 1/0 \}\}    <======================
\{%- endmacro %\}
---.*"""

    contents = """{% from 'macrogeneral' import mymacro -%}
{{ mymacro() }}
"""

    macrogeneral_contents = """{% macro mymacro() -%}
{{ 1/0 }}
{%- endmacro %}
"""

    with pytest.helpers.temp_file(
        "hello_import_generalerror", directory=template_dir, contents=contents
    ) as hello_import_generalerror:
        with pytest.helpers.temp_file(
            "macrogeneral",
            directory=template_dir,
            contents=macrogeneral_contents,
        ) as macrogeneral:
            with patch.object(
                SaltCacheLoader, "file_client", MagicMock(return_value=mock_file_client)
            ):
                with salt.utils.files.fopen(str(hello_import_generalerror)) as fp_:
                    with pytest.raises(SaltRenderError, match=expected):
                        render_jinja_tmpl(
                            salt.utils.stringutils.to_unicode(fp_.read()),
                            dict(opts=minion_opts, saltenv="test", salt=local_salt),
                        )


def test_macro_additional_log_for_undefined(
    minion_opts, local_salt, mock_file_client, template_dir
):
    """
    If we failed in a macro because of undefined variables, get
    more output from trace.
    """
    expected = r"""Jinja variable 'b' is undefined
.*macroundefined\(2\):
---
\{% macro mymacro\(\) -%\}
\{\{b.greetee\}\} <-- error is here    <======================
\{%- endmacro %\}
---"""

    contents = """{% from 'macroundefined' import mymacro -%}
{{ mymacro() }}
"""

    macroundefined_contents = """{% macro mymacro() -%}
{{b.greetee}} <-- error is here
{%- endmacro %}
"""

    with pytest.helpers.temp_file(
        "hello_import_undefined", directory=template_dir, contents=contents
    ) as hello_import_undefined:
        with pytest.helpers.temp_file(
            "macroundefined",
            directory=template_dir,
            contents=macroundefined_contents,
        ) as macroundefined:
            with patch.object(
                SaltCacheLoader, "file_client", MagicMock(return_value=mock_file_client)
            ):
                with salt.utils.files.fopen(str(hello_import_undefined)) as fp_:
                    with pytest.raises(SaltRenderError, match=expected):
                        render_jinja_tmpl(
                            salt.utils.stringutils.to_unicode(fp_.read()),
                            dict(opts=minion_opts, saltenv="test", salt=local_salt),
                        )


def test_macro_additional_log_syntaxerror(
    minion_opts, local_salt, mock_file_client, template_dir
):
    """
    If  we failed in a macro, get more output from trace.
    """
    expected = r"""Jinja syntax error: expected token .*end.*got '-'.*
.*macroerror\(2\):
---
# macro
\{% macro mymacro\(greeting, greetee='world'\) -\} <-- error is here    <======================
\{\{ greeting ~ ' ' ~ greetee \}\} !
\{%- endmacro %\}
---.*"""

    macroerror_contents = """# macro
{% macro mymacro(greeting, greetee='world') -} <-- error is here
{{ greeting ~ ' ' ~ greetee }} !
{%- endmacro %}
"""

    contents = """{% from 'macroerror' import mymacro -%}
{{ mymacro('Hey') ~ mymacro(a|default('a'), b|default('b')) }}
"""

    with pytest.helpers.temp_file(
        "hello_import_error", directory=template_dir, contents=contents
    ) as hello_import_error:
        with pytest.helpers.temp_file(
            "macroerror", directory=template_dir, contents=macroerror_contents
        ) as macroerror:
            with patch.object(
                SaltCacheLoader, "file_client", MagicMock(return_value=mock_file_client)
            ):
                with salt.utils.files.fopen(str(hello_import_error)) as fp_:
                    with pytest.raises(SaltRenderError, match=expected):
                        render_jinja_tmpl(
                            salt.utils.stringutils.to_unicode(fp_.read()),
                            dict(opts=minion_opts, saltenv="test", salt=local_salt),
                        )


def test_non_ascii_encoding(
    minion_opts, local_salt, mock_file_client, non_ascii, hello_import
):
    with patch.object(
        SaltCacheLoader, "file_client", MagicMock(return_value=mock_file_client)
    ):
        with salt.utils.files.fopen(str(hello_import)) as fp_:
            out = render_jinja_tmpl(
                salt.utils.stringutils.to_unicode(fp_.read()),
                dict(
                    opts={
                        "cachedir": minion_opts["cachedir"],
                        "file_client": "remote",
                        "file_roots": minion_opts["file_roots"],
                        "pillar_roots": minion_opts["pillar_roots"],
                    },
                    a="Hi",
                    b="Sàlt",
                    saltenv="test",
                    salt=local_salt,
                ),
            )
        assert out == salt.utils.stringutils.to_unicode(
            "Hey world !Hi Sàlt !" + os.linesep
        )
        assert mock_file_client.requests[0]["path"] == "salt://macro"

        with salt.utils.files.fopen(str(non_ascii), "rb") as fp_:
            out = render_jinja_tmpl(
                salt.utils.stringutils.to_unicode(fp_.read(), "utf-8"),
                dict(
                    opts={
                        "cachedir": minion_opts["cachedir"],
                        "file_client": "remote",
                        "file_roots": minion_opts["file_roots"],
                        "pillar_roots": minion_opts["pillar_roots"],
                    },
                    a="Hi",
                    b="Sàlt",
                    saltenv="test",
                    salt=local_salt,
                ),
            )
        assert "Assunção" + os.linesep == out
        assert mock_file_client.requests[0]["path"] == "salt://macro"


@pytest.mark.skipif(
    HAS_TIMELIB is False, reason="The `timelib` library is not installed."
)
@pytest.mark.parametrize(
    "data_object",
    [
        datetime.datetime(2002, 12, 25, 12, 00, 00, 00),
        "2002/12/25",
        1040814000,
        "1040814000",
    ],
)
def test_strftime(minion_opts, local_salt, data_object):
    response = render_jinja_tmpl(
        '{{ "2002/12/25"|strftime }}',
        dict(opts=minion_opts, saltenv="test", salt=local_salt),
    )
    assert response == "2002-12-25"

    response = render_jinja_tmpl(
        "{{ object|strftime }}",
        dict(
            object=data_object,
            opts=minion_opts,
            saltenv="test",
            salt=local_salt,
        ),
    )
    assert response == "2002-12-25"

    response = render_jinja_tmpl(
        '{{ object|strftime("%b %d, %Y") }}',
        dict(
            object=data_object,
            opts=minion_opts,
            saltenv="test",
            salt=local_salt,
        ),
    )
    assert response == "Dec 25, 2002"

    response = render_jinja_tmpl(
        '{{ object|strftime("%y") }}',
        dict(
            object=data_object,
            opts=minion_opts,
            saltenv="test",
            salt=local_salt,
        ),
    )
    assert response == "02"


def test_non_ascii(minion_opts, local_salt, non_ascii):
    out = JINJA(str(non_ascii), opts=minion_opts, saltenv="test", salt=local_salt)
    with salt.utils.files.fopen(out["data"], "rb") as fp:
        result = salt.utils.stringutils.to_unicode(fp.read(), "utf-8")
        assert salt.utils.stringutils.to_unicode("Assunção" + os.linesep) == result


def test_get_context_has_enough_context(minion_opts, local_salt):
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 8)
    expected = "---\n[...]\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\n[...]\n---"
    assert expected == context


def test_get_context_at_top_of_file(minion_opts, local_salt):
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 1)
    expected = "---\n1\n2\n3\n4\n5\n6\n[...]\n---"
    assert expected == context


def test_get_context_at_bottom_of_file(minion_opts, local_salt):
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 15)
    expected = "---\n[...]\na\nb\nc\nd\ne\nf\n---"
    assert expected == context


def test_get_context_2_context_lines(minion_opts, local_salt):
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 8, num_lines=2)
    expected = "---\n[...]\n6\n7\n8\n9\na\n[...]\n---"
    assert expected == context


def test_get_context_with_marker(minion_opts, local_salt):
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(
        template, 8, num_lines=2, marker=" <---"
    )
    expected = "---\n[...]\n6\n7\n8 <---\n9\na\n[...]\n---"
    assert expected == context


def test_render_with_syntax_error(minion_opts, local_salt):
    template = "hello\n\n{{ bad\n\nfoo"
    expected = r".*---\nhello\n\n{{ bad\n\nfoo    <======================\n---"
    with pytest.raises(SaltRenderError, match=expected):
        render_jinja_tmpl(
            template,
            dict(opts=minion_opts, saltenv="test", salt=local_salt),
        )


def test_render_with_utf8_syntax_error(minion_opts, local_salt):
    with patch.object(builtins, "__salt_system_encoding__", "utf-8"):
        template = "hello\n\n{{ bad\n\nfoo한"
        expected = salt.utils.stringutils.to_str(
            r".*---\nhello\n\n{{ bad\n\nfoo한    <======================\n---"
        )
        with pytest.raises(SaltRenderError, match=expected):
            render_jinja_tmpl(
                template,
                dict(opts=minion_opts, saltenv="test", salt=local_salt),
            )


def test_render_with_undefined_variable(minion_opts, local_salt):
    template = "hello\n\n{{ foo }}\n\nfoo"
    expected = r"Jinja variable \'foo\' is undefined"
    with pytest.raises(SaltRenderError, match=expected):
        render_jinja_tmpl(
            template,
            dict(opts=minion_opts, saltenv="test", salt=local_salt),
        )


def test_render_with_undefined_variable_utf8(minion_opts, local_salt):
    template = "hello\xed\x95\x9c\n\n{{ foo }}\n\nfoo"
    expected = r"Jinja variable \'foo\' is undefined"
    with pytest.raises(SaltRenderError, match=expected):
        render_jinja_tmpl(
            template,
            dict(opts=minion_opts, saltenv="test", salt=local_salt),
        )


def test_render_with_undefined_variable_unicode(minion_opts, local_salt):
    template = "hello한\n\n{{ foo }}\n\nfoo"
    expected = r"Jinja variable \'foo\' is undefined"
    with pytest.raises(SaltRenderError, match=expected):
        render_jinja_tmpl(
            template,
            dict(opts=minion_opts, saltenv="test", salt=local_salt),
        )


def test_relative_include(minion_opts, local_salt, template_dir, hello_import):
    template = "{% include './hello_import' %}"
    expected = "Hey world !a b !"
    with salt.utils.files.fopen(str(hello_import)) as fp_:
        out = render_jinja_tmpl(
            template,
            dict(
                opts=minion_opts,
                saltenv="test",
                salt=local_salt,
                tpldir=str(template_dir),
            ),
        )
    assert out == expected

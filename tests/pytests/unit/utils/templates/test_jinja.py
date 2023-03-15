"""
Tests for salt.utils.templates
"""
import os
import re

import pytest
from salt.exceptions import SaltRenderError
from salt.utils.templates import render_jinja_tmpl


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
            "hash_type": "md5",
            "extension_modules": os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "extmods"
            ),
        }
    )
    return minion_opts


@pytest.fixture
def local_salt():
    return {}


def test_jinja_undefined_error_context(minion_opts, local_salt):
    """
    Test that jinja provides both the line number on which the error occurred
    in the Jinja template, and also several lines of context around the error
    in the Jinja template source when ``jinja2.exceptions.UndefinedError`` is
    raised.
    """

    jinja_code = """
    {%- set sections = {"first": {"a": "b"}, "second": ["a", "b"]} %}
    {%- for section in sections %}
      {%- for name, config in section.items() %}
      {%- endfor %}
    {%- endfor %}
    """
    marker = "    <======================"

    # Test that the exception messages includes the source file context details
    # and marker.  Since salt catches and re-emits internal jinja exceptions as
    # `SaltRenderError`, the easiest way to distinguish which original
    # exception was raised is to match on the initial wording of the exception
    # message.
    match_regex = re.compile(
        rf"^Jinja variable .*; line .*{marker}$", re.DOTALL | re.MULTILINE
    )
    with pytest.raises(SaltRenderError, match=match_regex):
        render_jinja_tmpl(
            jinja_code,
            dict(opts=minion_opts, saltenv="test", salt=local_salt),
        )

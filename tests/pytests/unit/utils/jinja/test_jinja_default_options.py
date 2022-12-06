"""
Tests for salt.utils.jinja
"""

import os

import pytest

# dateutils is needed so that the strftime jinja filter is loaded
import salt.utils.dateutils  # pylint: disable=unused-import
import salt.utils.files  # pylint: disable=unused-import
import salt.utils.json  # pylint: disable=unused-import
import salt.utils.stringutils  # pylint: disable=unused-import
import salt.utils.yaml  # pylint: disable=unused-import
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
            "jinja_env": {"line_comment_prefix": "##", "line_statement_prefix": "%"},
        }
    )
    return minion_opts


@pytest.fixture
def local_salt():
    return {
        "myvar": "zero",
        "mylist": [0, 1, 2, 3],
    }


def test_comment_prefix(minion_opts, local_salt):

    template = """
        %- set myvar = 'one'
        ## ignored comment 1
        {{- myvar -}}
        {%- set myvar = 'two' %} ## ignored comment 2
        {{- myvar }} ## ignored comment 3
        %- if myvar == 'two':
        %- set myvar = 'three'
        %- endif
        {{- myvar -}}
        """
    rendered = render_jinja_tmpl(
        template, dict(opts=minion_opts, saltenv="test", salt=local_salt)
    )
    assert rendered == "onetwothree"


def test_statement_prefix(minion_opts, local_salt):

    template = """
        {%- set mylist = ['1', '2', '3'] %}
        %- set mylist = ['one', 'two', 'three']
        %- for item in mylist:
        {{- item }}
        %- endfor
        """
    rendered = render_jinja_tmpl(
        template, dict(opts=minion_opts, saltenv="test", salt=local_salt)
    )
    assert rendered == "onetwothree"

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
            "jinja_env": {
                "lstrip_blocks": True,
                "trim_blocks": False,
            },
            "extension_modules": os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "extmods"
            ),
        }
    )
    return minion_opts


@pytest.fixture
def local_salt():
    return {
        "myvar": "zero",
        "mylist": [0, 1, 2, 3],
    }


def test_blocktrimming(minion_opts, local_salt):
    template = """
#jinja2: { "lstrip_blocks": true, "trim_blocks": true }
#lets count
{% for i in range(3) %}
  {% if i == 1 %}
1337
  {% endif %}
{{ i }}
{% endfor %}
"""

    rendered = render_jinja_tmpl(
        template, dict(opts=minion_opts, saltenv="test", salt=local_salt)
    )

    assert (
        rendered
        == """
#lets count
0
1337
1
2

"""
    )

def test_lstrip_blocks_minionconf(minion_opts, local_salt):
    template = """
#lets count
{% for i in range(3) %}
  {% if i == 1 %}
1337
  {% endif %}
{{ i }}
{% endfor %}
"""

    rendered = render_jinja_tmpl(
        template, dict(opts=minion_opts, saltenv="test", salt=local_salt)
    )

    assert (
        rendered
        == """
#lets count


0


1337

1


2

"""
    )


def test_no_blocktrimming(minion_opts, local_salt):
    template = """
#jinja2: { "lstrip_blocks": false, "trim_blocks": false }
#beware of the whitespace
{% for i in range(3) %}
  {% if i == 1 %}
1337
  {% endif %}
{{ i }}
{% endfor %}
"""

    rendered = render_jinja_tmpl(
        template, dict(opts=minion_opts, saltenv="test", salt=local_salt)
    )

    assert (
        rendered
        == """
#beware of the whitespace

  
0

  
1337
  
1

  
2

"""
    )

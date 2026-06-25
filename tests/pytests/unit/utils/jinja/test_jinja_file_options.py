"""
Tests for the per-file ``#jinja2:`` Jinja environment override header
implemented in salt.utils.templates.render_jinja_tmpl.
"""

import logging
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
        }
    )
    return minion_opts


@pytest.fixture
def local_salt():
    return {
        "myvar": "zero",
        "mylist": [0, 1, 2, 3],
    }


# A body that produces visibly different whitespace depending on whether
# trim_blocks / lstrip_blocks are enabled.
BODY = """\
#lets count
{% for i in range(3) %}
  {% if i == 1 %}
1337
  {% endif %}
{{ i }}
{% endfor %}
"""


def _render(opts, local_salt, template, sls=""):
    context = {"opts": opts, "saltenv": "test", "salt": local_salt}
    if sls:
        context["sls"] = sls
    return render_jinja_tmpl(template, context)


def test_fileopts_match_global_jinja_env(minion_opts, local_salt):
    """
    A ``#jinja2:`` header must produce exactly the same result as setting the
    equivalent options globally via jinja_env -- it is the same machinery,
    just scoped to one file.
    """
    reference = _render(
        {**minion_opts, "jinja_env": {"trim_blocks": True, "lstrip_blocks": True}},
        local_salt,
        BODY,
    )
    with_header = _render(
        {**minion_opts},
        local_salt,
        '#jinja2: {"trim_blocks": true, "lstrip_blocks": true}\n' + BODY,
    )
    assert with_header == reference
    # And the header line itself must not leak into the output.
    assert "#jinja2:" not in with_header


def test_fileopts_override_global(minion_opts, local_salt):
    """
    The per-file header wins over a conflicting global jinja_env setting -- a
    formula can opt OUT of options the operator enabled globally.
    """
    # Global turns trimming on; the file turns it back off.
    opts = {**minion_opts, "jinja_env": {"trim_blocks": True, "lstrip_blocks": True}}
    file_off = _render(
        opts,
        local_salt,
        '#jinja2: {"trim_blocks": false, "lstrip_blocks": false}\n' + BODY,
    )
    # Equivalent to rendering the bare body with no trimming at all.
    no_trim = _render({**minion_opts}, local_salt, BODY)
    assert file_off == no_trim


def test_fileopts_applies_in_sls_context(minion_opts, local_salt):
    """
    The header is honored in the sls render path (jinja_sls_env) too, not just
    the plain jinja_env path.
    """
    reference = _render(
        {**minion_opts, "jinja_sls_env": {"trim_blocks": True, "lstrip_blocks": True}},
        local_salt,
        BODY,
        sls="some.state",
    )
    with_header = _render(
        {**minion_opts},
        local_salt,
        '#jinja2: {"trim_blocks": true, "lstrip_blocks": true}\n' + BODY,
        sls="some.state",
    )
    assert with_header == reference


def test_fileopts_after_renderer_shebang(minion_opts, local_salt):
    """
    When a renderer shebang occupies line 1, the header is honored on line 2.
    The shebang itself is left untouched (it is not stripped before the jinja
    renderer runs); only the header line is removed.
    """
    shebang = "#!jinja|yaml\n"
    reference = _render(
        {**minion_opts, "jinja_env": {"trim_blocks": True, "lstrip_blocks": True}},
        local_salt,
        shebang + BODY,
    )
    with_header = _render(
        {**minion_opts},
        local_salt,
        shebang + '#jinja2: {"trim_blocks": true, "lstrip_blocks": true}\n' + BODY,
    )
    assert with_header == reference
    # The shebang survives; the #jinja2 header does not.
    assert with_header.startswith("#!jinja|yaml")
    assert "#jinja2:" not in with_header


def test_fileopts_shebang_without_header_is_untouched(minion_opts, local_salt):
    """
    A shebang with no following ``#jinja2:`` header applies no options and
    leaves the template (shebang included) unchanged.
    """
    shebang = "#!jinja|yaml\n"
    out = _render({**minion_opts}, local_salt, shebang + BODY)
    plain = _render({**minion_opts}, local_salt, BODY)
    assert out == shebang + plain


def test_fileopts_interpreter_path_is_not_treated_as_shebang(minion_opts, local_salt):
    """
    A ``#!/path`` interpreter line is not a renderer shebang, so the header is
    only looked for on line 1 (which here is the ``#!/`` line) -- meaning a
    header on line 2 is NOT honored.
    """
    template = (
        "#!/usr/bin/env something\n"
        '#jinja2: {"trim_blocks": true, "lstrip_blocks": true}\n' + BODY
    )
    out = _render({**minion_opts}, local_salt, template)
    # Not recognized: the header line is left in place and no trimming applied.
    assert '#jinja2: {"trim_blocks": true, "lstrip_blocks": true}' in out


def test_fileopts_not_at_top_is_ignored(minion_opts, local_salt):
    """
    A ``#jinja2:`` line below the top of the file is treated as ordinary
    content: left in place, with no options applied.
    """
    template = BODY + '#jinja2: {"trim_blocks": true, "lstrip_blocks": true}\n'
    out = _render({**minion_opts}, local_salt, template)
    # Left untouched in the output.
    assert '#jinja2: {"trim_blocks": true, "lstrip_blocks": true}' in out
    # And no trimming was applied: identical to rendering the same text with
    # the default environment.
    reference = _render({**minion_opts}, local_salt, template)
    assert out == reference


def test_fileopts_malformed_json_is_ignored(minion_opts, local_salt, caplog):
    """
    A header whose payload is not valid JSON is left in place, no options are
    applied, and a warning is logged.
    """
    template = "#jinja2: {this is not valid json}\n" + BODY
    with caplog.at_level(logging.WARNING, logger="salt.utils.templates"):
        out = _render({**minion_opts}, local_salt, template)
    assert "#jinja2: {this is not valid json}" in out
    assert any("malformed '#jinja2:'" in rec.message for rec in caplog.records)


def test_fileopts_non_object_json_is_ignored(minion_opts, local_salt, caplog):
    """
    A header whose JSON is valid but not an object (e.g. a list) is ignored
    with a warning rather than crashing.
    """
    template = '#jinja2: ["trim_blocks", "lstrip_blocks"]\n' + BODY
    with caplog.at_level(logging.WARNING, logger="salt.utils.templates"):
        out = _render({**minion_opts}, local_salt, template)
    assert '#jinja2: ["trim_blocks", "lstrip_blocks"]' in out
    assert any("not a JSON object" in rec.message for rec in caplog.records)


def test_fileopts_unrecognized_key_warns_and_renders(minion_opts, local_salt, caplog):
    """
    An unknown Jinja environment option is skipped with a warning; rendering
    still succeeds and the header line is removed.
    """
    template = '#jinja2: {"not_a_real_jinja_option": true}\n' + BODY
    with caplog.at_level(logging.WARNING, logger="salt.utils.templates"):
        out = _render({**minion_opts}, local_salt, template)
    assert "#jinja2:" not in out
    assert any("is not recognized" in rec.message for rec in caplog.records)


def test_fileopts_single_option(minion_opts, local_salt):
    """
    A header may set just one option; it must match enabling only that option
    globally (proving individual options flow through, not just the pair).
    """
    reference = _render(
        {**minion_opts, "jinja_env": {"trim_blocks": True}},
        local_salt,
        BODY,
    )
    with_header = _render(
        {**minion_opts},
        local_salt,
        '#jinja2: {"trim_blocks": true}\n' + BODY,
    )
    assert with_header == reference


def test_fileopts_lone_cr_body_preserved(minion_opts, local_salt):
    """
    Regression: a lone-CR (classic-Mac) template with a recognized header must
    not be silently discarded. The header is removed and the body survives.
    """
    template = '#jinja2: {"trim_blocks": true}\rkept_a: 1\rkept_b: 2\r'
    out = _render({**minion_opts}, local_salt, template)
    assert "#jinja2:" not in out
    assert "kept_a: 1" in out
    assert "kept_b: 2" in out


def test_fileopts_crlf_body_preserved(minion_opts, local_salt):
    """
    A CRLF template with a recognized header keeps the body and drops only the
    header line.
    """
    template = '#jinja2: {"trim_blocks": true}\r\nkept_a: 1\r\nkept_b: 2\r\n'
    out = _render({**minion_opts}, local_salt, template)
    assert "#jinja2:" not in out
    assert "kept_a: 1" in out
    assert "kept_b: 2" in out


def test_fileopts_lone_cr_after_shebang_preserved(minion_opts, local_salt):
    """
    Regression: shebang on line 1 + header on line 2 with lone-CR endings must
    keep both the shebang and the body.
    """
    template = '#!jinja|yaml\r#jinja2: {"trim_blocks": true}\rkept_a: 1\r'
    out = _render({**minion_opts}, local_salt, template)
    assert out.startswith("#!jinja|yaml")
    assert "#jinja2:" not in out
    assert "kept_a: 1" in out


def test_fileopts_header_is_whole_file(minion_opts, local_salt):
    """
    A header that is the entire file (no body, no trailing newline) renders to
    nothing without error.
    """
    out = _render({**minion_opts}, local_salt, '#jinja2: {"trim_blocks": true}')
    assert out == ""


def test_fileopts_header_after_shebang_no_trailing_newline(minion_opts, local_salt):
    """
    Shebang + header with no trailing newline keeps the shebang and removes the
    header.
    """
    out = _render(
        {**minion_opts},
        local_salt,
        '#!jinja|yaml\n#jinja2: {"trim_blocks": true}',
    )
    assert out.startswith("#!jinja|yaml")
    assert "#jinja2:" not in out


def test_fileopts_scalar_json_ignored(minion_opts, local_salt, caplog):
    """
    A header whose JSON is a scalar (not an object) is ignored with a warning.
    """
    template = "#jinja2: 5\n" + BODY
    with caplog.at_level(logging.WARNING, logger="salt.utils.templates"):
        out = _render({**minion_opts}, local_salt, template)
    assert "#jinja2: 5" in out
    assert any("not a JSON object" in rec.message for rec in caplog.records)


def test_fileopts_empty_payload_ignored(minion_opts, local_salt, caplog):
    """
    A bare ``#jinja2:`` with no payload is not an override: it is left in place
    and is not treated as malformed JSON.
    """
    template = "#jinja2:\n" + BODY
    with caplog.at_level(logging.WARNING, logger="salt.utils.templates"):
        out = _render({**minion_opts}, local_salt, template)
    assert "#jinja2:" in out
    assert not any("malformed" in rec.message for rec in caplog.records)


def test_fileopts_only_first_header_consumed(minion_opts, local_salt):
    """
    Only the top header is consumed; a second ``#jinja2:`` line is left as
    ordinary content.
    """
    template = (
        '#jinja2: {"trim_blocks": true}\n' '#jinja2: {"lstrip_blocks": true}\n' + BODY
    )
    out = _render({**minion_opts}, local_salt, template)
    assert out.count("#jinja2:") == 1
    assert '#jinja2: {"lstrip_blocks": true}' in out


def test_fileopts_indented_header_ignored(minion_opts, local_salt):
    """
    A header indented by leading whitespace is treated as content (the anchor
    is byte 0 of the line, matching Ansible).
    """
    template = '  #jinja2: {"trim_blocks": true}\n' + BODY
    out = _render({**minion_opts}, local_salt, template)
    assert "#jinja2:" in out


def test_fileopts_empty_template(minion_opts, local_salt):
    """
    An empty template renders to empty without error.
    """
    assert _render({**minion_opts}, local_salt, "") == ""

"""
Tests for the towncrier changelog template at ``changelog/.template.jinja``.

These tests guard against the regression reported in saltstack/salt#69454,
where the template split every multi-line fragment into a separate top-level
bullet and appended the issue link to each one.
"""

import pathlib

import pytest

jinja2 = pytest.importorskip("jinja2")


REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
TEMPLATE_PATH = REPO_ROOT / "changelog" / ".template.jinja"

ISSUE_LINK = "[#69031](https://github.com/saltstack/salt/issues/69031)"

DEFINITIONS = {
    "fixed": {"name": "Fixed", "showcontent": True},
    "added": {"name": "Added", "showcontent": True},
}


def _render(text, category="fixed", link=ISSUE_LINK):
    template_src = TEMPLATE_PATH.read_text()
    template = jinja2.Template(template_src)
    sections = {"": {category: {text: [link]}}}
    return template.render(sections=sections, definitions=DEFINITIONS)


def test_single_line_fragment_renders_as_one_bullet():
    """A one-line fragment renders as exactly one bullet with the link appended once."""
    rendered = _render("Fixed a simple bug.")
    bullets = [line for line in rendered.splitlines() if line.lstrip().startswith("- ")]
    assert len(bullets) == 1
    assert rendered.count(ISSUE_LINK) == 1
    assert "- Fixed a simple bug." in rendered


def test_multi_line_fragment_renders_as_one_bullet():
    """
    A multi-line wrapped fragment must produce a single top-level bullet whose
    continuation lines are indented under it, and the issue link must appear
    exactly once -- at the end of the bullet.

    Regression test for saltstack/salt#69454.
    """
    text = (
        "Fixed two distinct bugs in the `salt.engines.redis_sentinel` engine that\n"
        "together prevented it from being usable. `start()` no longer raises\n"
        "`AttributeError: 'dict_values' object has no attribute 'pop'` on Python 3\n"
        "(the dict.values() result is now wrapped in `list(...)`). `Listener` and\n"
        "`start()` now accept an optional `password` argument and forward it to\n"
        "the redis client, allowing the engine to authenticate against a Sentinel\n"
        "that requires AUTH; the default of `None` keeps existing configurations\n"
        "working unchanged."
    )
    rendered = _render(text)

    # Exactly one top-level bullet for the whole fragment.
    top_level_bullets = [
        line for line in rendered.splitlines() if line.startswith("- ")
    ]
    assert len(top_level_bullets) == 1, (
        "Multi-line fragment must collapse into a single top-level bullet; "
        f"got {len(top_level_bullets)} bullets in:\n{rendered}"
    )

    # The issue link must appear exactly once.
    assert (
        rendered.count(ISSUE_LINK) == 1
    ), f"Issue link should appear exactly once; rendered output:\n{rendered}"

    # The first line of the fragment is the bullet's first line.
    assert (
        "- Fixed two distinct bugs in the `salt.engines.redis_sentinel` engine that"
        in rendered
    )

    # Continuation lines from the fragment are preserved (with indentation),
    # not split onto separate bullets.
    assert "together prevented it from being usable." in rendered
    assert "working unchanged." in rendered

    # The link is appended after the last line of the fragment.
    assert f"working unchanged. {ISSUE_LINK}" in rendered


def test_multi_line_fragment_continuation_is_indented():
    """
    Continuation lines under a bullet must be indented so Markdown treats them
    as part of the same list item rather than as a new paragraph.
    """
    text = "First line of the entry.\nSecond line of the entry."
    rendered = _render(text)

    lines = rendered.splitlines()
    # Find the bullet line.
    bullet_idx = next(
        i for i, line in enumerate(lines) if line.startswith("- First line")
    )
    # The next non-empty line should be the indented continuation.
    continuation = next(line for line in lines[bullet_idx + 1 :] if line.strip())
    assert continuation.startswith("  "), (
        f"Continuation line should be indented with at least two spaces; got: "
        f"{continuation!r}"
    )
    assert "Second line of the entry." in continuation


def test_multiple_fragments_each_get_their_own_bullet():
    """Two independent fragments produce two bullets, each with their own link."""
    template_src = TEMPLATE_PATH.read_text()
    template = jinja2.Template(template_src)
    link_a = "[#1](https://github.com/saltstack/salt/issues/1)"
    link_b = "[#2](https://github.com/saltstack/salt/issues/2)"
    sections = {
        "": {
            "fixed": {
                "Fixed bug A.": [link_a],
                "Fixed multi-line bug B that\nwraps across two lines.": [link_b],
            }
        }
    }
    rendered = template.render(sections=sections, definitions=DEFINITIONS)
    top_level_bullets = [
        line for line in rendered.splitlines() if line.startswith("- ")
    ]
    assert len(top_level_bullets) == 2
    assert rendered.count(link_a) == 1
    assert rendered.count(link_b) == 1
    assert f"Fixed bug A. {link_a}" in rendered
    assert f"wraps across two lines. {link_b}" in rendered


def test_fragment_with_markdown_sub_bullets_preserves_structure():
    """
    A fragment that uses Markdown-style indented sub-bullets must still
    produce a single top-level bullet, with the sub-bullets nested under it.
    """
    text = (
        "Refactored server-side PKI to support cache interface\n"
        "  - optimization: defer _pki_minions fetch\n"
        "  - refactor: push salt.utils.minions bits into salt.key"
    )
    link = "[#67799](https://github.com/saltstack/salt/issues/67799)"
    template_src = TEMPLATE_PATH.read_text()
    template = jinja2.Template(template_src)
    sections = {"": {"added": {text: [link]}}}
    rendered = template.render(sections=sections, definitions=DEFINITIONS)

    top_level_bullets = [
        line for line in rendered.splitlines() if line.startswith("- ")
    ]
    assert (
        len(top_level_bullets) == 1
    ), f"Expected one top-level bullet; got:\n{rendered}"
    # The link appears exactly once.
    assert rendered.count(link) == 1
    # The sub-bullets remain present as indented list items.
    assert "- optimization: defer _pki_minions fetch" in rendered
    assert "- refactor: push salt.utils.minions bits into salt.key" in rendered

"""
Targeting by pillar reads the stored values, not the redacted repr, so it works
on masked pillar data.
"""

import pytest

import salt.matchers.pillar_match as pillar_match
import salt.matchers.pillar_pcre_match as pillar_pcre_match
import salt.utils.data
import salt.utils.secret as secret


@pytest.fixture
def pillar():
    return secret.hide(
        {"role": "web", "app": {"name": "foo", "ports": [80, 443]}, "n": 5}
    )


@pytest.mark.parametrize(
    "tgt,expected",
    [
        ("role:web", True),
        ("role:w*", True),
        ("app:name:foo", True),
        ("app:ports:80", True),
        ("n:5", True),
        ("role:db", False),
    ],
)
def test_pillar_matchers(pillar, tgt, expected):
    opts = {"pillar": pillar}
    assert bool(pillar_match.match(tgt, opts=opts)) is expected
    assert bool(pillar_pcre_match.match(tgt, opts=opts)) is expected
    assert salt.utils.data.subdict_match(pillar, tgt) is expected

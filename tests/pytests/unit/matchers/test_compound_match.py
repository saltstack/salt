import pytest

from salt.matchers import compound_match, glob_match, grain_match, pillar_match
from salt.utils.context import func_globals_inject


@pytest.mark.parametrize(
    "tgt, expected",
    [
        ("minion1", True),  # Simple Glob fallback
        ("minion2", False),  # Simple Glob fallback
        (
            "G@example-grain:True and I@example-pillar:True",
            True,
        ),  # Engine dispatch (Grain & Pillar)
        ("G@example-grain:True or I@false", True),  # Boolean OR
        ("G@example-grain:True and I@false", False),  # Boolean AND
        ("not G@false", True),  # NOT operator
        (
            "( G@example-grain:True or I@false ) and G@example-grain:True",
            True,
        ),  # Complex nesting
        (
            ["G@example-grain:True", "and", "I@example-pillar:True"],
            True,
        ),  # List input support
        # Failure Cases
        (
            "(G@example-grain:True or I@false) and G@example-grain:True",
            False,
        ),  # No space around parens
        ("and true", False),  # Invalid start
        ("G@true and (I@true", False),  # Unclosed parenthesis
        ("G@unknown:engine", False),  # Unrecognized engine prefix
        (12345, False),  # Invalid type (int)
        (None, False),  # Invalid type (None)
    ],
)
def test_compound_match(tgt, expected):
    """Tests that valid expressions, engines, and globs evaluate correctly."""
    with func_globals_inject(
        compound_match.match,
        __opts__={},
        __matchers__={
            "glob_match.match": glob_match.match,
            "grain_match.match": grain_match.match,
            "pillar_match.match": pillar_match.match,
        },
    ):
        assert (
            compound_match.match(
                tgt,
                opts={
                    "id": "minion1",
                    "grains": {"example-grain": True},
                    "pillar": {"example-pillar": True},
                },
                minion_id="minion1",
            )
            == expected
        )

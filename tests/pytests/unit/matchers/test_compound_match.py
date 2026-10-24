import pytest

from salt.matchers import compound_match, glob_match, grain_match, pillar_match
from salt.utils.context import func_globals_inject


@pytest.mark.parametrize(
    "tgt, expected",
    [
        # Simple Glob fallback
        ("minion1", True),
        ("minion2", False),
        # Grain & Pillar
        (
            "G@example-grain:True and I@example-pillar:True",
            True,
        ),
        # Boolean OR / AND
        ("G@example-grain:True or I@false", True),
        ("G@example-grain:True and I@false", False),
        ("not G@false", True),  # NOT operator
        # Complex nesting
        (
            "( G@example-grain:True or I@false ) and G@example-grain:True",
            True,
        ),
        # List inputs
        (
            ["G@example-grain:True", "and", "I@example-pillar:True"],
            True,
        ),
        ## Failure Cases ##
        # No space around parens
        (
            "(G@example-grain:True or I@false) and G@example-grain:True",
            False,
        ),
        # Invalid start
        ("and true", False),
        # Unclosed parenthesis
        ("G@true and (I@true", False),
        # Unrecognized engine prefix
        ("G@unknown:engine", False),
        # Invalid type int / None
        (12345, False),
        (None, False),
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

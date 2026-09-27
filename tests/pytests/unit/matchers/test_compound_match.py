import pytest

from salt.matchers import compound_match
from salt.utils.context import func_globals_inject
from tests.support.mock import MagicMock, patch


@pytest.fixture
def matchers():
    matchers = {
        "grain_match.match": MagicMock(),
        "pillar_match.match": MagicMock(),
        "glob_match.match": MagicMock(),
    }
    with func_globals_inject(compound_match, __matchers__=matchers, __opts__={}):
        yield matchers


@pytest.mark.parametrize(
    "tgt, expected",
    [
        # --- Success Cases ---
        ("true", True),  # Simple Glob fallback
        ("false", False),  # Simple Glob fallback
        ("G:true and I:true", True),  # Engine dispatch (Grain & Pillar)
        ("G:true or I:false", True),  # Boolean OR
        ("G:true and I:false", False),  # Boolean AND
        ("not G:false", True),  # NOT operator
        ("(G:true or I:false) and G:true", True),  # Complex nesting
        (["G:true", "and", "I:true"], True),  # List input support
    ],
)
def test_compound_match_success(matchers, tgt, expected):
    """Tests that valid expressions, engines, and globs evaluate correctly."""

    def side_effect(pattern, *args, **kwargs):
        return pattern == "true"

    for m in matchers.values():
        m.side_effect = side_effect

    assert compound_match.match(tgt, opts={}, minion_id="id") == expected


@pytest.mark.parametrize(
    "tgt",
    [
        # --- Failure Cases ---
        ("and true",),  # Invalid start
        ("G:true and (I:true",),  # Unclosed parenthesis
        ("G:unknown:engine",),  # Unrecognized engine prefix
        (12345,),  # Invalid type (int)
        (None,),  # Invalid type (None)
    ],
)
def test_compound_match_failure(matchers, tgt):
    """Tests that malformed inputs return False gracefully."""
    assert compound_match.match(tgt, opts={}, minion_id="id") is False


@pytest.mark.parametrize(
    "tgt, expansion, expected",
    [
        # --- Scenario 1: Successful Expansion ---
        ("N:group1", ["A", "or", "B"], True),
        # --- Scenario 2: Expansion + Boolean Logic ---
        ("N:group1 and G:true", ["A", "and", "B"], False),
        # --- Scenario 3: Expansion resulting in a single word ---
        ("N:group1 or G:false", ["true"], True),
    ],
)
def test_compound_match_nodegroup_expansion(
    mock_matchers_expansion, tgt, expansion, expected
):
    """Verifies that the 'N' engine correctly expands target words."""
    matchers = mock_matchers_expansion

    def expanded_side_effect(pattern, *args, **kwargs):
        return pattern in ["A", "B", "true"]

    matchers["glob_match.match"].side_effect = expanded_side_effect
    matchers["grain_match.match"].side_effect = expanded_side_effect

    with patch("salt.utils.minions.nodegroup_comp") as mock_nodegroup:
        mock_nodegroup.return_value = expansion
        opts = {"nodegroups": {"group1": ["minion_a"]}}

        result = compound_match.match(tgt, opts=opts, minion_id="id")
        assert result == expected
        mock_nodegroup.assert_called_once()


def test_compound_match_nodegroup_empty_expansion(mock_matchers_expansion):
    """Verifies that an empty expansion handles syntax errors gracefully."""
    mock_matchers_expansion["glob_match.match"].return_value = True

    with patch("salt.utils.minions.nodegroup_comp") as mock_nodegroup:
        mock_nodegroup.return_value = []
        assert (
            compound_match.match(
                "G:true or N:group1", opts={"nodegroups": {}}, minion_id="id"
            )
            is False
        )

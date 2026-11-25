"""
Tests for salt.config.loader_validation -- the hand-rolled validator
for the loader_validate_* family of opts.
"""

import pytest

from salt.config.loader_validation import (
    KNOWN_LOADER_NAMES,
    VALID_MODES,
    validate_loader_validation_opts,
)


class TestTierDefaults:
    def test_all_empty_passes(self):
        assert validate_loader_validation_opts({}) is True

    @pytest.mark.parametrize("mode", sorted(VALID_MODES))
    def test_valid_mode_passes(self, mode):
        assert (
            validate_loader_validation_opts({"loader_validate_wire_input_mode": mode})
            is True
        )

    def test_invalid_tier_mode_raises(self):
        with pytest.raises(ValueError, match="not a valid mode"):
            validate_loader_validation_opts(
                {"loader_validate_wire_input_mode": "enforcee"}
            )

    def test_non_string_tier_mode_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            validate_loader_validation_opts({"loader_validate_wire_input_mode": 42})

    def test_all_four_tier_opts_checked(self):
        """Every one of the four tier opts should be validated."""
        with pytest.raises(ValueError, match="not a valid mode") as exc:
            validate_loader_validation_opts(
                {
                    "loader_validate_wire_input_mode": "bogus1",
                    "loader_validate_wire_return_mode": "bogus2",
                    "loader_validate_internal_input_mode": "bogus3",
                    "loader_validate_internal_return_mode": "bogus4",
                }
            )
        # All four errors accumulated into one message.
        text = str(exc.value)
        assert "bogus1" in text
        assert "bogus2" in text
        assert "bogus3" in text
        assert "bogus4" in text


class TestOverrides:
    def test_valid_overrides_pass(self):
        opts = {
            "loader_validate_overrides": {
                "states": {"input_mode": "strict", "return_mode": "enforce"},
                "wire_salt": {"input_mode": "warn"},
            }
        }
        assert validate_loader_validation_opts(opts) is True

    def test_overrides_not_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            validate_loader_validation_opts(
                {"loader_validate_overrides": ["not", "a", "dict"]}
            )

    def test_unknown_loader_name_raises(self):
        with pytest.raises(ValueError, match="unknown loader"):
            validate_loader_validation_opts(
                {
                    "loader_validate_overrides": {
                        "nonexistent_loader": {"input_mode": "strict"}
                    }
                }
            )

    def test_known_loader_names_include_wire_set(self):
        for name in ("wire_salt", "salt_dunder", "states", "runners", "wheels"):
            assert name in KNOWN_LOADER_NAMES

    def test_unknown_direction_key_raises(self):
        with pytest.raises(ValueError, match="not a valid direction key"):
            validate_loader_validation_opts(
                {
                    "loader_validate_overrides": {
                        "states": {"inpit_mode": "strict"}  # typo
                    }
                }
            )

    def test_invalid_mode_value_raises(self):
        with pytest.raises(ValueError, match="not a valid mode"):
            validate_loader_validation_opts(
                {
                    "loader_validate_overrides": {
                        "states": {"input_mode": "strcit"}  # typo
                    }
                }
            )

    def test_override_entry_not_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            validate_loader_validation_opts(
                {"loader_validate_overrides": {"states": "strict"}}
            )

    def test_accumulates_multiple_errors(self):
        """One raise, every problem in the message."""
        with pytest.raises(ValueError, match="bogus") as exc:
            validate_loader_validation_opts(
                {
                    "loader_validate_wire_input_mode": "bogus",
                    "loader_validate_overrides": {
                        "nonexistent": {"input_mode": "strict"},
                        "states": {"input_mode": "also-bogus"},
                    },
                }
            )
        text = str(exc.value)
        assert "bogus" in text
        assert "nonexistent" in text
        assert "also-bogus" in text


class TestResolver:
    """The resolver lives in salt.loader.lazy; test its behavior directly."""

    def test_override_wins_over_tier(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_wire_input_mode": "warn",
            "loader_validate_overrides": {
                "states": {"input_mode": "strict"},
            },
        }
        assert _resolve_validate_mode(opts, "states", True, "input") == "strict"

    def test_tier_wins_when_no_override(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {"loader_validate_wire_input_mode": "enforce"}
        assert _resolve_validate_mode(opts, "wire_salt", True, "input") == "enforce"

    def test_internal_tier_for_non_wire(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_wire_input_mode": "strict",
            "loader_validate_internal_input_mode": "off",
        }
        # is_wire_loader=False -> internal tier is consulted.
        assert _resolve_validate_mode(opts, "salt_dunder", False, "input") == "off"

    def test_override_without_direction_falls_through_to_tier(self):
        """If the override entry lacks the requested direction, fall
        back to the tier default for that direction."""
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_wire_return_mode": "enforce",
            "loader_validate_overrides": {
                "states": {"input_mode": "strict"},  # no return_mode
            },
        }
        assert _resolve_validate_mode(opts, "states", True, "return") == "enforce"

    def test_unnamed_loader_skips_override_lookup(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_wire_input_mode": "warn",
            "loader_validate_overrides": {
                "states": {"input_mode": "strict"},
            },
        }
        # No loader name -> override dict is ignored; tier wins.
        assert _resolve_validate_mode(opts, None, True, "input") == "warn"

    def test_hard_default_when_everything_missing(self):
        from salt.loader.lazy import _resolve_validate_mode

        assert _resolve_validate_mode({}, "states", True, "input") == "off"

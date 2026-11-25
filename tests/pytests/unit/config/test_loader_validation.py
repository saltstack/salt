"""
Tests for salt.config.loader_validation -- the hand-rolled validator
for the loader_validate_overrides opt.
"""

import pytest

from salt.config.loader_validation import (
    KNOWN_LOADER_NAMES,
    VALID_MODES,
    validate_loader_validation_opts,
)


class TestOverrides:
    def test_all_empty_passes(self):
        assert validate_loader_validation_opts({}) is True

    def test_empty_overrides_dict_passes(self):
        assert (
            validate_loader_validation_opts({"loader_validate_overrides": {}}) is True
        )

    @pytest.mark.parametrize("mode", sorted(VALID_MODES))
    def test_valid_mode_passes(self, mode):
        assert (
            validate_loader_validation_opts(
                {"loader_validate_overrides": {"states": {"input_mode": mode}}}
            )
            is True
        )

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

    def test_non_string_mode_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            validate_loader_validation_opts(
                {"loader_validate_overrides": {"states": {"input_mode": 42}}}
            )

    def test_override_entry_not_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            validate_loader_validation_opts(
                {"loader_validate_overrides": {"states": "strict"}}
            )

    def test_accumulates_multiple_errors(self):
        """One raise, every problem in the message."""
        with pytest.raises(ValueError, match="nonexistent") as exc:
            validate_loader_validation_opts(
                {
                    "loader_validate_overrides": {
                        "nonexistent": {"input_mode": "strict"},
                        "states": {"input_mode": "also-bogus"},
                    },
                }
            )
        text = str(exc.value)
        assert "nonexistent" in text
        assert "also-bogus" in text


class TestResolver:
    """The resolver lives in salt.loader.lazy; test its behavior directly."""

    def test_override_resolves(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_overrides": {
                "states": {"input_mode": "strict"},
            },
        }
        assert _resolve_validate_mode(opts, "states", "input") == "strict"

    def test_missing_override_entry_defaults_off(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_overrides": {
                "states": {"input_mode": "strict"},
            },
        }
        # Named loader with no matching override entry.
        assert _resolve_validate_mode(opts, "wire_salt", "input") == "off"

    def test_override_without_direction_defaults_off(self):
        """If the override entry lacks the requested direction, resolve
        to off."""
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_overrides": {
                "states": {"input_mode": "strict"},  # no return_mode
            },
        }
        assert _resolve_validate_mode(opts, "states", "return") == "off"

    def test_unnamed_loader_always_off(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_overrides": {
                "states": {"input_mode": "strict"},
            },
        }
        # No loader name -> override dict is ignored.
        assert _resolve_validate_mode(opts, None, "input") == "off"

    def test_hard_default_when_everything_missing(self):
        from salt.loader.lazy import _resolve_validate_mode

        assert _resolve_validate_mode({}, "states", "input") == "off"

    def test_each_direction_resolved_independently(self):
        from salt.loader.lazy import _resolve_validate_mode

        opts = {
            "loader_validate_overrides": {
                "states": {"input_mode": "strict", "return_mode": "warn"},
            },
        }
        assert _resolve_validate_mode(opts, "states", "input") == "strict"
        assert _resolve_validate_mode(opts, "states", "return") == "warn"

"""
Validation for loader validation opts.

Catches typos and malformed structure in the ``loader_validate_*``
family of opts at daemon startup rather than letting them silently
fall back to ``"off"`` via ``opts.get(..., "off")`` at dispatch time.

Four flat tier-default opts are checked:

* ``loader_validate_wire_input_mode``
* ``loader_validate_wire_return_mode``
* ``loader_validate_internal_input_mode``
* ``loader_validate_internal_return_mode``

Plus one nested dict opt for per-loader overrides::

    loader_validate_overrides:
      states:
        input_mode: strict
        return_mode: strict
      grains:
        input_mode: off

The validator matches the ``salt.config.worker_pools.validate_worker_pools_config``
pattern: accumulate every problem into an error list, raise once at the
end so operators can fix the whole file in one pass.

Called from ``LazyLoader.__init__`` so every daemon that constructs a
loader (master, minion, salt-call, salt-api) surfaces configuration
errors at startup.
"""

from collections.abc import Mapping

# Valid values for every ``*_mode`` opt.
VALID_MODES = frozenset({"off", "warn", "enforce", "strict"})

# Loader names the per-loader override dict is allowed to key on.
# Must match the ``name=`` kwarg set by factories in
# ``salt/loader/__init__.py``. Keys the dict can't recognize would
# silently no-op at dispatch time -- an unacceptable silent-drop (see
# the research in ``agents/reports/nested_config_precedents.md``), so
# unknown override keys raise.
KNOWN_LOADER_NAMES = frozenset(
    {
        "wire_salt",
        "salt_dunder",
        "states",
        "runners",
        "wheels",
    }
)

# Valid direction keys inside a per-loader override entry.
_VALID_DIRECTION_KEYS = frozenset({"input_mode", "return_mode"})

# The four top-level tier-default opts. Checked for valid mode values.
_TIER_OPT_KEYS = (
    "loader_validate_wire_input_mode",
    "loader_validate_wire_return_mode",
    "loader_validate_internal_input_mode",
    "loader_validate_internal_return_mode",
)


# Sentinel attached to the opts dict once validation has succeeded, so
# subsequent LazyLoader.__init__ calls against the same opts can
# short-circuit instead of re-validating the same dict ~25 times per
# daemon startup.
_VALIDATED_SENTINEL = "_salt_loader_validation_opts_validated"


def validate_loader_validation_opts(opts):
    """Validate the loader_validate_* family of opts.

    Returns ``True`` on success. Raises :class:`ValueError` with a
    newline-joined error message on failure -- every problem the
    validator finds is accumulated, matching the pattern in
    :func:`salt.config.worker_pools.validate_worker_pools_config`.

    :param dict opts: The Salt configuration dictionary.
    :returns: ``True`` when the configuration is valid.
    :raises ValueError: If any loader_validate_* opt is malformed.
    """
    if opts.get(_VALIDATED_SENTINEL):
        return True

    errors = []

    # 1. Tier-default opts must be one of VALID_MODES.
    for key in _TIER_OPT_KEYS:
        if key not in opts:
            continue
        value = opts[key]
        if not isinstance(value, str):
            errors.append(f"{key}: must be a string, got {type(value).__name__}")
            continue
        if value not in VALID_MODES:
            errors.append(
                f"{key}: {value!r} is not a valid mode "
                f"(expected one of {sorted(VALID_MODES)})"
            )

    # 2. Overrides dict structure.
    overrides = opts.get("loader_validate_overrides", {})
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, Mapping):
        errors.append(
            f"loader_validate_overrides: must be a dict, "
            f"got {type(overrides).__name__}"
        )
        raise ValueError("\n".join(errors))

    for loader_name, loader_cfg in overrides.items():
        if not isinstance(loader_name, str):
            errors.append(
                f"loader_validate_overrides: key must be a string, "
                f"got {type(loader_name).__name__}"
            )
            continue
        if loader_name not in KNOWN_LOADER_NAMES:
            errors.append(
                f"loader_validate_overrides.{loader_name}: unknown loader "
                f"(known: {sorted(KNOWN_LOADER_NAMES)})"
            )
            continue
        if not isinstance(loader_cfg, Mapping):
            errors.append(
                f"loader_validate_overrides.{loader_name}: must be a dict, "
                f"got {type(loader_cfg).__name__}"
            )
            continue
        for direction_key, mode in loader_cfg.items():
            if direction_key not in _VALID_DIRECTION_KEYS:
                errors.append(
                    f"loader_validate_overrides.{loader_name}.{direction_key}: "
                    f"not a valid direction key "
                    f"(expected one of {sorted(_VALID_DIRECTION_KEYS)})"
                )
                continue
            if not isinstance(mode, str):
                errors.append(
                    f"loader_validate_overrides.{loader_name}.{direction_key}: "
                    f"must be a string, got {type(mode).__name__}"
                )
                continue
            if mode not in VALID_MODES:
                errors.append(
                    f"loader_validate_overrides.{loader_name}.{direction_key}: "
                    f"{mode!r} is not a valid mode "
                    f"(expected one of {sorted(VALID_MODES)})"
                )

    if errors:
        raise ValueError("\n".join(errors))

    # Cache the success so sibling LazyLoaders built from the same opts
    # dict don't re-run the check.
    try:
        opts[_VALIDATED_SENTINEL] = True
    except (TypeError, AttributeError):  # pragma: no cover
        # opts is a frozen/immutable mapping -- fine, just skip caching.
        pass
    return True

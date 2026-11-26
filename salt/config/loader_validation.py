"""
Validation for the loader_validate_* opts.

Catches typos and malformed structure in ``loader_validate_overrides``
and ``loader_validate_defaults`` at daemon startup rather than letting
them silently fall back to ``"off"`` via ``opts.get(..., "off")`` at
dispatch time.

``loader_validate_overrides`` is a dict keyed by loader name, each
value a dict with optional ``input_mode`` / ``return_mode`` entries.
``loader_validate_defaults`` has the same per-direction shape but is
unkeyed -- it applies to any loader without a matching override entry.

::

    loader_validate_defaults:
      input_mode: warn
      return_mode: warn
    loader_validate_overrides:
      states:
        input_mode: strict
        return_mode: strict

Resolution at dispatch (in :func:`salt.loader.lazy._resolve_validate_mode`):
overrides win, then defaults, then hard-coded ``"off"``.

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


def _validate_direction_map(cfg, errors, path):
    """Validate a mapping of ``{<direction>_mode: <mode>}`` entries.

    Shared between ``loader_validate_defaults`` (top-level direction map)
    and each entry under ``loader_validate_overrides``. Accumulates
    errors into ``errors``; ``path`` prefixes the error messages so the
    operator can locate the offending line.
    """
    if not isinstance(cfg, Mapping):
        errors.append(f"{path}: must be a dict, got {type(cfg).__name__}")
        return
    for direction_key, mode in cfg.items():
        if direction_key not in _VALID_DIRECTION_KEYS:
            errors.append(
                f"{path}.{direction_key}: not a valid direction key "
                f"(expected one of {sorted(_VALID_DIRECTION_KEYS)})"
            )
            continue
        if not isinstance(mode, str):
            errors.append(
                f"{path}.{direction_key}: must be a string, "
                f"got {type(mode).__name__}"
            )
            continue
        if mode not in VALID_MODES:
            errors.append(
                f"{path}.{direction_key}: {mode!r} is not a valid mode "
                f"(expected one of {sorted(VALID_MODES)})"
            )


def validate_loader_validation_opts(opts):
    """Validate ``loader_validate_overrides`` and ``loader_validate_defaults``.

    Returns ``True`` on success. Raises :class:`ValueError` with a
    newline-joined error message on failure -- every problem the
    validator finds is accumulated, matching the pattern in
    :func:`salt.config.worker_pools.validate_worker_pools_config`.

    Called once per :class:`LazyLoader` constructor. A minion creates
    ~25 loaders at startup; each validation call is a few 10s of
    microseconds against the small loader_validate_* key set, so the
    total boot cost is well under 1ms.

    :param dict opts: The Salt configuration dictionary.
    :returns: ``True`` when the configuration is valid.
    :raises ValueError: If any loader_validate_* opt is malformed.
    """
    errors = []

    # Defaults (top-level direction map applied when a loader has no
    # override entry for the direction).
    defaults = opts.get("loader_validate_defaults", {})
    if defaults is not None and defaults:
        _validate_direction_map(defaults, errors, "loader_validate_defaults")

    # Per-loader overrides.
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
        _validate_direction_map(
            loader_cfg, errors, f"loader_validate_overrides.{loader_name}"
        )

    if errors:
        raise ValueError("\n".join(errors))

    return True

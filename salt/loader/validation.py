"""
Loader-level input and state-return validation for Salt modules.

Hooks into ``LazyLoader._load_module`` to wrap annotated callables with
pydantic-driven validation. Behavior is controlled by the
``loader_validate_mode`` option:

* ``off`` (default) -- no wrapping; loader behaves as before.
* ``warn`` -- validate on every call; on failure log and pass through.
* ``strict`` -- validate on every call; on failure raise
  ``SaltInvocationError``.

Annotation-driven -- no per-function decorators required. A module author
writes a plain Python function with type hints and the loader installs the
wrapper at load time. The same hook runs for core modules, ``saltext.*``
extensions, and third-party modules under ``file_roots/_modules/`` because
everything flows through the loader. Functions on modules that don't go
through the loader are untouched.

Reserved kwargs injected by the publish layer and state compiler
(``__pub_*``, ``__id__``, ``__sls__``, ...) are filtered out of the
validation input and forwarded unchanged to the underlying function, so
module authors never have to declare them in signatures.

Functions in ``salt.states.*`` additionally get their return validated
against the universal ``StateReturn`` contract regardless of annotations.
"""

import functools
import inspect
import logging
import typing

try:
    from pydantic import BaseModel, ConfigDict, ValidationError, create_model

    HAS_PYDANTIC = True
except ImportError:  # pragma: no cover
    HAS_PYDANTIC = False

from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


# Keyword arguments injected by Salt's publish layer and state compiler.
# These are stripped from validation input and forwarded unchanged to the
# wrapped function, so module authors do not have to declare them.
#
# Sourced from salt.state.STATE_RUNTIME_KEYWORDS (the canonical state-compiler
# set), filtered to just dunder-named entries. Plain-name runtime keywords
# like 'failhard', 'onlyif', 'retry' are stripped by the state compiler
# before dispatch and never reach the loader, so they aren't needed here.
# The import is deferred to avoid a circular import: salt.state imports
# salt.loader which transitively imports this module.
_RESERVED_KWARGS_CACHE = None


def _reserved_kwargs():
    global _RESERVED_KWARGS_CACHE
    if _RESERVED_KWARGS_CACHE is None:
        try:
            from salt.state import STATE_RUNTIME_KEYWORDS

            _RESERVED_KWARGS_CACHE = frozenset(
                k for k in STATE_RUNTIME_KEYWORDS if k.startswith("__")
            )
        except ImportError:
            _RESERVED_KWARGS_CACHE = frozenset()
    return _RESERVED_KWARGS_CACHE


def __getattr__(name):
    # PEP 562: resolve RESERVED_KWARGS lazily from salt.state's canonical set.
    if name == "RESERVED_KWARGS":
        return _reserved_kwargs()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Loader tags whose function returns are validated against StateReturn.
_STATE_LOADER_TAGS = frozenset({"states"})


_VALID_MODES = frozenset({"off", "warn", "strict"})


if HAS_PYDANTIC:
    SALT_VALIDATE_CONFIG = ConfigDict(
        arbitrary_types_allowed=True,
        # Lax coercion: CLI strings ("30", "true") coerce to declared type.
        strict=False,
        # Reserved kwargs are already stripped by the wrapper, but keep
        # extras tolerant for anything we missed.
        extra="ignore",
    )

    class StateReturn(BaseModel):
        """Universal contract for ``salt.states.*`` function returns.

        Every state function's return must satisfy this shape. Enforced at
        loader-wrap time so a module returning ``result='True'`` (string)
        rather than ``result=True`` (bool) is caught at the module, not
        three layers downstream in ``State.call``.
        """

        model_config = SALT_VALIDATE_CONFIG

        name: str
        changes: dict
        result: bool | None
        comment: str | list
        warnings: list | None = None
        pchanges: dict | None = None


def _has_annotations(fn):
    """Return True if the function has any parameter or return annotation."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    for param in sig.parameters.values():
        if param.annotation is not inspect.Parameter.empty:
            return True
    return sig.return_annotation is not inspect.Signature.empty


def _build_input_model(fn):
    """Build a pydantic model mirroring the function's non-var parameters.

    Returns ``(Model, sig)`` or ``(None, None)`` when no model can be built.
    Variadic positional / keyword params are skipped -- ``*args`` and
    ``**kwargs`` can accept anything, and pydantic ``extra='ignore'`` takes
    care of forwarded kwargs beyond what's declared.
    """
    if not HAS_PYDANTIC:
        return None, None
    try:
        sig = inspect.signature(fn)
        # inspect.get_annotations (3.10+) sidesteps importing typing's
        # 3.14-only annotationlib machinery during pylint inference.
        hints = inspect.get_annotations(fn, eval_str=True)
    except (TypeError, ValueError, NameError):
        return None, None

    fields = {}
    for name, param in sig.parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = hints.get(name, typing.Any)
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[name] = (annotation, default)

    if not fields:
        return None, sig

    model_name = f"_{fn.__module__.replace('.', '_')}_{fn.__name__}_Input"
    try:
        model = create_model(
            model_name,
            __config__=SALT_VALIDATE_CONFIG,
            **fields,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        # Any pydantic schema-build failure should degrade to no validation
        # for that one function, never break loader_module.
        log.debug(
            "Could not build input model for %s.%s",
            fn.__module__,
            fn.__name__,
            exc_info=True,
        )
        return None, sig
    return model, sig


def _is_reserved(name, reserved_set):
    """A kwarg is reserved if it is in the state-compiler's canonical set,
    or has the ``__pub_`` prefix (publish-layer convention). The prefix
    check catches keys like ``__pub_schedule`` / ``__pub_stamp`` that the
    publish layer injects but the state compiler doesn't know about.
    """
    return name in reserved_set or name.startswith("__pub_")


def _split_reserved(kwargs):
    """Partition kwargs into (non-reserved, reserved) dicts."""
    reserved_set = _reserved_kwargs()
    reserved = {k: v for k, v in kwargs.items() if _is_reserved(k, reserved_set)}
    if not reserved:
        return kwargs, reserved
    non_reserved = {
        k: v for k, v in kwargs.items() if not _is_reserved(k, reserved_set)
    }
    return non_reserved, reserved


def _check_state_return(fn, ret, mode):
    """Validate a state function's return against StateReturn.

    On failure: raise SaltInvocationError in strict mode, log in warn mode.
    Always returns the original ``ret`` -- the payload is never mutated.
    """
    if not HAS_PYDANTIC or mode == "off":
        return ret
    try:
        StateReturn.model_validate(ret)
    except ValidationError as exc:
        msg = (
            f"state return contract violation in "
            f"{fn.__module__}.{fn.__name__}: {exc}"
        )
        if mode == "strict":
            raise SaltInvocationError(msg) from exc
        log.warning(msg)
    return ret


def _coerced_kwargs(validated_model, provided_keys):
    """Pull attribute values back off a validated model for keys that were
    actually provided in the call. Avoids clobbering fn-level defaults with
    pydantic-sourced defaults, and preserves nested BaseModel instances
    (which would otherwise be flattened by ``model_dump``).
    """
    return {
        name: getattr(validated_model, name)
        for name in validated_model.__class__.model_fields
        if name in provided_keys
    }


def wrap_callable(fn, mode="off", validate_state_return=False):
    """Wrap ``fn`` with validation. Returns ``fn`` unchanged when disabled.

    :param fn: the function to wrap
    :param mode: one of ``off``, ``warn``, ``strict``
    :param validate_state_return: when True, validate return against
        :class:`StateReturn` in addition to input validation
    """
    if mode == "off" or not HAS_PYDANTIC:
        return fn
    if getattr(fn, "__salt_validated__", False):
        return fn

    annotated = _has_annotations(fn)
    if not annotated and not validate_state_return:
        return fn

    model, sig = _build_input_model(fn) if annotated else (None, None)
    if sig is None:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return fn

    positional_only = [
        p.name
        for p in sig.parameters.values()
        if p.kind is inspect.Parameter.POSITIONAL_ONLY
    ]

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        non_reserved, reserved = _split_reserved(kwargs)
        if model is None:
            ret = fn(*args, **kwargs)
        else:
            try:
                bound = sig.bind_partial(*args, **non_reserved)
            except TypeError:
                # Arity mismatch -- let fn's own TypeError surface.
                return fn(*args, **kwargs)
            try:
                validated = model.model_validate(dict(bound.arguments))
            except ValidationError as exc:
                msg = (
                    f"input validation failure in "
                    f"{fn.__module__}.{fn.__name__}: {exc}"
                )
                if mode == "strict":
                    raise SaltInvocationError(msg) from exc
                log.warning(msg)
                ret = fn(*args, **kwargs)
            else:
                coerced = _coerced_kwargs(validated, bound.arguments)
                pos = [coerced.pop(n) for n in positional_only if n in coerced]
                ret = fn(*pos, **coerced, **reserved)

        if validate_state_return:
            _check_state_return(fn, ret, mode)
        return ret

    wrapper.__salt_validated__ = True
    return wrapper


def wrap_module(mod, opts, tag):
    """Walk a loaded module and install validation wrappers in place.

    Called from ``LazyLoader._load_module`` after dunder injection. No-op
    when pydantic is unavailable, the mode is ``off``, or the module has
    no annotated public callables.

    Functions are replaced on the module object via ``setattr`` -- the same
    mechanism the loader already uses to install ``__opts__`` et al. This
    means direct imports of the module after the first loader load also
    see wrapped functions.
    """
    if not HAS_PYDANTIC:
        return
    mode = opts.get("loader_validate_mode", "off")
    if mode not in _VALID_MODES:
        log.warning("Invalid loader_validate_mode %r; falling back to 'off'", mode)
        return
    if mode == "off":
        return

    validate_state_return = tag in _STATE_LOADER_TAGS

    for name in dir(mod):
        if name.startswith("_"):
            continue
        fn = getattr(mod, name, None)
        if not inspect.isfunction(fn):
            continue
        # Skip re-exports: only wrap functions defined in this module.
        if getattr(fn, "__module__", None) != mod.__name__:
            continue
        wrapped = wrap_callable(
            fn, mode=mode, validate_state_return=validate_state_return
        )
        if wrapped is not fn:
            setattr(mod, name, wrapped)

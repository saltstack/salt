"""
Loader-level input and return validation for Salt modules.

Called from ``LoadedFunc.__call__`` / ``LoadedCoro.__call__`` on every
loader dispatch. Behavior is controlled by the ``loader_validate_mode``
option:

* ``off`` (default) -- validation is skipped; loader behaves as before.
* ``warn`` -- validate on every call; on failure log and pass through.
* ``enforce`` -- validate on every call; on failure raise
  ``SaltInvocationError``.
* ``strict`` -- like ``enforce``, additionally require every loader-
  dispatched function to have type annotations on all non-var parameters.
  Raises ``SaltInvocationError`` on the first call to any function that
  doesn't meet the bar. Intended for dev / CI environments that want to
  enforce "the whole surface is typed."

Annotation-driven -- no per-function decorators required. A module author
writes a plain Python function with type hints and the loader validates
on dispatch. The input model is built lazily from the signature on first
call and cached on the function via ``__salt_validate_model__``, so only
functions actually invoked pay the model-build cost.

Return contracts are pinned per loader-kind by the factories in
``salt/loader/__init__.py`` -- for example ``salt.loader.states()`` passes
``output_contract=StateReturn`` so every state function's return is
checked against that model. Other factories pass no contract and only
input validation applies.

Reserved kwargs injected by the publish layer and state compiler
(``__pub_*``, ``__id__``, ``__sls__``, ...) are filtered out of the
validation input and forwarded unchanged to the underlying function,
so module authors never have to declare them in signatures.
"""

import inspect
import logging

try:
    from pydantic import BaseModel, ConfigDict, ValidationError, create_model

    HAS_PYDANTIC = True
except ImportError:  # pragma: no cover
    HAS_PYDANTIC = False

from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


# Reserved kwargs are sourced lazily from salt.state.STATE_RUNTIME_KEYWORDS
# (the canonical state-compiler set), filtered to dunder-named entries.
# Plain-name runtime keywords like 'failhard', 'onlyif', 'retry' are
# stripped by the state compiler before dispatch and never reach the
# loader, so they aren't needed here. The import is deferred to avoid
# a circular: salt.state imports salt.loader which imports this module.
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


if HAS_PYDANTIC:
    SALT_VALIDATE_CONFIG = ConfigDict(
        arbitrary_types_allowed=True,
        # Lax coercion: CLI strings ("30", "true") coerce to declared type.
        strict=False,
        # Reserved kwargs are already stripped by the caller, but keep
        # extras tolerant for anything we missed.
        extra="ignore",
    )

    class StateReturn(BaseModel):
        """Universal contract for ``salt.states.*`` function returns.

        Every state function's return must satisfy this shape. Pinned on
        the states loader by ``salt.loader.states()`` so a module returning
        ``result='True'`` (string) rather than ``result=True`` (bool) is
        caught at the module, not three layers downstream in ``State.call``.
        """

        model_config = SALT_VALIDATE_CONFIG

        name: str
        changes: dict
        result: bool | None
        comment: str | list
        warnings: list | None = None
        pchanges: dict | None = None

else:  # pragma: no cover
    SALT_VALIDATE_CONFIG = None
    StateReturn = None


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


_RAISING_MODES = frozenset({"enforce", "strict"})


def _has_annotations(fn):
    """Return True if the function has any parameter annotation."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    for param in sig.parameters.values():
        if param.annotation is not inspect.Parameter.empty:
            return True
    return False


def _missing_annotations(fn):
    """Return the list of parameter names on ``fn`` that lack annotations.

    Excludes ``*args`` and ``**kwargs`` -- they can't be annotated in a way
    pydantic would validate anyway, so a missing annotation on those is not
    actionable.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    missing = []
    for name, param in sig.parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if param.annotation is inspect.Parameter.empty:
            missing.append(name)
    return missing


# Sentinel attached to a function when we've determined no input model
# can be built for it (either no annotations, or pydantic was unable to
# construct one). Avoids re-attempting model build on every call.
_NO_MODEL = object()


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
        annotation = hints.get(name, inspect.Parameter.empty)
        if annotation is inspect.Parameter.empty:
            # Skip unannotated params so pydantic doesn't invent a schema
            # for them from the default value's type.
            continue
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
        # for that one function, never break the loader.
        log.debug(
            "Could not build input model for %s.%s",
            fn.__module__,
            fn.__name__,
            exc_info=True,
        )
        return None, sig
    return model, sig


def _get_or_build_model(fn):
    """Return the cached (model, sig) for ``fn``, building on first call."""
    cached = getattr(fn, "__salt_validate_model__", None)
    if cached is _NO_MODEL:
        return None, None
    if cached is not None:
        return cached
    if not _has_annotations(fn):
        _set_cache(fn, _NO_MODEL)
        return None, None
    model, sig = _build_input_model(fn)
    if model is None:
        _set_cache(fn, _NO_MODEL)
        return None, None
    _set_cache(fn, (model, sig))
    return model, sig


def _set_cache(fn, value):
    """Attach the model cache to the function. Some callables (C builtins,
    functools.partial) don't accept attribute assignment; silently skip
    caching in that case -- we'll rebuild each call, which is correct
    but slower."""
    try:
        fn.__salt_validate_model__ = value
    except (AttributeError, TypeError):  # pragma: no cover
        pass


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


def validate_inputs(fn, args, kwargs, mode):
    """Validate call-site inputs for ``fn`` and return the (args, kwargs)
    to dispatch with. No-op when mode is ``off`` or pydantic is unavailable.

    In ``strict`` mode, any non-``*args``/``**kwargs`` parameter lacking a
    type annotation is itself a failure -- raises ``SaltInvocationError``
    on the first call to that function.

    In ``enforce`` / ``strict`` mode a validation failure raises. In
    ``warn`` mode the original args/kwargs are returned unchanged and the
    error is logged.
    """
    if mode == "off" or not HAS_PYDANTIC:
        return args, kwargs

    if mode == "strict":
        missing = _missing_annotations(fn)
        if missing:
            raise SaltInvocationError(
                f"strict mode requires type annotations in "
                f"{fn.__module__}.{fn.__name__}, missing: {', '.join(missing)}"
            )

    model, sig = _get_or_build_model(fn)
    if model is None:
        return args, kwargs

    non_reserved, reserved = _split_reserved(dict(kwargs))
    try:
        bound = sig.bind_partial(*args, **non_reserved)
    except TypeError:
        # Arity mismatch -- let fn's own TypeError surface.
        return args, kwargs

    try:
        validated = model.model_validate(dict(bound.arguments))
    except ValidationError as exc:
        msg = f"input validation failure in {fn.__module__}.{fn.__name__}: {exc}"
        if mode in _RAISING_MODES:
            raise SaltInvocationError(msg) from exc
        log.warning(msg)
        return args, kwargs

    coerced = _coerced_kwargs(validated, bound.arguments)
    positional_only = [
        p.name
        for p in sig.parameters.values()
        if p.kind is inspect.Parameter.POSITIONAL_ONLY
    ]
    new_pos = tuple(coerced.pop(n) for n in positional_only if n in coerced)
    new_kwargs = {**coerced, **reserved}
    return new_pos, new_kwargs


def validate_return(fn, ret, contract, mode):
    """Validate ``fn``'s return against the loader's ``output_contract``.

    Returns ``ret`` unchanged (we never mutate the payload). On failure
    raises ``SaltInvocationError`` in ``enforce`` / ``strict`` mode, logs
    in ``warn`` mode.
    """
    if mode == "off" or not HAS_PYDANTIC or contract is None:
        return ret
    try:
        contract.model_validate(ret)
    except ValidationError as exc:
        msg = f"return contract violation in {fn.__module__}.{fn.__name__}: {exc}"
        if mode in _RAISING_MODES:
            raise SaltInvocationError(msg) from exc
        log.warning(msg)
    return ret

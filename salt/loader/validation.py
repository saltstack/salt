"""
Loader-level input and return validation for Salt modules.

Called from ``LoadedFunc.__call__`` / ``LoadedCoro.__call__`` on every
loader dispatch. Behavior is split across two independent options:

``loader_validate_input_mode`` -- governs ``validate_inputs()``:

* ``off`` (default) -- input validation is skipped.
* ``warn`` -- validate annotated callables; log + pass through on failure.
* ``enforce`` -- raise ``SaltInvocationError`` on validation failure.
* ``strict`` -- like ``enforce``, additionally require every loader-
  dispatched function to have type annotations on all non-var parameters.
  Raises on the first call to any function that doesn't meet the bar.
  Intended for dev / CI environments that want "the whole surface typed."

``loader_validate_return_mode`` -- governs ``validate_return()``:

* ``off`` (default) -- return validation is skipped.
* ``warn`` -- validate when a contract applies, log + pass through on
  failure.
* ``enforce`` -- raise ``SaltInvocationError`` on contract violation.
* ``strict`` -- like ``enforce``, additionally require that every
  loader-dispatched function be reachable through *some* contract
  (factory-pinned, registry entry, or module-declared refinement).
  Functions with none of those raise -- the discovery sensor for
  "Salt does not yet know what this returns."

Annotation-driven -- no per-function decorators required. A module author
writes a plain Python function with type hints and the loader validates
on dispatch. The input model is built lazily from the signature on first
call and cached on the function via ``__salt_validate_model__``, so only
functions actually invoked pay the model-build cost.

Return contracts are Salt-owned, defined in
:mod:`salt.loader.contracts`. Two tiers:

* **Factory-pinned contract** (``LazyLoader.output_contract``) -- a
  single model that every function in a loader kind must satisfy.
  Factories pin this (e.g. ``states()`` passes ``StateReturn``).
* **Per-function registry** (``LazyLoader.return_registry``) -- a
  ``{"module.func": ReturnModel}`` dict for loader kinds where returns
  vary per function.

Modules **cannot** declare their own return contract wholesale. They
*may* declare a more-specific return type via ``-> SomeSubModel`` as
long as it's a pydantic subclass of the base contract -- in which case
validation uses the refined model. Declarations not compatible with
the base raise at dispatch time.

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
else:  # pragma: no cover
    SALT_VALIDATE_CONFIG = None


# Re-exported from salt.loader.contracts for backward compat with earlier
# versions of this module that defined StateReturn in-place.
# pylint: disable=unused-import,wrong-import-position
from salt.loader.contracts.states import StateReturn  # noqa: F401

# pylint: enable=unused-import,wrong-import-position


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


# Sentinel attached to a function when contract resolution has decided
# no validation is applicable (and we don't want to re-resolve on every
# call).
_NO_CONTRACT = object()


def _return_annotation(fn):
    """Return the resolved return annotation of ``fn``, or None.

    Resolution handles string annotations (``from __future__ import
    annotations`` style), silently returns None on failure rather than
    propagating -- a function with an unresolvable annotation just doesn't
    get refinement support.
    """
    try:
        hints = inspect.get_annotations(fn, eval_str=True)
    except (TypeError, ValueError, NameError):
        return None
    return hints.get("return")


def _check_refinement(fn, declared, base):
    """Raise if the module-declared return is incompatible with the base.

    Only enforced when both are pydantic ``BaseModel`` subclasses. For
    non-class or non-BaseModel contracts (generics, type aliases,
    primitives), refinement isn't supported in this cut -- the base
    contract is used and the declaration is silently ignored.
    """
    if not HAS_PYDANTIC:
        return
    if declared is None or base is None:
        return
    if not (inspect.isclass(declared) and inspect.isclass(base)):
        return
    if not (issubclass(base, BaseModel) and issubclass(declared, BaseModel)):
        return
    if not issubclass(declared, base):
        raise SaltInvocationError(
            f"{fn.__module__}.{fn.__name__}: declared return type "
            f"{declared.__name__} is not a subclass of Salt's contract "
            f"{base.__name__}"
        )


def _is_refined_subclass(declared, base):
    """True when ``declared`` strictly refines ``base`` via BaseModel
    subclassing (not equal, not the same class)."""
    return (
        HAS_PYDANTIC
        and declared is not None
        and base is not None
        and inspect.isclass(declared)
        and inspect.isclass(base)
        and issubclass(base, BaseModel)
        and issubclass(declared, BaseModel)
        and issubclass(declared, base)
        and declared is not base
    )


def _resolve_return_contract(fn, fn_name, factory_contract, registry, mode):
    """Decide which return model (if any) to validate ``fn``'s return against.

    Precedence:

    1. Factory contract + compatible module refinement -> module's type
       (more specific).
    2. Factory contract alone -> factory contract.
    3. Registry entry for ``fn_name`` + compatible module refinement ->
       module's type.
    4. Registry entry alone -> registry entry.
    5. Module declared alone (no factory, no registry) -> module's type.
    6. Nothing: ``strict`` raises; other modes return None (no validation).

    Incompatible refinements (declared type not a subclass of the base)
    raise ``SaltInvocationError``.
    """
    declared = _return_annotation(fn)

    # Factory contract (universal-per-loader-kind) takes priority.
    if factory_contract is not None:
        _check_refinement(fn, declared, factory_contract)
        if _is_refined_subclass(declared, factory_contract):
            return declared
        return factory_contract

    # Per-function registry (Salt-owned) covers varying-shape loaders.
    if registry is not None and fn_name is not None:
        registry_contract = registry.get(fn_name)
        if registry_contract is not None:
            _check_refinement(fn, declared, registry_contract)
            if _is_refined_subclass(declared, registry_contract):
                return declared
            return registry_contract

    # Module-declared annotation, no Salt-side contract. Accepted so
    # module authors can opt in before a registry entry lands.
    if declared is not None:
        return declared

    # Nothing to validate against.
    if mode == "strict":
        raise SaltInvocationError(
            f"{fn.__module__}.{fn.__name__}: strict return mode requires a "
            "contract (factory, registry entry, or declared annotation)"
        )
    return None


def _get_or_resolve_return_contract(fn, fn_name, factory_contract, registry, mode):
    """Return the resolved contract, caching on the function.

    Incompatible-refinement errors are not cached -- they're raised afresh
    on every call so the error is loud and visible every time.
    """
    cached = getattr(fn, "__salt_return_contract__", None)
    if cached is _NO_CONTRACT:
        if mode == "strict":
            # Re-resolve so strict's "missing contract" raise fires even
            # after a non-strict call cached _NO_CONTRACT.
            return _resolve_return_contract(
                fn, fn_name, factory_contract, registry, mode
            )
        return None
    if cached is not None:
        return cached
    resolved = _resolve_return_contract(fn, fn_name, factory_contract, registry, mode)
    if resolved is None:
        try:
            fn.__salt_return_contract__ = _NO_CONTRACT
        except (AttributeError, TypeError):  # pragma: no cover
            pass
    else:
        try:
            fn.__salt_return_contract__ = resolved
        except (AttributeError, TypeError):  # pragma: no cover
            pass
    return resolved


def validate_return(fn, fn_name, ret, contract, registry, mode):
    """Validate ``fn``'s return against the effective return contract.

    The effective contract is the most-specific of: module's declared
    return type (if a strict pydantic subclass of the factory/registry
    base), the factory ``output_contract``, or the per-function
    ``registry`` entry. If no contract applies and mode is ``strict``,
    raises -- otherwise no-op.

    Returns ``ret`` unchanged (payload is never mutated).
    """
    if mode == "off" or not HAS_PYDANTIC:
        return ret

    effective = _get_or_resolve_return_contract(fn, fn_name, contract, registry, mode)
    if effective is None:
        return ret

    try:
        effective.model_validate(ret)
    except ValidationError as exc:
        msg = f"return contract violation in {fn.__module__}.{fn.__name__}: {exc}"
        if mode in _RAISING_MODES:
            raise SaltInvocationError(msg) from exc
        log.warning(msg)
    return ret

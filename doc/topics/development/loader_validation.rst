.. _loader-validation:

=================
Loader Validation
=================

.. versionadded:: 3008.0

Salt's loader can validate call-site inputs and function returns against
Python type annotations.  Annotations are the user interface: a module
author writes a plain function with type hints, and the loader
validates on every dispatch, coerces CLI strings to the declared types,
and (for state modules) enforces a return contract.

The feature is opt-in per loader and per direction, defaults to off,
and relies on :mod:`pydantic` -- when pydantic is unavailable the
layer becomes a no-op.


When to use loader validation
=============================

Loader validation targets two long-standing classes of silent bugs:

* **Silent type mismatch at the CLI boundary.**  ``salt '*' pkg.installed
  version=1.2`` parses ``1.2`` into a ``float`` -- the module then
  compares against a string version and silently reinstalls (or does
  nothing) with no diagnostic.  With input validation enabled on the
  wire loader, the mismatch surfaces as a ``SaltInvocationError`` naming
  the function and offending argument.

* **State modules that return a malformed dict.**  A state function
  that forgets the ``comment`` key, returns ``None`` instead of a dict,
  or sets ``result`` to a string crashes the state compiler deep in
  the runtime with an unhelpful traceback.  With return validation
  enabled on the ``states`` loader, the same bug produces a direct
  ``return contract violation in <module>.<func>`` message pointing
  at the field that failed.

Validation is cheap in the ``off`` mode (a single dict lookup per
dispatch) and modest in ``enforce`` / ``strict`` mode (~100us per
dispatch for a typical signature).  It can be deployed boundary-only
(wire + state returns) in production, or everywhere in CI.


Configuration
=============

A single master / minion option controls validation:

.. code-block:: yaml

    loader_validate_overrides:
      <loader-name>:
        input_mode: <mode>
        return_mode: <mode>

The outer dict is keyed by loader name; each entry has optional
``input_mode`` and ``return_mode`` keys.  Direction keys that are
omitted resolve to ``off``.

Loader names
------------

Five loaders participate in validation:

``wire_salt``
    The filtered ``minion_mods`` loader that the publish layer uses
    to dispatch user-initiated ``salt '*' <mod>.<func>`` calls.  This
    is the boundary where CLI-string type coercion matters most.

``salt_dunder``
    The inner ``__salt__`` loader that composes shipped code paths
    (one execution module calling another).  Inputs here are already
    Python objects, not strings.  Enabling input validation here
    adds internal-contract enforcement.

``states``
    State module dispatch.  The default factory pins
    :class:`salt.loader.contracts.states.StateReturn` as the return
    contract, so ``return_mode`` is where the state-return bug class
    is caught.

``runners``
    ``salt-run`` and salt-api runner dispatch.

``wheels``
    Wheel client dispatch.

Direction-key names that are not in this list, or mode values that
are not one of the four below, are rejected at daemon startup with
a consolidated error message naming every problem -- malformed
configuration cannot silently no-op at dispatch time.

Modes
-----

``off`` (default)
    No validation.  Equivalent to not configuring the entry at all.

``warn``
    Validate on every dispatch; on failure, log a warning naming the
    function and the validation error, then pass the original
    arguments through unchanged.  Purely observational.

``enforce``
    Validate on every dispatch; on failure, raise
    :class:`salt.exceptions.SaltInvocationError`.  Successful
    validation returns pydantic-coerced values (``"30"`` becomes
    ``30``, ``"true"`` becomes ``True``, etc.) to the function.

``strict``
    Same as ``enforce``, plus:

    * For ``input_mode``, every non-variadic parameter of the
      function must carry a type annotation.  The first dispatch of
      a function with a missing annotation raises
      ``strict mode requires type annotations in <mod>.<func>,
      missing: ...``.
    * For ``return_mode``, a return contract must exist for the
      function -- factory-pinned, registry-declared, or module-declared
      via a ``-> SomeModel`` return annotation.  Dispatches with none
      raise ``strict return mode requires a contract``.

    ``strict`` is the discovery sensor: it tells you where coverage
    is still missing.

Worked configurations
---------------------

**Observability on every loader** (production-safe; no behavior
change, just log lines when validation fails):

.. code-block:: yaml

    loader_validate_overrides:
      wire_salt:
        input_mode: warn
        return_mode: warn
      salt_dunder:
        input_mode: warn
        return_mode: warn
      states:
        input_mode: warn
        return_mode: warn
      runners:
        input_mode: warn
        return_mode: warn
      wheels:
        input_mode: warn
        return_mode: warn

**Catch state-return bugs, nothing else** (zero migration cost; the
``StateReturn`` contract is already factory-pinned on the ``states``
loader):

.. code-block:: yaml

    loader_validate_overrides:
      states:
        return_mode: enforce

**Boundary strict, internals untouched** (fail hard on bad CLI or
API input, but don't disturb internal composition):

.. code-block:: yaml

    loader_validate_overrides:
      wire_salt:
        input_mode: enforce
        return_mode: enforce
      states:
        input_mode: enforce
        return_mode: enforce
      runners:
        input_mode: enforce
        return_mode: enforce
      wheels:
        input_mode: enforce
        return_mode: enforce

**CI / dev -- whole surface typed**:

.. code-block:: yaml

    loader_validate_overrides:
      wire_salt:
        input_mode: strict
        return_mode: strict
      salt_dunder:
        input_mode: strict
        return_mode: strict
      states:
        input_mode: strict
        return_mode: strict
      runners:
        input_mode: strict
        return_mode: strict
      wheels:
        input_mode: strict
        return_mode: strict

**LTS production pattern** -- surface external callers, trust
shipped internals:

.. code-block:: yaml

    loader_validate_overrides:
      wire_salt:
        input_mode: warn
      states:
        return_mode: warn


Annotating a module function
============================

Loader validation is annotation-driven.  No decorators, no registration
step: a module author adds type hints to a function and the loader
builds a pydantic model from the signature on the function's first
dispatch, caches it on the function object, and uses it on every
subsequent call.

Before -- untyped, silent coercion on bad input:

.. code-block:: python

    def installed(name, version=None, refresh=False):
        ret = {"name": name, "changes": {}, "result": True, "comment": ""}
        # version="1.2" from CLI arrives as str; version=1.2 from an
        # SLS float literal arrives as float. Nothing catches this.
        ...
        return ret

After -- types declared, loader coerces CLI strings to the declared
types, state-return contract enforced:

.. code-block:: python

    def installed(name: str, version: str | None = None, refresh: bool = False):
        ret = {"name": name, "changes": {}, "result": True, "comment": ""}
        ...
        return ret

With ``loader_validate_overrides.states.input_mode: enforce`` enabled,
calling ``salt '*' state.single pkg.installed name=nginx version=1.2``
coerces ``version`` to the string ``"1.2"`` before the function is
invoked.  Bad input (``version=['a', 'list']``) raises
``SaltInvocationError`` naming the function and field.

CLI-string coercion is governed by pydantic's lax-coercion mode:

* ``"30"`` -> ``30`` for ``int``
* ``"3.14"`` -> ``3.14`` for ``float``
* ``"true"`` / ``"yes"`` / ``"on"`` -> ``True`` for ``bool``
* ``"false"`` / ``"no"`` / ``"off"`` -> ``False`` for ``bool``

Reserved publish-layer and state-compiler kwargs (``__pub_*``,
``__id__``, ``__sls__``, ``__env__``, ...) are filtered out of the
validation input and forwarded unchanged.  Module authors never need
to declare them in signatures.


Salt-provided annotation types
==============================

:mod:`salt.loader.annotations` ships Salt-idiomatic pydantic types for
common argument shapes.  A module author imports them like any other
annotation:

.. code-block:: python

    from salt.loader.annotations import ByteSize, Duration, MinionID, Port

``MinionID``
    A minion id or target glob.  Accepts ``[A-Za-z0-9._-]`` plus the
    glob metacharacters ``*?[]``, up to 253 characters.

    .. code-block:: python

        def ping(target: MinionID = "*"): ...

``Port``
    An IP port, 1-65535 inclusive.

    .. code-block:: python

        def listen(bind: str, port: Port = 4506): ...

``Duration``
    A time duration that coerces to :class:`datetime.timedelta`.
    Accepts numeric seconds, short strings (``"30s"``, ``"5m"``,
    ``"2h"``, ``"1d"``, decimals allowed), and ISO-8601 (``"PT1H30M"``).

    .. code-block:: python

        def retry(interval: Duration = "30s"): ...

``ByteSize``
    A byte count that coerces to ``int``.  Accepts raw integers and
    strings with SI (``"500MB"``) or IEC (``"1.5GiB"``) suffixes.

    .. code-block:: python

        def cap(max_memory: ByteSize = "500MB"): ...

The set is deliberately small.  Request additional types by opening
an issue on `saltstack/salt
<https://github.com/saltstack/salt/issues>`_.


Return contracts
================

A return contract is a :class:`pydantic.BaseModel` subclass that every
dispatched function in a loader kind must satisfy.  Contracts are
Salt-owned, defined under :mod:`salt.loader.contracts`.

State return contract
---------------------

:class:`salt.loader.contracts.states.StateReturn` is pinned on the
``states`` loader by the factory.  It defines the minimum shape of a
state return:

.. code-block:: python

    class StateReturn(BaseModel):
        name: str
        changes: dict
        result: bool | None
        comment: str | list
        warnings: list | None = None
        pchanges: dict | None = None

With ``states.return_mode: enforce``, any state function return that
does not match this shape raises ``SaltInvocationError`` naming the
function and the failing field.

Refinement -- declaring a more specific return
----------------------------------------------

A state module may declare a stricter return by subclassing
``StateReturn`` and annotating the function's return:

.. code-block:: python

    from pydantic import BaseModel
    from salt.loader.contracts.states import StateReturn

    class FileManagedChanges(BaseModel):
        diff: str | None = None
        mode: str | None = None
        user: str | None = None

    class FileManagedReturn(StateReturn):
        changes: FileManagedChanges  # overrides base's ``dict``

    def managed(name: str, source: str, mode: str | None = None,
                ...) -> FileManagedReturn:
        ret = {"name": name, "changes": {}, "result": True, "comment": ""}
        ...
        return ret

The loader detects that ``FileManagedReturn`` is a strict subclass of
``StateReturn`` and validates against the refined model.  Returns that
satisfy the base contract but violate the refinement (e.g. an
unexpected key in ``changes``) are flagged.

Declared returns that are *not* subclasses of the factory contract
raise ``SaltInvocationError`` at dispatch time -- a module cannot
widen Salt's contract, only narrow it.

Other loader kinds
------------------

Only the ``states`` loader ships with a factory-pinned return contract
today.  A per-function registry mechanism for ``runners`` / ``wheels``
is scaffolded but intentionally empty: entries will land as individual
runner and wheel returns are modeled.  Until a contract exists, module
authors can still declare their own ``-> SomeModel`` and the loader
will validate against it in ``warn`` / ``enforce`` / ``strict`` mode.


Troubleshooting
===============

Common messages
---------------

``input validation failure in <module>.<func>: <pydantic error>``
    An argument did not satisfy the declared type.  In ``warn`` mode
    the call still proceeds with the original arguments; in
    ``enforce`` / ``strict`` it raises.

``return contract violation in <module>.<func>: <pydantic error>``
    The function's return did not match the effective contract.
    Same mode distinction as inputs.

``strict mode requires type annotations in <mod>.<func>, missing: <names>``
    ``input_mode: strict`` is active and the function has unannotated
    parameters.  Add annotations or demote to ``enforce`` / ``warn``.

``<mod>.<func>: strict return mode requires a contract``
    ``return_mode: strict`` is active and the function is reachable
    through no contract.  Add a ``-> SomeModel`` annotation, add a
    Salt-side contract, or demote the mode.

``<mod>.<func>: declared return type <X> is not a subclass of Salt's contract <Y>``
    The function annotated a return type that does not inherit from
    the factory-pinned contract.  Either make the type a subclass, or
    remove the annotation.

``loader_validate_overrides.<X>: unknown loader (known: ...)``
    ``<X>`` is not in :data:`salt.config.loader_validation.KNOWN_LOADER_NAMES`.
    Correct the key, or remove the override block.

``loader_validate_overrides.<X>.<Y>: not a valid direction key``
    Only ``input_mode`` and ``return_mode`` are allowed per-loader.

``loader_validate_overrides.<X>.<Y>: '<mode>' is not a valid mode``
    Mode must be one of ``off``, ``warn``, ``enforce``, ``strict``.

Startup failures
----------------

Configuration problems in ``loader_validate_overrides`` are caught at
daemon startup, not at first dispatch, and every problem the
validator finds is reported together.  When the master or minion
refuses to start with a ``ValueError`` naming
``loader_validate_overrides``, fix every line listed in the error
message in one pass -- that is the complete list of problems the
validator found.


Operational notes
=================

**Pydantic dependency.**  Validation requires :mod:`pydantic`, which
ships in Salt's base requirements as of 3008.  If pydantic is not
importable, the validation layer silently degrades to a no-op; the
``loader_validate_overrides`` opt is still parsed and validated for
structure, but no dispatch is intercepted.

**Default behavior is off.**  Every loader direction defaults to
``off`` on upgrade.  Operators and module authors opt in explicitly.

**Performance.**

* ``off`` mode: one dict lookup per dispatch.
* ``warn`` / ``enforce`` mode: ~50-100us per dispatch for a typical
  signature, after the first call builds and caches the input model
  on the function object.
* ``strict`` mode: adds an annotation-coverage check on the first
  call to each function.  Subsequent calls are the same cost as
  ``enforce``.

The first dispatch of each function pays the pydantic schema-build
cost (hundreds of microseconds to a few milliseconds depending on
signature size).  Subsequent dispatches use the cached model.

**Concurrency.**  The per-function model and contract caches are
written without a lock -- two workers that first-dispatch the same
function concurrently can both build a pydantic model, and the loser's
model is dereferenced after the attribute write and garbage-collected.
This is transient duplicate allocation of a Rust-backed
``SchemaValidator``, not a correctness bug.

**Unnamed loaders no-op.**  A ``LazyLoader`` constructed without a
``name=`` kwarg does not participate in validation; its dispatches
always resolve to ``off`` regardless of the opt.  This keeps internal
scratch loaders (grains collection, SPM, etc.) out of the validation
surface until a factory explicitly names them.

**No existing Salt module is annotated yet.**  This feature ships the
mechanism.  Migration to annotated signatures is incremental and
per-module -- there is no fleet-wide flag day.


See also
========

* :ref:`writing-state-modules` -- state module conventions.
* :ref:`writing-execution-modules` -- execution module conventions.
* :mod:`salt.loader.annotations` -- the Salt-provided annotation
  types.
* :mod:`salt.loader.contracts` -- the Salt-owned return contracts.

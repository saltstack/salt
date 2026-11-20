"""
Salt-owned return contracts for loader-dispatched functions.

Two tiers:

* **Universal-per-loader-kind**: a single model that every function in
  that loader kind must conform to. Pinned on the loader via the factory
  in :mod:`salt.loader` (e.g. ``states()`` passes ``output_contract=
  StateReturn``). Covers states, tops, beacons, matchers, outputters,
  grains, pillars.

* **Per-function registry**: a ``{"module.func": ReturnModel}`` dict for
  loader kinds where functions have individually-varying return shapes
  (runners, wheels, returners, auth, sdb, cache, executors, fileservers).
  Looked up at dispatch time by the loader-qualified function name.
  Owned here in Salt, not declared by modules.

Modules **cannot** declare their own return contract wholesale. They
*may* declare a more-specific return type via ``-> SomeSubModel`` -- as
long as it is a strict pydantic subclass of the base contract -- in
which case validation uses the refined model. Declarations that are
not subclasses of the base contract raise at dispatch time.

Strict mode (``loader_validate_return_mode=strict``) additionally
requires that every loader-dispatched function be reachable through
*some* contract: factory-pinned, registry entry, or module-declared
refinement. Functions with none of those are themselves a failure --
the discovery sensor for "Salt does not yet know what this returns."
"""

from salt.loader.contracts.states import StateReturn

__all__ = ["StateReturn"]

# Resource system: known gaps for state authoring and `salt-call`

Two related gaps found while building `saltext-opsdev` and trying to run
resource states locally with `salt-call`.

---

## Gap 1 — `salt-call` bypasses resource dispatch (FIXED via `-r`)

### What happened

`salt-call` used `salt.cli.caller.BaseCaller`, which always called
``self.minion.functions[fun](*args, **kwargs)``.  Resource dispatch lives
in `Minion._thread_return` and `BaseCaller` never reached that code path,
so resources were silently ignored.

### Fix — opt-in `-r/--resources` flag

Rather than auto-promote salt-call to dispatch to resources (which would
break every existing script that expects a single bare-value return),
`-r/--resources` is a new opt-in flag that mirrors the master CLI's
targeting model:

```bash
# Today's behaviour, unchanged
salt-call test.ping                          # → True

# Opt-in resource dispatch
salt-call -r test.ping                       # default tgt='*' → minion + all resources
salt-call -r --tgt dummy-01 test.ping        # → True (single, unwrapped)
salt-call -r --tgt 'T@dummy' --tgt-type compound state.apply mysls
salt-call -r --tgt 'os:Debian' --tgt-type grain test.ping
```

### Implementation

* `salt.utils.parsers.SaltCallOptionParser` — adds three options:
  ``-r/--resources`` (boolean), ``--tgt`` (default ``*``), and
  ``--tgt-type`` (default ``glob``).  No collision with existing
  salt-call short flags.
* `salt.minion` — exposes the resource targeting helpers
  (``_resolve_resource_targets``, ``_resource_matches_compound``,
  ``_collect_resource_grains``, ``_is_pure_resource_target``,
  ``_NO_RESOURCE_FUNS``, ``_MERGE_RESOURCE_FUNS``,
  ``_prefix_resource_state_key``) on ``MinionBase`` via a single
  ``setattr`` rebind at the end of the module.  ``SMinion`` (used by
  salt-call) now sees them through the MRO without a 250-line code move.
* `salt.cli.caller.BaseCaller._call_with_resources` — new method invoked
  when ``-r`` is set.  Resolves resource targets via the inherited
  helper, decides if the managing minion also matches (suppressed for
  pure ``T@``/``M@`` compounds via ``_is_pure_resource_target``), runs
  the function once per matched target, and merges results.  Output:
  bare value when one target ran, ``{id: result}`` dict otherwise.  For
  ``state.apply`` and other merge funs, results are folded into one
  combined dict with state IDs prefixed by resource id — matching the
  master merge-mode shape exactly.
* `salt.modules.state.__virtual__` — narrowed from "virtual out for
  every resource_type" to "virtual out only for resource types that have
  a per-type override module" (currently just ``ssh``).  This lets the
  standard ``state.apply`` run in a dummy resource context, where the
  Gap 2 fix routes its ``__salt__`` to the per-resource execution loader
  automatically.

Verified end-to-end in ``tests/pytests/unit/cli/test_caller_resources.py``
(6 tests) and via manual ``salt-call`` runs.  The dummy
``salt/states/dummyresource_test.py`` state module is reachable from a
normal ``.sls`` and dispatches correctly to per-resource execution
modules.

**Status:** fixed.

---

## Gap 2 — `State` throws away resource context (FIXED)

### What we *thought* the gap was

`salt.loader.states` packs only six dunders into every state module:

```python
# salt/loader/__init__.py – states()
pack={
    "__salt__":        functions,
    "__proxy__":       proxy or {},
    "__utils__":       utils,
    "__serializers__": serializers,
    "__context__":     context,
    "__file_client__": file_client,
}
```

`__resource_funcs__` is **not** in that list.  We initially assumed the fix
was to pack `__resource_funcs__` into states/ too so state modules could call
`__resource_funcs__["..."]` directly.

### Why that framing was wrong

State modules already have `__salt__`.  In a resource context, `__salt__`
**should** resolve to the per-resource execution loader — and that loader
already routes resource-aware module calls correctly.  Specifically:

* The per-resource loader (`salt.loader.resource_modules`) is itself a
  `__salt__`-style loader scanning `salt/modules/`.  It just sets
  `opts["resource_type"]` and packs `pack_self="__salt__"`.
* Resource-aware modules (e.g. `salt/modules/dummyresource_test.py`)
  gate their `__virtual__` on `resource_type` and override the standard
  module slot (`test`, etc.).  Standard modules (e.g. `salt/modules/test.py`)
  yield via `__virtual__` when `resource_type` is set.

So a state module that calls `__salt__["test.ping"]` in a dummy-resource
context naturally dispatches to `dummyresource_test.ping`.  No new dunder
required.

### What the actual gap was

`State.load_modules` (`salt/state.py:1355`) unconditionally rebuilt
`self.functions` from `salt.loader.minion_mods(self.opts, ...)`, regardless
of whether `self.opts["resource_type"]` was set.  This silently dropped
the resource context: state modules ended up with `__salt__` pointing at
the managing minion's modules, even when the surrounding execution
function (`salt.modules.state.apply_`) had been dispatched into a
per-resource loader.

So the chain was:

1. `_thread_return` dispatches `state.apply` into `resource_loaders["dummy"]`.
   ✓ Per-resource loader is the function set.
2. Inside `state.apply`, `__opts__["resource_type"] == "dummy"`.  ✓
3. `salt.state.HighState(__opts__, ...)` carries the per-resource opts.  ✓
4. `State.load_modules` calls `salt.loader.minion_mods(self.opts, ...)`.
   ✗ — fresh load with no resource awareness.  State modules' `__salt__`
   is now the managing minion's modules.
5. `__salt__["test.ping"]` in a state module → managing minion's `test.ping`,
   not `dummyresource_test.ping`.

### Fix

In `State.load_modules`, when `self.opts.get("resource_type")` is set, build
`self.functions` via `salt.loader.resource_modules(...)` (with a freshly
built `salt.loader.resource(...)` for the connection-module loader) instead
of `minion_mods`.  All other paths are unchanged.

```python
def load_modules(self, data=None, proxy=None):
    log.info("Loading fresh modules for state activity")
    self.utils = salt.loader.utils(self.opts, file_client=self.file_client)
    resource_type = self.opts.get("resource_type")
    if resource_type:
        self.resource_funcs = salt.loader.resource(
            self.opts, utils=self.utils, context=self.state_con
        )
        self.functions = salt.loader.resource_modules(
            self.opts,
            resource_type,
            resource_funcs=self.resource_funcs,
            utils=self.utils,
            context=self.state_con,
        )
    else:
        self.functions = salt.loader.minion_mods(...)
    ...
```

State modules then dispatch resource-aware automatically.  `saltext-opsdev`
can author state functions in `states/` like any other Salt extension —
no `__resource_funcs__` dunder needed.

A demonstrating state module ships at `salt/states/dummyresource_test.py`:
its `present(name)` function calls `__salt__["test.ping"]` and gets
`True` from `salt.resource.dummy.ping` (via the per-resource override).

Verified end-to-end in
`tests/pytests/unit/state/test_resource_aware_loader.py`.

**Status:** fixed.

---

## Gap 3 — Master-side `T@` targeting for merge-mode functions (FIXED)

### What happened

```bash
salt -C 'T@dummy:dummy-01' state.apply mysls
```

`CkMinions._check_resource_minions` returned the resource ID (`dummy-01`)
in the wait-list.  The CLI then waited for `dummy-01` to return.

For non-merge functions (e.g. `test.ping`) this worked because the
managing minion sent a separate return per resource with `resource_id`
set and the master's `_return` handler remapped `load["id"] =
load["resource_id"]`.

For **merge-mode functions** the managing minion runs all resources
inline and returns ONE combined dict under its own ID — no per-resource
`resource_id`, no remap.  The CLI was waiting for `dummy-01`, the
response arrived as `resources-minion`, mismatch → `ERROR: No return
received`.

There was a related secondary issue: even with the wait-list fixed, the
managing minion's own `state.apply` would still try to apply the SLS
against itself, which fails for resource-only state modules
(`dummy_test.present` virtuals out unless `resource_type` is set),
producing a noisy `result: false` entry in the merged output.

### Fix

Three coordinated changes:

1. **`salt.utils.minions.check_minions` now plumbs `fun`** into
   `_check_compound_minions` → `_check_resource_minions`.  When
   `fun in _MERGE_RESOURCE_FUNS`, the resource matcher returns the
   **managing minion id(s)** from `registry.get_managing_minions_for_srn`
   (full SRN) or `registry.get_managing_minions_by_type` (bare type)
   instead of the resource id(s).  The CLI then waits for the managing
   minion, which delivers the merged response.

2. **`Minion._target_load`** now treats pure resource targets
   (`T@type[:id]`) as also matching the managing minion **when the
   function is a merge fun**: ``minion_is_target = bool(minion_matches)
   and (is_merge_fun or not is_pure_resource_target)``.  Without this
   override the managing minion would discard the publish entirely.

3. **`Minion._thread_return`** now detects the pure-resource + merge
   combination via the new ``data["pure_resource_target"]`` flag and
   **skips the regular function execution** in that case (seeding
   ``ret["return"] = {}`` instead).  The merge block below fills the
   dict from each per-resource loader, producing the same master-style
   output as before but without the spurious "not found" entry from the
   managing minion.

The merge-mode return keys still encode the resource ID via
`_prefix_resource_state_key`, so operators see per-resource provenance
in the rendered state output.

Verified end-to-end in
`tests/pytests/integration/resources/test_dummy_resource_state.py` —
full integration smoke suite green (292 passed, 0 failed).

**Status:** fixed.

---

## Summary table

| Scenario | Works today? | Notes |
|---|---|---|
| `salt-call -r state.apply` hits resources | **Yes** | Gap 1 — fixed via `-r/--tgt/--tgt-type` |
| `salt-call -r --tgt 'T@dummy' state.apply` (specific resource) | **Yes** | Gap 1 — fixed |
| `salt-call -r test.ping` (managing minion + all resources) | **Yes** | Gap 1 — fixed |
| `salt -C 'T@dummy' state.apply` hits resources | **Yes** | Gap 3 — fixed (managing-minion remap on master) |
| `salt -C 'T@dummy:dummy-01' state.apply` (specific resource by id) | **Yes** | Gap 3 — fixed |
| `salt resources-minion state.apply` (merge auto-dispatches) | No (resource_targets empty) | needs fun-aware target widening on minion |
| State functions in `states/` using `__salt__` in resource context | **Yes** | Gap 2 — fixed |
| `.sls` files using resource execution functions via `module.run` | Yes (via master dispatch) | unchanged |

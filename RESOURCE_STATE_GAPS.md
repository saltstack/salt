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

## Gap 2 — `State` throws away resource context (RETRACTED)

### Original framing

`salt.loader.states` packs only six dunders into every state module;
`__resource_funcs__` is not among them.  An earlier attempt fixed this by
making `State.load_modules` switch to `salt.loader.resource_modules(...)`
when `opts["resource_type"]` was set, so state modules' `__salt__` would
dispatch through per-resource overrides.

### Why this was reverted

The fix made one narrow case work (the dummy demo state module
calling `__salt__["test.ping"]` and getting `dummyresource_test.ping`)
but introduced a broad regression for any standard state module
(`pkg.installed`, `service.running`, `file.managed`, `host.present`)
that internally calls helpers like `__salt__["cmd.run_stdout"]`:

```
KeyError: 'cmd.run_stdout'
```

In a per-resource loader, `cmd.py` virtuals out (it has an opt-out gate
for `resource_type`), and unless the resource type ships a
`<rtype>resource_cmd.py` override, the slot is empty.  SSH happens to
have the override; ``dummy``, ``starting_state``, and any new resource
type does not.  The fix silently traded a wrong-target bug for a
loud-but-broader missing-function bug.

### The deeper issue

The Gap 2 framing assumed a state module could be transparently
resource-aware via the implicit `__salt__` rewrite.  That assumption is
unsafe: a state module written for the managing minion might call
``__salt__["pkg.install"]`` thinking it operates on the local system;
silently routing it to a per-resource loader (or worse, to a logical
resource that has no shell at all) leads to the wrong action on the
wrong target.

### Path forward

Resource-aware state context comes from **explicit resource-aware state
functions** — the pattern documented in `DERIVED_RESOURCES.md`:

* `ssh_host.state_applied`, `ss_env.deployed`, `ssh_host.fetch_file`,
  etc. are state functions that internally manage the resource context
  (compile, ship, execute via the resource's transport).
* State authors call those explicitly when they want resource-context
  behaviour.
* `__salt__` in any state module always means "managing minion" — same
  as a regular minion, no surprises.
* No automatic loader rewriting.

Gap 4 in `DERIVED_RESOURCES.md` covers the related concern that
resource execution-module override sets need to be comprehensive enough
for state functions targeting transport-based resources (SSH) to work
without slot gaps.

**Status:** retracted; reverted commit-by-commit.  See
`tests/pytests/unit/cli/test_caller_resources.py::test_r_state_apply_against_logical_resource_fails_loudly`
for the loud-failure test that captures the new expected behaviour for
logical resource types.

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
against itself.  For resource types whose state module (e.g.
`sshresource_state`) takes over the ``state`` slot, the dispatch goes
where it should, but the managing minion's standard `state.apply`
would also fire and produce noisy failure entries against any
resource-only state functions.  The `pure_resource_target` skip in
`_thread_return` suppresses that.

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

Applies to resource types that ship a `<rtype>resource_state.py`
override (today: SSH).  For resource types without one (dummy,
starting_state, etc.) `state.apply` against a resource is correctly
unsupported — the per-resource loader has no `state.apply` slot and
the operator gets a "not supported for resource type 'dummy'" error.

**Status:** fixed.

---

## Summary table

| Scenario | Works today? | Notes |
|---|---|---|
| `salt-call -r test.ping` (managing minion + all resources) | **Yes** | Gap 1 — fixed via `-r/--tgt/--tgt-type` |
| `salt-call -r --tgt dummy-01 test.ping` (specific resource) | **Yes** | Gap 1 — fixed |
| `salt-call -r --tgt dummy-01 grains.items` (per-resource grains) | **Yes** | Gap 1 — fixed |
| `salt -C 'T@ssh:hostA' state.apply` (transport-based resource) | **Yes** | Gap 3 — fixed (managing-minion remap on master) |
| `salt-call -r state.apply` against a logical resource | Loud failure | Logical resources don't ship `<rtype>resource_state.py`; "not supported" error returned |
| `salt resources-minion state.apply` (merge auto-dispatches) | No (resource_targets empty) | needs fun-aware target widening on minion |
| State functions in `states/` using `__salt__` in resource context | Managing minion's `__salt__` | Gap 2 retracted; use explicit resource-aware state functions instead (see DERIVED_RESOURCES.md) |
| `.sls` files using resource execution functions via `module.run` | Yes (via master dispatch) | unchanged |

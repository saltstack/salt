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

## Gap 2 — `State` throws away resource context (FIXED via per-type directory layout)

### Original framing

`salt.loader.states` packs only six dunders into every state module;
`__resource_funcs__` is not among them.  An earlier attempt fixed this by
making `State.load_modules` switch to `salt.loader.resource_modules(...)`
when `opts["resource_type"]` was set, so state modules' `__salt__` would
dispatch through per-resource overrides.

That fix worked for the narrow case of a state module specifically
designed for resource context (e.g. ``dummy_test.present`` calling
``__salt__["test.ping"]``) but introduced a regression for any standard
state module (`pkg.installed`, `service.running`, `file.managed`,
`host.present`) that internally called helpers like
``__salt__["cmd.run_stdout"]`` — under the original implementation,
``cmd.py`` virtualled out under any ``resource_type`` and the slot was
empty unless the resource type shipped a ``<rtype>resource_cmd.py``
override.  Most types didn't.

### Final fix

`State.load_modules` continues to switch to
`salt.loader.resource_modules(...)` when `opts["resource_type"]` is set,
**but** the per-resource loader's content is now controlled explicitly by
the **per-type directory layout** introduced in this branch
(`salt/resources/<rtype>/modules/` — see Implementation section).
Because standard ``cmd.py``, ``state.py``, ``test.py`` no longer have
``__virtual__`` opt-out guards on ``resource_type``, they always load —
and per-type override files in `salt/resources/<rtype>/modules/` win
their slot via directory-order priority in
:func:`salt.loader._module_dirs`.

Result: ``__salt__`` in a state module running in a resource context
sees both the resource-specific overrides (where they exist) and the
standard module set (everywhere else).  No KeyError, no silent
fall-through to the wrong target.

For escape-hatch access to the managing minion's loader from inside a
resource context, state and execution modules now have access to a new
``__minion__`` dunder.  See **Implementation: per-type directory
layout** below.

**Status:** fixed.

### Implementation: per-type directory layout

The Gap 2 fix is implemented as a small change in two places:

1. ``salt/loader/__init__.py``: ``_module_dirs(opts, ext_type)`` checks
   ``opts.get("resource_type")``; when set, prepends
   ``salt/resources/<rtype>/<ext_type>/`` (and equivalent paths under
   each extension layer — CLI ``module_dirs``, ``extension_modules``,
   entry-point packages) before the standard salt ``<ext_type>``
   directory.  LazyLoader processes dirs in order, so the per-type
   override wins whenever a file exists at the per-type path.

2. ``salt/loader/__init__.py``: ``salt.loader.resource_modules`` and
   ``salt.loader.states`` accept a ``minion_mods=`` kwarg that gets
   packed as ``__minion__`` so resource-context modules can dispatch
   to the managing minion's loader explicitly when needed.

3. The standard ``__virtual__`` opt-out guards in ``salt/modules/cmd.py``,
   ``salt/modules/state.py``, ``salt/modules/test.py`` were removed.
   They no longer need to know about ``resource_type``; the directory
   layout enforces the gating.

### Implementation: file moves

| Old path | New path |
|---|---|
| `salt/resource/ssh.py` | `salt/resources/ssh/__init__.py` |
| `salt/resource/dummy.py` | `salt/resources/dummy/__init__.py` |
| `salt/modules/sshresource_test.py` | `salt/resources/ssh/modules/test.py` |
| `salt/modules/sshresource_state.py` | `salt/resources/ssh/modules/state.py` |
| `salt/modules/sshresource_cmd.py` | `salt/resources/ssh/modules/cmd.py` |
| `salt/modules/sshresource_pkg.py` | `salt/resources/ssh/modules/pkg.py` |
| `salt/modules/dummyresource_test.py` | `salt/resources/dummy/modules/test.py` |

The migrated files dropped their ``__virtualname__`` and ``__virtual__``
resource-type guards — filename now matches the slot, and directory
location enforces the gating.

### Authoring a resource type

Drop files into the per-type tree, exactly mirroring Salt's standard
trees:

```
salt/resources/<rtype>/
  __init__.py            # connection module — init, discover, grains,
                         # ping, shutdown
  modules/               # execution-module overrides (filename = slot)
    cmd.py
    pkg.py
    state.py
    ...
  states/                # state-module overrides (filename = slot)
    ...
  grains/                # grain modules (per-resource grains, optional)
    ...
```

For the common case of "I want this resource type to use the standard
``state.sls``/``state.apply``", re-export from the salt module using
``salt.utils.functools.namespaced_function`` so the re-exported
function picks up the per-resource loader's ``__salt__`` /
``__opts__`` / ``__resource__`` at call time:

```python
# salt/resources/<rtype>/modules/state.py (or a saltext extension's
#  equivalent path under saltext/<your-ext>/resources/<rtype>/modules/)
import salt.utils.functools
import salt.modules.state as _src

sls = salt.utils.functools.namespaced_function(_src.sls, globals())
apply_ = salt.utils.functools.namespaced_function(_src.apply_, globals())
highstate = salt.utils.functools.namespaced_function(_src.highstate, globals())
__func_alias__ = {"apply_": "apply"}
```

Salt extensions follow the same layout under their package — e.g.
``saltext/<ext>/resources/<rtype>/modules/<slot>.py`` — and Salt's
loader picks them up automatically via the entry-point package
discovery.

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

Applies to resource types that ship a per-type `state.py` override
(today: SSH).  For resource types without one, `state.apply` falls
through to the standard ``salt/modules/state.py`` (post-Gap-2 layout
fix) — running the state on the managing minion with the per-resource
loader as ``__salt__``.

**Status:** fixed.

---

## Summary table

| Scenario | Works today? | Notes |
|---|---|---|
| `salt-call -r test.ping` (managing minion + all resources) | **Yes** | Gap 1 — fixed via `-r/--tgt/--tgt-type` |
| `salt-call -r --tgt dummy-01 test.ping` (specific resource) | **Yes** | Gap 1 — fixed |
| `salt-call -r --tgt dummy-01 grains.items` (per-resource grains) | **Yes** | Gap 1 — fixed |
| `salt -C 'T@ssh:hostA' state.apply` (transport-based resource) | **Yes** | Gap 3 — fixed (managing-minion remap on master) |
| `salt-call -r state.sls foo` against a logical resource | **Yes** | Standard `state.sls` loads in the per-resource loader (Gap 2 fix); resource-specific overrides win when the rtype provides them |
| `salt resources-minion state.apply` (merge auto-dispatches) | No (resource_targets empty) | needs fun-aware target widening on minion |
| State modules in `states/` using `__salt__` in resource context | Per-resource loader's `__salt__` | Resource overrides win their slot via directory-order priority; standard modules fill the rest |
| State modules using `__minion__["x.y"]` for managing-minion escape hatch | **Yes** | Gap 2 — new dunder packed by `State.load_modules` in resource context |
| `.sls` files using resource execution functions via `module.run` | Yes (via master dispatch) | unchanged |

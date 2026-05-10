# Resource system: known gaps for state authoring and `salt-call`

Two related gaps found while building `saltext-opsdev` and trying to run
resource states locally with `salt-call`.

---

## Gap 1 — `salt-call` bypasses resource dispatch entirely

### What happens

`salt-call` uses `salt.cli.caller.BaseCaller`, which calls functions like this:

```python
# salt/cli/caller.py – BaseCaller.call()
ret["return"] = self.minion.functions[fun](*args, **kwargs)
```

Resource dispatch lives in `Minion._thread_return` (the full minion class).
`BaseCaller` never reaches that code path.  Even though `SMinion.gen_modules`
correctly calls `MinionBase.gen_modules` — which does set up `resource_loaders`
and calls `resource_type.init()` — those loaders are never consulted when
`salt-call` executes a function.

### Consequence

```bash
# This runs state.apply on the regular minion only.
# Resource targets are silently ignored.
salt-call --local state.apply
```

Any function that relies on `__resource_funcs__` or `resource_ctxvar` being
set will fail or return empty results when invoked via `salt-call`.

### Possible fix

`BaseCaller.call()` could check whether the requested function is in
`_MERGE_RESOURCE_FUNS` and, if so, also iterate `self.minion.resource_loaders`
to dispatch to each resource — collecting and merging the results the same way
`_thread_return` does.  For non-merge functions a `--resource-id` /
`--resource-type` flag would be needed to select a target.

---

## Gap 2 — `salt.loader.states` never injects `__resource_funcs__`

### What happens

`salt.loader.states` packs these dunders into every state module:

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

`__resource_funcs__` is **not** in that list.  It is only injected by
`salt.loader.resource_modules` (the per-type execution-module loader).

### Consequence

A state module (files in `states/`) that calls `__resource_funcs__[...]` will
fail at runtime with a `NameError` or an empty-dict lookup, regardless of
whether the minion has resource loaders configured.  This affects any Salt
extension that puts resource-aware state logic in `states/`.

The SSH resource avoids this entirely: its state-like behaviour lives in
`salt/modules/sshresource_state.py` — an **execution** module — which does
have `__resource_funcs__` injected.  State-format dicts (the four-key
`{result, comment, changes, name}` shape) are returned from execution
functions, not from a `states/` module.

### Consequence for `saltext-opsdev`

`src/saltext/opsdev/states/starting_stateresource_env.py` follows the
intuitive pattern (state functions in `states/`) but is architecturally
incorrect.  `__resource_funcs__` will never be available there.

The functions (`deployed`, `absent`, `lease_current`) should be moved to
`src/saltext/opsdev/modules/starting_stateresource_env.py` alongside the
existing `status`, `connection_info`, etc. functions.  Callers then use
`module.run` in `.sls` files, or invoke them directly as execution functions
via resource dispatch.

### Possible fix

Pass `resource_funcs` into `salt.loader.states` when the loader is being
built in a resource context (i.e. when `opts.get("resource_type")` is set),
and add `__resource_funcs__` to the `pack` dict.  This would let state modules
in `states/` use the familiar `__resource_funcs__[...]` dunder and allow
`.sls`-based state authoring for resource types.

---

## Summary table

| Scenario | Works today? | Workaround |
|---|---|---|
| `salt-call --local state.apply` hits resources | No | Use full minion + master |
| `salt-call --local ss_env.status` for a resource | No | Use full minion + master |
| State functions in `states/` using `__resource_funcs__` | No | Move to `modules/` execution module |
| State functions in `modules/` using `__resource_funcs__` | Yes (via master dispatch) | — |
| `.sls` files using resource execution functions via `module.run` | Yes (via master dispatch) | — |

# Gap 5 — `state.py __virtual__` guard is too broad: resource types without a `state.*` override lose `state.sls`

Discovered: 2026-05-10, during `salt-call -r --tgt dwozniak-91-ss state.sls starting_state.vcf-91-dev`
after adding a second resource type (`ssh`) to the Pillar alongside `starting_state`.

**Status: fixed via the per-type directory layout** (`salt/resources/<rtype>/modules/`).
The broad `__virtual__` guard in `salt/modules/state.py` was deleted entirely;
the standard ``state.py`` now loads in every context.  Per-type ``state.py``
overrides under ``salt/resources/<rtype>/modules/`` (or under any
extension's ``saltext/<ext>/resources/<rtype>/modules/``) win their slot
via directory-order priority in :func:`salt.loader._module_dirs`.  See
``RESOURCE_STATE_GAPS.md`` for the full picture.

---

## What happened

The following command failed immediately — before any state even ran — with:

```
Function 'state.sls' is not supported for resource type 'starting_state'.
```

```bash
sudo salt-call -r --tgt dwozniak-91-ss --local \
  --config-dir .../saltcall \
  state.sls starting_state.vcf-91-dev
```

The same command had worked on the two prior runs (when only the `starting_state`
resource type was active).  The only thing that changed between the working and
failing run was that `pillar/ssh_resources.sls` now contained a real SSH host
(`jumphost-dwozniak-91-ss`), causing the minion to discover and build a loader
for the `ssh` resource type in addition to `starting_state`.

---

## Root cause

### 1. The Gap 2 fix introduced a broad `__virtual__` guard in `salt/modules/state.py`

Commit `5fd6da6810a` ("state: call resource init() in State.load_modules") changed
`State.load_modules` to build `self.functions` via `salt.loader.resource_modules`
instead of `minion_mods` when `opts["resource_type"]` is set.  As a companion
change, `salt/modules/state.py` was given a `__virtual__` guard that returns
`False` for **all** resource types:

```python
# salt/modules/state.py
def __virtual__():
    if __opts__.get("resource_type"):
        return False, "state: not loaded in resource-type loaders"
    ...
    return __virtualname__
```

The intent was to yield the `"state"` virtualname slot to resource-specific
override modules like `sshresource_state` (which provides `state.sls`,
`state.highstate`, and `state.apply` for SSH resources).

### 2. The guard is too broad — it fires for ALL resource types, not just `ssh`

`sshresource_state` only overrides `state.*` when `resource_type == "ssh"`:

```python
# salt/modules/sshresource_state.py
def __virtual__():
    if __opts__.get("resource_type") == "ssh":
        return __virtualname__   # "state"
    return False, "sshresource_state: only loads in an ssh-resource-type loader."
```

For resource types that have **no** override module (e.g. `starting_state`,
`dummy`, any future custom type), the outcome is:

- `salt/modules/state.py` → returns `False` (blocked by the broad guard)
- `sshresource_state.py`  → returns `False` (wrong resource type)
- Result: **the `state` virtualname slot is empty** in the resource loader for
  that type.

### 3. The caller-level check catches the empty slot before `State.load_modules` is reached

`salt/cli/caller.py` checks `if fun not in loader` against the minion's
per-type `resource_loaders[rtype]` loader **before** running the function:

```python
# salt/cli/caller.py ~387
loader = getattr(self.minion, "resource_loaders", {}).get(rtype)
if fun not in loader:
    results[rid] = (
        f"Function '{fun}' is not supported for resource "
        f"type '{rtype}'."
    )
    continue
```

Because `state.sls` is absent from `resource_loaders["starting_state"]`,
the call is rejected here and never reaches `State.load_modules` at all.

### 4. Why it only appeared when the `ssh` resource type was added

When only `starting_state` was in the Pillar, only a `starting_state`
resource loader was built.  `state.sls` was absent from it (same root cause),
but the two successful runs that preceded this failure had a warm Pillar cache
that still showed `hosts: {}` for the SSH resource — the minion had not yet
reloaded the updated Pillar.  Once the cache expired and the full Pillar
(including a real SSH host) was compiled, the minion built a loader for `ssh`
too.  The `ssh` loader's presence is what finally caused the lazy evaluation
of `resource_loaders["starting_state"]` to reveal the missing `state.sls`.

(The `starting_state` loader was always broken post–Gap 2; the Pillar cache
masked the failure for two runs.)

---

## How it was fixed

**Option B** was implemented in commit `d28f8d2e981`: a narrow
`_RESOURCE_TYPES_WITH_STATE_OVERRIDE = frozenset({"ssh"})` sentinel is
defined in `salt/modules/state.py`.  The `__virtual__` guard only returns
`False` for resource types *in* that set.  For all other resource types
(e.g. `starting_state`) the standard `state.sls` slot is available.

For resource types that need customised state execution (e.g. different
transport, merged module loaders), a per-type override module can be provided
in a Salt extension:

- **`starting_state`** → `saltext-opsdev` ships
  `src/saltext/opsdev/modules/starting_stateresource_state.py` which:
  1. Claims the `state` virtualname ahead of `salt.modules.state`
     (loads first alphabetically).
  2. Builds a local `HighState` (manages states on the same machine,
     not via SSH like `sshresource_state`).
  3. Applies the Gap 4 local workaround: after `HighState` initialises
     its `resource_modules` loader, the standard `minion_mods` set is
     merged in for any slot not already claimed by a resource-specific
     module — making `cmd.*`, `pkg.*`, `file.*`, etc. available alongside
     `ss_env.*` in the same SLS.

---

## Relationship to Gap 4

Gap 4 documents that `State.load_modules` using `resource_modules` instead of
`minion_mods` causes standard modules (`cmd`, `pkg`, `file`, etc.) to be
absent from the state's `__salt__`.

Gap 5 was a **prerequisite failure**: the caller rejected the function call
entirely before `State.load_modules` was reached.  The Gap 5 fix unblocked
dispatch; `starting_stateresource_state` then resolves Gap 4 locally inside
the extension without requiring a Salt core change.

Both gaps were introduced by the same commit (`fccc5263638`).

# Derived Resources and the Resource Module Loader Gap

Two related topics discovered while building `saltext-opsdev` and applying
real-world states against a VCF starting-state environment.

---

## Gap 4 — Resource context replaces standard Salt modules instead of augmenting them (OPEN)

### What happened

When running a standard Salt state (e.g. `openvpn/local.sls`) via
`salt-call -r --tgt dwozniak-91-ss state.sls openvpn.local`, the `pkg.installed`
state failed with:

```
KeyError: 'cmd.run_stdout'
```

The full traceback showed `salt/states/pkg.py` calling
`__salt__["pkg.list_pkgs"]`, which internally called
`__salt__["cmd.run_stdout"]`, which was absent from the loader.

Two other failures confirmed the scope:
- `file.managed` could create a directory but failed to copy a file that
  required reading the source via the file client (module absent).
- `host.present` could *read* `/etc/hosts` (pure Python, no module
  dependency) but crashed when trying to *add* a new entry because that
  calls `hosts.add_host`, which needs `cmd` for the write path on some
  platforms.

### Root cause

The Gap 2 fix (`State.load_modules` building `self.functions` via
`salt.loader.resource_modules` instead of `minion_mods`) is **too
aggressive**.  `resource_modules` only loads modules whose `__virtual__`
returns True when `opts["resource_type"]` is set — that is, resource-specific
override modules.  Standard modules like `cmd`, `pkg`, `file`, `hosts`,
`aptpkg`, etc. virtual themselves *out* when `resource_type` is set
(or were never written to check it, so they load normally but `cmd` itself
isn't indexed because something earlier in the chain broke the loader
context).

The result: **resource-specific modules entirely replace the standard
module set** in the state's `__salt__`, rather than augmenting it.

### Intended design

The resources architecture intends for resource-specific modules to
**override specific function slots** while leaving the rest of the standard
module set intact.  For example:

- `dummyresource_test.py` overrides `test.ping` when `resource_type ==
  "dummy"`, but `test.echo`, `test.sleep`, etc. should still come from
  the standard `test` module.
- `starting_stateresource_env.py` adds `ss_env.*` functions, but `pkg.*`,
  `cmd.*`, `file.*`, `hosts.*` etc. should all remain available.

This is analogous to Python's MRO: resource-specific modules have higher
precedence for the slots they claim, but they do not shadow everything else.

### Proposed fix

In `State.load_modules`, when `resource_type` is set, build **both** loaders
and merge them with resource-specific modules taking precedence:

```python
if resource_type:
    self.resource_funcs = salt.loader.resource(
        self.opts, utils=self.utils, context=self.state_con
    )
    # Start with the full standard module set so pkg, cmd, file, etc. work
    base_functions = salt.loader.minion_mods(
        self.opts,
        utils=self.utils,
        context=self.state_con,
        proxy=proxy,
    )
    # Build the resource-specific layer
    resource_functions = salt.loader.resource_modules(
        self.opts,
        resource_type,
        resource_funcs=self.resource_funcs,
        utils=self.utils,
        context=self.state_con,
    )
    # Merge: resource-specific overrides win, standard modules fill the gaps
    base_functions.update(resource_functions)
    self.functions = base_functions
else:
    self.functions = salt.loader.minion_mods(...)
```

This way `__salt__["test.ping"]` dispatches to the resource-specific
override while `__salt__["cmd.run_stdout"]` still resolves to the standard
implementation.

### Impact without this fix

Any `.sls` file that mixes resource-aware states (`ss_env.*`) with standard
Salt states (`pkg.installed`, `file.managed`, `host.present`) cannot be
applied in a resource context.  Workaround: a two-step shell script that
fetches resource data first, then applies the SLS with `--local` (no `-r`)
with the data injected as Pillar.  This works but defeats the goal of a
single `state.apply` driving the full workflow.

**Status:** open.

---

## Derived Resources

### Problem

All resources in the current system are **statically declared** in Pillar
before Salt runs.  This works well for resources whose connection details
are known ahead of time (e.g. a Kubernetes cluster with a fixed API
endpoint).

But some resources only *become knowable* as a consequence of another
resource reaching a desired state.  The canonical example from `saltext-opsdev`:

```
starting_state/dwozniak-91-ss    →   (after deploy)   jump host at 10.162.38.32
```

The jump host's IP, username, and password live inside `ss_env.connection_info`,
which can only be fetched after the starting-state environment is in the
`succeeded` state.  There is no stable, pre-known value to put in Pillar.

A developer who wants Salt to manage both the starting-state environment
**and** the jump host's OpenVPN server today must:

1. Run `ss_env.connection_info` manually.
2. Copy the IP/credentials into a second Pillar file.
3. Apply a separate state targeting the jump host.

This breaks the "single `state.apply` owns the full desired state" contract.

### Concept

A **derived resource** is a resource whose Pillar-equivalent configuration
is emitted at runtime by another resource's state function, rather than
declared statically.  The emitting state function registers the derived
resource into a shared registry; subsequent states in the same apply (and
future runs) can then target it using the same `T@type:id` compound syntax
as any static resource.

### Lifecycle

```
Run 1 (first apply)
───────────────────
ss_env.deployed("dwozniak-91-ss")
  → environment reaches "succeeded"
  → calls connection_info()
  → registers derived resource:
      type: ssh_host
      id:   jumphost-dwozniak-91-ss
      config:
        ip:       10.162.38.32
        username: worker
        password: FNAQo^@lzkZFg47g
        source:   starting_state/dwozniak-91-ss   ← provenance link

ssh_host.state_applied("jumphost-dwozniak-91-ss", mods="openvpn.init")
  → resource now in registry → executes normally

Run 2+ (idempotent re-apply)
────────────────────────────
ss_env.deployed("dwozniak-91-ss")
  → already "succeeded", no-op
  → re-registers derived resource (idempotent, overwrites stale config)

ssh_host.state_applied(...)
  → normal execution against cached registration
```

### Registry design

The derived resource registry needs two scopes:

**In-run scope (`__context__`)**  
Entries survive for the lifetime of a single `state.apply` call.  Sufficient
for resources that are always re-derived from an upstream resource on every
run (e.g. jump host IP that could change if the environment is redeployed).

**Cross-run scope (local cache file)**  
Entries persist to a JSON file in `cachedir` (e.g.
`/var/cache/salt/minion/derived_resources.json`).  Allows `T@ssh_host:jumphost-*`
targeting in subsequent `salt -C` commands without repeating the full
upstream state.  Cache is invalidated when the source resource's grains
change (e.g. `starting_state_status` transitions away from `succeeded`).

```python
# salt/utils/resources.py  (proposed additions)

def register_derived(opts, resource_type, resource_id, config, source_srn=None):
    """
    Register a derived resource into the in-run context and the local cache.

    source_srn: the SRN of the resource that produced this derivation,
                e.g. "starting_state/dwozniak-91-ss".  Used to invalidate
                the cache when the source resource changes state.
    """

def get_derived(opts, resource_type, resource_id):
    """
    Return derived config dict or None.  Checks in-run context first,
    then the local cache.
    """

def invalidate_derived(opts, source_srn):
    """
    Remove all derived resources whose source_srn matches.
    Called automatically when the source resource's grains are refreshed
    and the status grain changes.
    """
```

### Integration points

**`resource_type.discover(opts)`**  
Each resource type's `discover()` must check both Pillar and the derived
registry.  Example for `ssh_host`:

```python
def discover(opts):
    # Static Pillar declarations
    ids = list(pillar_resources_tree(opts).get("ssh_host", {}).keys())
    # Derived registrations
    ids += salt.utils.resources.list_derived(opts, "ssh_host")
    return ids
```

**`resource_type.init(opts)`**  
When `init` is called for a derived resource, it reads config from the
registry rather than from Pillar:

```python
def init(opts):
    resource_id = __resource__["id"]
    cfg = (
        pillar_resources_tree(opts).get("ssh_host", {}).get(resource_id)
        or salt.utils.resources.get_derived(opts, "ssh_host", resource_id)
    )
    if cfg is None:
        raise RuntimeError(f"ssh_host '{resource_id}' not found in Pillar or derived registry")
    __context__[CONTEXT_KEY] = {"initialized": True, **cfg}
```

**State module emission**  
A state function registers derived resources as a side effect, after the
upstream resource is confirmed healthy:

```python
# saltext/opsdev/states/starting_stateresource_env.py

def deployed(name, cycle=None, wait=False, register_resources=True, **_kwargs):
    # ... existing logic to ensure the env is running ...

    if result["result"] and register_resources:
        conn = __salt__["ss_env.connection_info"]()
        jb = conn.get("linux_jumpbox", {})
        if jb.get("ip"):
            salt.utils.resources.register_derived(
                __opts__,
                resource_type="ssh_host",
                resource_id=f"jumphost-{name}",
                config={
                    "ip":       jb["ip"],
                    "username": jb.get("username", "worker"),
                    "password": jb.get("password", ""),
                },
                source_srn=f"starting_state/{name}",
            )

    return result
```

### Example SLS using derived resources

```yaml
# dev/vcf-91-full.sls

# 1. Ensure starting state is up and register derived resources.
ensure_environment:
  ss_env.deployed:
    - name: dwozniak-91-ss
    - cycle: Cycle59
    - register_resources: true

# 2. Ensure lease.
ensure_lease:
  ss_env.lease_current:
    - name: dwozniak-91-ss
    - min_days_remaining: 3
    - extend_by: 7
    - require:
      - ss_env: ensure_environment

# 3. Configure OpenVPN server on the jump host.
#    Targets T@ssh_host:jumphost-dwozniak-91-ss, registered in step 1.
configure_jumphost_vpn:
  ssh_host.state_applied:
    - name: jumphost-dwozniak-91-ss
    - mods: openvpn.init
    - require:
      - ss_env: ensure_environment

# 4. Generate client config from jump host and configure local machine.
configure_local_vpn:
  ssh_host.fetch_file:
    - name: jumphost-dwozniak-91-ss
    - remote_path: /etc/openvpn/client.ovpn
    - local_path: /root/nimbus-vpn.ovpn
    - require:
      - ssh_host: configure_jumphost_vpn

configure_local_hosts_and_vpn:
  ss_env.local_vpn_client:
    - name: dwozniak-91-ss
    - require:
      - ssh_host: fetch_file
```

Applied as a single command:

```bash
salt-call -r --tgt dwozniak-91-ss --local \
  --config-dir /home/dan/src/mops/salt/saltstack-raas/dev/local/saltcall \
  state.sls dev.vcf-91-full
```

### Relationship to Gap 4

The derived resource pattern requires Gap 4 to be fixed first.  Step 3
(`ssh_host.state_applied`) applies an `.sls` file against the jump host
in an `ssh_host` resource context.  That `.sls` (`openvpn/init.sls`) uses
standard Salt states (`pkg.installed`, `service.running`, `cmd.run`, etc.).
Without the merged loader, those states will fail with the same
`KeyError: 'cmd.run_stdout'` error observed in Gap 4.

### Open questions

1. **`ssh_host` resource type** — does not yet exist in this branch.  It
   would wrap `salt-ssh` or `paramiko` to execute Salt states and commands
   on remote machines without requiring a Salt minion on the target.

2. **Cache invalidation granularity** — should the cache be per-SRN or per
   grain key?  Invalidating on any grain change may be too broad; only
   `starting_state_status` transitions to/from `succeeded` should matter.

3. **Security** — derived resource configs contain credentials (passwords,
   keys).  The cache file must be readable only by root/the Salt user and
   ideally encrypted at rest, consistent with how Pillar secrets are handled.

4. **Ordering guarantees** — `salt.loader.resource`'s `discover()` is called
   at startup, before any states run.  Derived resources registered mid-apply
   won't be in the initial discovery set.  The state runner would need to
   re-call `discover()` (and re-run `init()`) for newly registered resource
   types after each state that emits `register_derived`.

5. **`state.apply` vs orchestration** — for complex multi-resource workflows,
   Salt's orchestration runner (`salt-run state.orchestrate`) may be a
   better fit than a single `state.sls`, since it has native support for
   cross-minion dependencies and ordering.  Derived resources inside
   orchestrate would follow the same registration API.

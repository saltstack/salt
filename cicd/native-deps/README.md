# Native-package dependency audit

Salt's "native" packages for 3008.x install into the OS's system Python
rather than the bundled onedir. That means every Python dep in
`requirements/static/pkg/py<ver>/linux.lock` has to come from one of two
places on the target host:

* **The distro's own `python3-*` repo** — preferred. Lets the distro
  manage security updates and avoids shipping bytes we don't own.
* **A `_vendor/` subdirectory inside the Salt native package** — fallback
  for deps the distro doesn't ship. Materialized at package build time
  via `pip install --target=...` and added to `sys.path` by Salt's init.

The tool in `tools/pkg/native_deps.py` answers two questions:

1. **For each target distro, which deps are missing from its native
   repo?** → feeds the per-build vendor list.
2. **For deps the distro _does_ ship, what version does it ship?** →
   feeds a per-pyver floor that constrains our `.in` files so pip-compile
   doesn't resolve to a version no distro actually carries.

## Workflow

Regenerate when any of these change: a target distro's base image, Salt's
`requirements/*.in` / `requirements/static/pkg/pyX.Y/linux.lock`, or the
distro-slug set in `tools/pkg/native_deps.py`.

```sh
# 1. Audit every supported distro (slow -- each spins up a container
#    and runs ~60 `yum info` / `apt-cache show` calls).
tools pkg native-deps list-platforms
tools pkg native-deps audit photon-5
tools pkg native-deps audit debian-12
# ... one per slug ...

# 2. Compute proposed floors from the committed JSONs.
tools pkg native-deps floors

# 3. Review floors.yml, promote agreed floors into requirements/*.in,
#    regenerate locks via pre-commit.

# 4. For each native-package build, emit the vendor list.
tools pkg native-deps vendor-plan photon-5
```

## Outputs

All outputs live in this directory and are committed to the repo.

| File | Owner | Purpose |
|------|-------|---------|
| `<slug>.json` | `audit` | Per-distro probe: image digest, python version, every lock entry's `native_pkg` + `native_version` + `status` + Salt-side `import_tier` + `import_sites`. |
| `floors.yml` | `floors` | Per-pyver, per-pkg: `floor` (min across native-shipping distros), `votes` (slug → version), `missing_in` (distros that'd vendor), `gap_major`. Review artifact only — never a build input. |
| `<slug>-vendor.txt` | `vendor-plan` | Requirements-style list of `pkg==ver` the native package build must pip-install into `_vendor/`. Grouped into three tiers; only the first is uncommented. |

## Import tiers

Every audit entry carries an `import_tier` classifying how Salt code
uses the dep:

| Tier | Meaning | Vendor default |
|------|---------|----------------|
| `module-top` | Unindented `import X` in a hot-path file under `salt/`. Missing → ImportError the moment Salt loads the owning module. | **Must vendor** (or drop the owning subsystem from the native build). |
| `feature-opt-in` | Unindented, but every owning file is lazy-loaded from a feature selector (transport dispatch, netapi backend). Missing → ImportError only on a deployment that selects the feature. Annotated with `owning_features`. | Optional — vendor only if the native package declares the feature supported. |
| `indented` | Only appears inside a `try/except` or inside a function body. Missing → feature degrades silently. | Optional — commented out in `vendor-plan`, uncomment to keep the feature functional. |
| `none` | No reference anywhere under `salt/`. Pure transitive — only pulled in by another dep's `install_requires`. | Only needed if its parent is vendored. |

The hand-maintained `LAZY_FEATURE_OWNERS` map in
`tools/pkg/native_deps.py` names the files/dirs that count as lazy
feature owners (transport backends, netapi backends). Add to it when a
new lazy-loaded subsystem lands.

`vendor-plan` emits one section per tier. `import_sites` on each audit
entry lets you click through to the exact `file:line` locations.

## Interpreting `gap_major`

When a dep is shipped natively on every target distro but the min-shipped
version is many majors behind our lock pin, you have three options:

1. **Accept the floor** — pin `>=<floor>` in `requirements/*.in` and
   constrain Salt code to that API surface.
2. **Raise the floor + vendor on the lagging distro** — treat the lagging
   distro as "vendored" for this dep. The floor is then re-inferred from
   the remaining distros that still ship it natively.
3. **Drop the lagging distro from the native-package matrix.**

The tool surfaces the gap and the voters; the choice is manual.

## Target distro set

The slugs below are what `audit-all`-style loops iterate. Add or remove
in `DISTROS` in `tools/pkg/native_deps.py`. Base images are stock
upstream tags so the audit reflects what the distro's own repo ships,
not whatever `salt-ci-containers` has pre-provisioned.

| Slug | Image |
|------|-------|
| amazonlinux-2023 | `amazonlinux:2023` |
| debian-12 | `debian:12` |
| debian-13 | `debian:13` |
| fedora-43 | `fedora:43` |
| photon-5 | `photon:5.0` |
| rockylinux-9 | `rockylinux:9` (+ `epel-release`) |
| ubuntu-22.04 | `ubuntu:22.04` |
| ubuntu-24.04 | `ubuntu:24.04` |
| ubuntu-26.04 | `ubuntu:26.04` |

## Known quirks

* **DNS inside the probe container.** The tool passes `--dns 8.8.8.8` on
  container create. Hosts whose `/etc/resolv.conf` points at internal
  nameservers Docker can't route to otherwise hang on `apt-get update` /
  `tdnf update`.
* **Entrypoint is `sleep 2147483647`, not `tail -f /dev/null`.** `tail
  -f` consumes an inotify instance, which may be exhausted on busy
  workstations and causes the probe container to exit before any `docker
  exec` lands.
* **Index refresh is best-effort.** If `tdnf update` / `apt-get update`
  fails (common when offline or behind captive DNS), the audit continues
  against prebaked image metadata and the result is still usable. The
  warning is logged.
* **Package-name mapping is manual.** Debian and Photon both call `pyzmq`
  something unusual (`python3-zmq` vs `python3-pyzmq`). The per-distro
  `pkgmap` in `tools/pkg/native_deps.py` captures the exceptions;
  everything else is `python3-<lock-name>`.

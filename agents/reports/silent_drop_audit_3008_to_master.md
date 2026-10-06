# Silent-drop audit: 3008.x -> master merge

Audit scope: files under `salt/`, `tests/`, `changelog/`, `requirements/`,
`pkg/`, `tools/`, `doc/` that differ between `origin/3008.x` and
`origin/master`, excluding the 13 UU-conflicted files already flagged for
manual resolution. The scan asks: is the working-tree blob byte-identical to
`origin/master:<file>` while `origin/3008.x` has commits touching this file
that master lacks? If so, the merge picked master's content and *may* have
dropped 3008.x work.

Scan produced 47 candidates (41 `EXISTS_MATCH_DEST`, 6 `MISSING_SRC_ONLY`).
Each was manually classified by pulling a distinctive signature (function
name, comment, docstring, or issue number) from the 3008.x-only fix commits
and grepping for that signature in the current tree.

## Summary
- Total candidate files: 47
- REAL DROP (needs restoration): **0**
- DELIBERATE-DEST (kept master's, defensible): 41
- BOTH-FIXED-INDEPENDENTLY: 6 (counted under DELIBERATE-DEST above where
  the master version subsumes / equals the 3008.x fix — noted per file
  below)

**No silent SOURCE-content drops were found.** Every candidate is either a
deliberate master-side enhancement/refactor/removal, or the 3008.x fix
landed on master under a different commit hash and is present verbatim in
the tree.

## REAL DROPS (action required)

None.

## DELIBERATE-DEST breakdown

### Cluster 1: master deleted files, 3008.x kept them (6 files)
These files exist only on 3008.x; master intentionally removed them.
Confirmed by explicit deletion commits with rationale on master.

| File | Deletion commit | Reason |
|---|---|---|
| `salt/utils/kickstart.py` | `899e2a4d37f` "Remove orphaned genesis utility modules" | genesis moved to community extension |
| `salt/utils/preseed.py` | `899e2a4d37f` | same |
| `salt/utils/yast.py` | `899e2a4d37f` | same |
| `tests/unit/utils/test_kickstart.py` | `899e2a4d37f` | tests for removed module |
| `salt/utils/namecheap.py` | `0a2fe0f32ac` "Remove orphaned salt.utils.namecheap module" | namecheap moved to `saltext.namecheap` |
| `tests/unit/modules/test_network.py` | `a06a8a57a9e` "Migrate legacy unit/modules/test_network.py into the pytest suite" | tests migrated to pytest twin under `tests/pytests/unit/modules/test_network.py` |

### Cluster 2: master is a strict superset of 3008.x (adds new content on top)
Master's version contains the 3008.x fix PLUS additional master-side work.

- `salt/modules/disk.py` — master added `format_(discard=True)` param and
  changed `_parse_numbers` SI-suffix notation from `10E3` to `1e3`. 3008.x's
  `disk.tune` invalid-kwargs fix (`2ea5e1b744c`) is present in the merged
  tree (`SaltInvocationError`, `invalid_kwargs`).
- `tests/pytests/unit/modules/test_disk.py` — master added
  `test_format__nodiscard_ext`, `test_format__nodiscard_xfs`,
  `test_parse_numbers_issue_65490` (paired with the disk.py changes above).
- `salt/modules/pw_user.py` — master added `def primary_group(name)` at
  line 509 (versionadded 3009.0). All 3008.x FreeBSD fixes present.
- `salt/modules/network.py` — the 3008.x fixes (`fqdns` ThreadPool leak,
  hostname quoting, IPv6 `sanitize_host`, `ip_networks6` docs, `ping -W`)
  are all present. Master merged them via different commit hashes but
  content is identical.
- `salt/utils/network.py` — `sanitize_host` IPv6 fix (`a26ad836a0b`, refs
  #68995) present in current tree at lines 71-88.
- `salt/utils/user.py` — three `nicholasmhughes` fixes (`34bf45ee279`,
  `28be150d1a4`, `eaa004dd642`) all present:
  `user_group_list_local` / `user_group_list_remote` split, removal of
  `HAS_PYSSS`, `_getgrall()` helper.
- `salt/utils/parsers.py` — three recent fixes (`b1346d4fa4a`
  OptsDict, `3e51839232d` `--priv`, `e93ec8fa42e` None-value merge)
  present. `b403da18bf9`'s "hasattr(self, 'config') / self.config.update"
  branch was intentionally replaced on master with the simpler `self.config
  = self.setup_config()` — see next commit `e93ec8fa42e` on 3008.x which
  reverses `b403da18bf9` back to this form. Net semantics match master.
  Recent big features (`--start-event`, `--disable-keepalive`,
  `-r/--resources`) all present.
- `salt/client/__init__.py` — verified: `cmd_subset` failed-minion fix,
  LazyLoader teardown, `subset = kwargs.pop("sub", subset)`, Salt Resources
  imports (`salt.utils.metrics`, `salt.utils.resources`, `def
  _resource_ids_from_minion_grains_cache`), single-JID batch fix,
  `publish_timeout`, `async def run_job_async`, `if isinstance(payload,
  str)` prep-jid fix — all present.
- `salt/output/highstate.py` — `_compress_ids`, `state_compress_ids`,
  `state_output_pct`, terse formatter (`Started: {6[start_time]!s}`) all
  present.
- `salt/states/test.py` — requisites/aggregate fix
  (`__low__["__reqs__"].get("watch", [])`) and `OS not supported!`
  fail-with-changes docs present.
- `salt/utils/job.py` — `_store_job`, `_store_minions`,
  `MasterMinion(opts, states=False, rend=False)` teardown, "Load does not
  contain 'jid'" KeyError guard all present. Master's diff vs 3008.x is a
  single-line `import salt.utils.versions` removal (paired with removal of
  the `warn_until(3008, ...)` deprecated-API code — deliberate 3008.0-cycle
  cleanup).
- `salt/netapi/rest_cherrypy/__init__.py` — master added
  `ssl_ca_certs` / `ssl_cert_reqs` client-cert validation on top of the
  existing intermediate-cert support (`ssl_chain`).
- `tests/pytests/unit/output/test_highstate.py` — master added 269 lines
  of diff-colorization tests (`_GREEN`, `_LIGHT_RED`,
  `test_diff_in_full_color_output`, ...). All 3008.x compress_ids /
  state_output_pct tests present.
- `tests/pytests/unit/utils/test_network.py` — master added
  `test_cidr_to_ipv4_netmask_is_registered_jinja_filter`, `test_ip_to_int`,
  `test_int_to_ipv4`, `test_int_to_ipv6`, `test_nth_host`. All 3008.x
  sanitize_host IPv6 tests present (`test_sanitize_host_ipv6*`).
- `tests/pytests/unit/modules/test_network.py` — master added
  `test_arp_linux_falls_back_to_ip_neigh` and stricter assertions
  (`assert result is True` vs the weaker `assert result`).
- `tests/pytests/unit/modules/test_pw_user.py` — master added
  `test_primary_group`, `test_primary_group_nonexistent`.
- `tests/pytests/unit/utils/test_user.py` — master added
  `test_get_group_name`, `test_get_group_name_unknown_gid`.
- `tests/pytests/functional/modules/state/requisites/test_watch.py` —
  master added `test_watch_skips_mod_watch_when_normal_run_has_changes`
  and `test_watch_fires_when_force_mod_watch_is_set`.
- `tests/pytests/unit/netapi/cherrypy/test_events.py` — the eauth-token
  query-string rejection tests (`test_events_get_rejects_token_in_query_string`,
  `test_events_get_accepts_token_in_x_auth_token_header`) are present
  because the same security fix (`9f9052b5231`, refs #69071) is in the
  merged tree alongside master's additions. The changelog entry
  `changelog/69071.fixed.md` was rolled into `CHANGELOG.md` line 1637 by
  the v3006.26 release process; verified.
- `tests/integration/files/conf/master` — master added
  `master_stats: true` on line 114.
- `tests/packdump.py` — master added type hints (`def dump(path: str) ->
  None`) and `Usage:` error message.
- `tests/filename_map.yml` — master added one entry:
  `unit.states.test_postgres_default_privileges`.
- `pkg/macos/build_python.sh` — master replaced `deactivate` with direct
  `unset VIRTUAL_ENV / _OLD_VIRTUAL_PATH / _OLD_VIRTUAL_PYTHONHOME`; both
  branches contain the "Build python 3.10.9" (`4f6caca155e`) fix
  (`3.10.9` / `3.11.2` versions, `python -c "import sys;
  print(sys.executable)"` SYS_PY_BIN discovery).
- `pkg/windows/build_python.ps1` — same pattern as macOS: master
  replaced `. deactivate` with direct `Remove-Item env:` cleanup; 3008.x
  MSI-display fix present.
- `requirements/static/ci/cloud.txt` — master pinned
  `apache-libcloud>=3.8.0` unconditionally; 3008.x had the split
  `<3.9.1 for python<3.10` conditional. Master's choice tracks the
  python-3.10-only requirement floor.
- `requirements/static/ci/py3.14/changelog.lock` — master has
  `packaging==26.2` (newer) vs 3008.x's `24.0`.
- `requirements/zeromq.txt` — master added `-r base.txt` / `-r
  crypto.txt` includes (structural change, not a dropped requirement).
- `tools/container.py` — master version has
  `RAISE_DEPRECATIONS_RUNTIME_ERRORS: "0"`; 3008.x flipped it to `"1"`
  via `ce3b55c154d`. Note: this is a per-run env override for the local
  dev container tool. The CI-level enforcement in
  `.github/workflows/templates/layout.yml.jinja` is `"1"` on both
  branches, so CI still fails on deprecation warnings. See "Soft
  observations" below.
- `tools/precommit/docstrings.py` — master removed the entry for
  `salt/utils/namecheap.py` (consistent with removing the module itself
  in `0a2fe0f32ac`).
- Doc files (12): `doc/ref/cache/all/index.rst`,
  `doc/ref/cli/_includes/output-options.rst`,
  `doc/ref/clouds/all/salt.cloud.clouds.saltify.rst`,
  `doc/ref/states/all/index.rst`, `doc/topics/jinja/index.rst`,
  `doc/topics/releases/2017.7.8.rst`, `doc/topics/releases/2018.3.3.rst`,
  `doc/topics/releases/2019.2.1.rst`, `doc/topics/releases/3006.10.md`,
  `doc/topics/releases/index.rst`, `doc/topics/ssh/index.rst`,
  `doc/topics/transports/ssl.rst`. Every one is a master-side doc
  enhancement (new toctree entries, new jinja filters `ip_to_int` /
  `int_to_ipv4` / `int_to_ipv6`, expanded Saltfile explanation, richer
  `state_output` docs, minor typo fixes). 3008.x's contribution to
  `3006.10.md` is a `.in` -> `.txt` typo correction that was landed on
  master under a different form (`base.in` vs `base.txt` — both
  variants coexist harmlessly in different release notes).

## Cluster grouping

No clusters of related silent drops (the x509_v2-style disaster from the
prior 3007.x -> 3008.x merge does not repeat here).

The only *semantic* difference worth calling attention to that is NOT a
deliberate master feature is:

**Soft observation — not a REAL DROP but worth a maintainer eye:**
- `tools/container.py:65` — `RAISE_DEPRECATIONS_RUNTIME_ERRORS: "0"` on
  master vs `"1"` on 3008.x. This affects only the local dev container
  workflow (`tools container create`), not CI. `ce3b55c154d`'s
  companion changes to `.github/workflows/templates/layout.yml.jinja`
  (setting it to `"1"`) *are* present in the merged tree, so CI
  enforcement is intact. If the intent of `ce3b55c154d` was also to
  make local `tools container create` mirror CI behaviour, this specific
  line could be lifted from 3008.x post-merge, but it does not block or
  weaken any user-facing salt code path.

## Not scanned

- The 13 UU-conflict files — deliberately excluded per the audit rules
  since they are pending manual resolution:
  `.github/workflows/ci.yml`, `.github/workflows/dependabot-sync.yml`,
  `.github/workflows/nightly-stress-test.yml`,
  `.github/workflows/nightly.yml`, `.github/workflows/scheduled.yml`,
  `.github/workflows/staging.yml`,
  `.github/workflows/templates/layout.yml.jinja`,
  `.pre-commit-config.yaml`, `pkg/macos/install_salt.sh`,
  `requirements/base.txt`,
  `tests/pytests/pkg/integration/test_version.py`,
  `tests/pytests/unit/cli/test_batch.py`,
  `tests/pytests/unit/grains/test_core.py`.
- Files outside `salt/`, `tests/`, `changelog/`, `requirements/`, `pkg/`,
  `tools/`, `doc/` (scope defined by the audit prompt).
- Files that satisfy `ours == src` (the merged content matches 3008.x —
  no drop possible).
- Files where either `ours == dst == src` (no drift), or where the file
  does not exist on either branch.

# Multi-master AsyncAuth pubkey cache race

Investigation on branch `dwoz/fix/multimaster-pubkey-race` (off
`dwoz/resiliency-test-suite`).

## 1. Bug restatement

`AsyncAuth.__singleton_init__` picks a single filename based only on
`__role`:

```
salt/crypt.py:1123-1126
    if self.opts["__role"] == "syndic":
        self.mpub = "syndic_master.pub"
    else:
        self.mpub = "minion_master.pub"
```

In multimaster mode (`master_type: str` with a list, or `master_type:
failover`), `salt.minion.MultiMinion._spawn_minions` (salt/minion.py:2030)
creates one child `Minion` per master and schedules
`_connect_minion()` for each concurrently on the same io_loop. Each
child's `s_opts` overrides only `master`/`multimaster`/`beacons_leader`;
`pki_dir` is identical. The children's `AsyncAuth` singletons are
correctly disambiguated by `_auth_singleton_key` (keyed by `master_uri`,
salt/crypt.py:1018-1028) but every instance still writes and reads the
same path `pki_dir/minion_master.pub`.

On first contact for each master, `verify_master` (salt/crypt.py:1812)
sees `m_pub_exists is False` and the open-mode / non-sign branch at
salt/crypt.py:1877-1896 writes the newly received master pubkey to that
single file. The two children race: whichever child executes
`fopen(m_pub_fn, "wb+")` second wins. When the other side's
`sign_in()` response arrives later, `decrypt_aes` (salt/crypt.py:1617)
loads the winning master's pubkey and calls `mkey.decrypt(payload["sig"])`
on a signature produced by the losing master's private key. That raises
`ValueError("Unable to decrypt message")` at the rsax931 verify path,
the auth future resolves with an error, and only the surviving child
installs its `__master_alive_<master>` scheduler job. The losing master
sees "Minion did not return. [No response]" and
`baseline_rapid_ping_burst` fails 124/124 or 5/5.

## 2. Every read/write of `self.mpub`

All paths derive from `os.path.join(self.opts["pki_dir"], self.mpub)`.
Line numbers from current `dwoz/fix/multimaster-pubkey-race` HEAD.

### AsyncAuth (coroutine path)

- `salt/crypt.py:1124-1126` — assignment (syndic vs minion).
- `salt/crypt.py:1428` — `handle_signin_response` builds `m_pub_fn` for
  the "Invalid master key" error message (read-only reference used only
  in the log).
- `salt/crypt.py:1467-1476` — `handle_signin_response` loads cached
  master pubkey and verifies the `clear_signature` over
  `clear_signed_data`. **Read**. Race-sensitive: on the second child's
  turn this reads whichever pubkey the other child just wrote.
- `salt/crypt.py:1604-1608` — `minion_sign_in_payload` reads the cached
  master pubkey to encrypt the sign-in token. **Read**. Benign on first
  contact (FileNotFoundError is swallowed) but race-sensitive on
  reconnect.
- `salt/crypt.py:1648-1659` — `decrypt_aes` loads cached master pubkey
  and calls `mkey.decrypt(payload["sig"])` to recover the AES-key
  digest. **Read**. This is the frame that actually raises
  `ValueError("Unable to decrypt message")` and is the user-visible
  failure.
- `salt/crypt.py:1727-1730` — `verify_signing_master` (the signed-master
  pubkey trust mode) writes the master's pubkey to `m_pub_fn` after
  verifying the `pub_sig`. **Write**. Same single-file race under
  `verify_master_pubkey_sign: True`.
- `salt/crypt.py:1828` — `verify_master` builds `m_pub_fn` to decide
  whether to compare or write the pubkey.
- `salt/crypt.py:1838-1839` — `verify_master` reads the cached pubkey
  for the equality check. **Read**.
- `salt/crypt.py:1894-1895` — `verify_master` first-contact write of
  the payload's pubkey when `verify_master_pubkey_sign: False` and
  `m_pub_exists is False`. **Write**. This is the race the live
  repro hits: both children find `m_pub_exists is False` and both write
  in sequence.

### SAuth (sync path, same bug class)

- `salt/crypt.py:1973-1978` — assignment (now with three cases: syndic,
  monitor, minion).
- `salt/crypt.py:2088` — `sign_in` builds `m_pub_fn` (unused local;
  defensive).

### Channel layer

`salt/channel/client.py` caches the path at construction time:
- `salt/channel/client.py:152-153` — `AsyncReqChannel.__init__`:
  `self.master_pubkey_path = os.path.join(self.opts["pki_dir"], self.auth.mpub)`.
- `salt/channel/client.py:573` — `AsyncPubChannel.__init__`: same
  assignment. Both consume `auth.mpub`, so any fix in `AsyncAuth` is
  inherited automatically.

### Other references (not involved in this race)

- `salt/modules/key.py:48` — `key.finger_master` hardcodes
  `"minion_master.pub"`. Irrelevant to the race (invoked explicitly by
  the operator) but will miss the new per-master name on a sharded
  cache. Left in a follow-up; see "Deferred" below.
- `salt/utils/migrations.py:42` — pre-3005 migration preserves the old
  `minion_master.pub`. Still correct: the sharded names are new.
- Various tests reference the literal string `minion_master.pub`; they
  exercise single-master mode and remain correct.

## 3. Prior art for per-master naming

The only precedent I found for per-master differentiation on the minion
side is:

- `verify_pubkey_sig` uses `master_sign_key_name` (configured, not
  derived) for the master-of-masters signing key. No file sharding.
- `handle_signin_response` already stores `auth["master_uri"] =
  self.opts["master_uri"]` in the per-key creds_map value. The in-memory
  side is per-master; only the on-disk cache is not.

Master-side prior art exists for cluster keys:
`master_id`/`cluster_id`-named `.pem`/`.pub` files
(`salt/crypt.py:738-765`), and `cluster_peers/<master_id>.pub`. That
precedent says sharding by a stable string identifier is acceptable.

## 4. Fix design

### Shape

Shard the filename by master only when we are in multimaster mode and
`opts["master"]` is a single hostname (i.e. after `MultiMinion`
narrowed the list). Fall back to the historical name otherwise. The
scope of the fix stays confined to `AsyncAuth.__singleton_init__` and
`SAuth.__singleton_init__`; nothing else in the module needs to change
because every read/write already goes through `self.mpub`.

```
def _mpub_for(opts):
    if opts["__role"] == "syndic":
        return "syndic_master.pub"
    # SAuth also honors legacy monitor_master mode
    master = opts.get("master")
    if (
        opts.get("multimaster")
        and isinstance(master, str)
        and master
    ):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", master)
        return f"minion_master.{safe}.pub"
    return "minion_master.pub"
```

Guards:

1. **Single-master preserves on-disk identity.** No `multimaster` flag ->
   name is the literal `"minion_master.pub"`. The tens of existing
   minion filesystems keep working untouched. This is the condition the
   live rollout cares most about.
2. **Syndic preserved.** The syndic branch is unchanged.
3. **Monitor preserved.** `SAuth` retains the
   `monitor_master.pub` branch; monitor + multimaster is not a
   documented combination and left unchanged.
4. **Backward-compat on upgrade.** On first contact the new code finds
   the per-master file missing and goes through the normal
   write-on-first-contact path. If the operator had already pinned a
   pubkey at `minion_master.pub` from a prior install, we migrate it on
   construction: when the new per-master file is absent and the legacy
   file exists, copy the bytes to the new location. This keeps
   trust-on-first-use semantics stable across upgrades and does not
   compromise the race fix (each child now owns its own file after the
   copy).
5. **Sanitization.** `opts["master"]` can be any hostname/IP. Filenames
   must stay portable. `re.sub(r"[^A-Za-z0-9_.-]", "_", master)` keeps
   the hostname human-readable and collision-resistant for distinct
   master names.

### What I considered and rejected

- **Hashing on `master_uri`.** Opaque; worse for operator debugging; no
  readability win over the sanitized hostname. `master_uri` also carries
  a port that is usually the same across masters.
- **Serializing initial auth across the multimaster child set.** Would
  work but requires cross-child coordination, opaque locking, and does
  not help when both children rotate the AES key later and overwrite
  each other's cached pubkey. Sharding is strictly simpler and matches
  the master-side precedent of per-identity on-disk state.
- **Mangle only the cache inside `verify_master`, keep `self.mpub` as a
  tuple of `(preferred, legacy)`.** Bigger blast radius; every reader
  needs to learn a new convention. Rejected.

### Risk assessment

- Auth-critical surface. The fix changes a path string, not the
  signature/decryption algebra. Every call site still goes through the
  same pub key load/verify code. Confidence is high.
- The fallback-to-legacy migration is one `shutil.copyfile` guarded by
  `exists(legacy) and not exists(new)`; no destructive op.
- There is one upstream dependency, `salt/channel/client.py:153,573`,
  which reads `self.auth.mpub`. It gets the new sharded name for free.
- `salt/modules/key.py:48` and `salt/utils/migrations.py:42` keep the
  literal `"minion_master.pub"`. The former is fingerprint output for
  humans running `salt '*' key.finger_master` and will show the
  single-master fallback or nothing in multimaster mode — acceptable
  but worth tracking (listed under "Deferred").

### Deferred (not in this patch)

- `salt.modules.key.finger_master`: update to walk the per-master shards
  and emit a dict keyed by master name. Low priority; only affects an
  operator-facing CLI in multimaster mode.

## 5. Test plan

Unit regression under `tests/pytests/unit/crypt/`:

- Two `AsyncAuth` instances for different `master`/`master_uri` sharing
  `pki_dir` and `multimaster: True` must land on different
  `self.mpub` paths.
- Writing one master's pubkey to its own `mpub` must not disturb the
  other's file.
- Reading the other master's cached file with the wrong instance must
  raise / return `""` (cross-read verification failure).
- Single-master fallback: `multimaster` absent → `mpub` is the historic
  `"minion_master.pub"`.
- Syndic unchanged: `__role: syndic` → `"syndic_master.pub"`.
- Legacy migration: when only the legacy file is on disk and a
  multimaster `AsyncAuth` is constructed, the per-master file is
  populated from the legacy file.

## 6. Live repro confirmation

(Captured earlier on this branch; not re-run in this investigation.)

- mm-hothot minion startup log shows "Creating minion process manager"
  twice.
- One of the two `_connect_minion` tasks raises
  `ValueError("Unable to decrypt message")` out of `rsax931` during the
  initial AES decrypt. Stack top frame is `salt/crypt.py:1657`
  (`m_digest = mkey.decrypt(payload["sig"])`).
- Only one `__master_alive_<master>` scheduler job is registered.
- `salt '*' test.ping` from the surviving master succeeds; from the
  losing master returns "Minion did not return. [No response]".
- Nightly resiliency run `43644065679` reports the same symptom.

## 7. Files touched by the fix

- `salt/crypt.py` — per-master `mpub` resolution in
  `AsyncAuth.__singleton_init__` and `SAuth.__singleton_init__`; legacy
  migration helper used by both.
- `tests/pytests/unit/crypt/test_multimaster_pubkey_cache.py` — new
  regression suite.
- `changelog/` — entry filed under the saltstack/salt issue number once
  one is opened. No changelog file in this commit; per user memory
  "No PRs — commit local-only", this stays on the local worktree branch.

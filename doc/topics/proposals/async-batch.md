# Proposal: Async Batch Mode

## Problem

Salt's `--batch` and `--async` flags are mutually exclusive. Batch mode
(`salt/cli/batch.py:Batch.run()`) is a synchronous generator that blocks the
CLI process for the entire run. If you have 10,000 minions and batch size 100,
the CLI must stay alive through all 100 iterations, polling for returns and
printing output. There is no way to fire off a batch job, disconnect, and check
on it later.

Issues: #25362, #58502

## Goals

1. `salt '*' test.ping --batch 10 --async` returns a JID and exits immediately.
2. The master drives batch progression autonomously — each minion return
   triggers the next sub-batch without any client connection.
3. `salt-run jobs.lookup_jid <jid>` shows accumulated results from all
   completed iterations.
4. The existing synchronous batch behavior is preserved and uses the same
   core logic, just with a different output adapter.
5. Timeouts and stalled batches are handled without depending on the 60s
   maintenance loop.

## Architecture

Three layers, from inside out:

```
 +-----------------+
 |   BatchState    |   Pure data. Serializable. No I/O.
 +-----------------+
         |
 +-----------------+
 | progress_batch  |   Core logic. Reads returns, updates state,
 +-----------------+   decides what to publish next.
         |
 +-----------------+
 | Output Adapters |   CLI (stdout), Event (fire salt/batch/*),
 +-----------------+   Silent (job cache only)
```

Three drivers call `progress_batch()`:

| Driver | Trigger | Purpose |
|--------|---------|---------|
| **Sync CLI** | poll loop in `Batch.run()` | Today's behavior, refactored |
| **BatchManager** | event bus + timer loop | Dedicated master process for async batch progression |
| **Maintenance** | 60s loop in `Maintenance.run()` | Safety net: restart recovery, orphan cleanup |

### Layer 1: BatchState

A plain data class (or dict) stored as `.batch.p` in the JID directory
alongside `.load.p` and `.minions.p`. Contains everything needed to decide
what happens next:

```python
{
    "all_minions": ["web1", "web2", ..., "web100"],
    "pending":     ["web51", "web52", ..., "web100"],
    "active":      {"web41": 1718000000.0, ...},   # minion_id -> dispatch_time
    "done":        {"web1": True, "web2": True, ...},  # minion_id -> success
    "failed":      {"web5": "Minion did not respond"},
    "batch_size":  10,
    "fun":         "test.ping",
    "arg":         [],
    "kwargs":      {},
    "tgt":         "*",
    "tgt_type":    "glob",
    "failhard":    False,
    "batch_wait":  0,
    "timeout":     60,
    "gather_job_timeout": 10,
    "last_progress": 1718000000.0,   # timestamp of last state change
    "created":     1718000000.0,
    "halted":      False,            # True if failhard triggered or all done
    "halted_reason": None,
    "ret":         "",               # return returner
    "eauth":       {},
}
```

Key properties:
- **Pure data** — no file handles, no sockets, no references to runtime objects.
- **Serializable** — `salt.payload.dump()`/`load()` round-trips cleanly.
- **Atomic updates** — always written via `salt.utils.atomicfile.atomic_open()`.
- **Idempotent reads** — any process can read it without locking; writes use
  atomic rename so readers never see partial data.

### Layer 2: progress_batch()

The core function. Takes a `BatchState` and a set of newly returned minion IDs,
returns an `Action` describing what to do next:

```python
def progress_batch(state, new_returns):
    """
    Advance the batch state machine.

    Args:
        state: Current BatchState dict (will be mutated)
        new_returns: dict of {minion_id: return_data} from just-completed minions

    Returns:
        Action namedtuple:
            publish: list of minion IDs to publish to next (may be empty)
            finished_minions: dict of {minion_id: return_data} just processed
            halted: bool — True if the batch is done or failhard triggered
            halted_reason: str or None
    """
```

Logic:
1. Move returned minions from `active` to `done` (or `failed`).
2. Check failhard — if any return has retcode > 0 and `failhard=True`, set
   `halted=True`.
3. Check timeouts — move minions that exceeded `timeout` from `active` to
   `failed`.
4. If not halted and `active` slots are available, pop from `pending` up to
   `batch_size - len(active)`, respecting `batch_wait`.
5. Update `last_progress` timestamp.
6. Return the action.

This function has **no I/O**. It does not read the job cache, publish to
minions, or write to disk. The caller is responsible for all of that. This
makes it trivially testable and safe to call from any context.

### Layer 3: Output Adapters

An adapter is called after `progress_batch()` returns, to report what happened:

```python
class CLIOutput:
    """Print to stdout — today's behavior."""
    def on_minion_return(self, minion_id, data, opts):
        salt.output.display_output(...)

    def on_batch_start(self, minion_ids):
        salt.utils.stringutils.print_cli(f"\nExecuting run on {sorted(minion_ids)}\n")

    def on_batch_done(self, state):
        pass  # CLI just exits naturally

    def on_minion_timeout(self, minion_id):
        salt.utils.stringutils.print_cli(f"Minion '{minion_id}' failed to respond")

class EventOutput:
    """Fire events on the master event bus — for async/BatchManager mode."""
    def on_minion_return(self, minion_id, data, opts):
        # Individual returns already fire via the normal return path.
        # Fire batch-progress events for monitoring:
        # salt/batch/<jid>/progress
        pass

    def on_batch_start(self, minion_ids):
        # salt/batch/<jid>/start  {minions: [...], iteration: N}
        pass

    def on_batch_done(self, state):
        # salt/batch/<jid>/done  {success: N, failed: N, total: N}
        pass

class SilentOutput:
    """No output — job cache only. For programmatic use."""
    def on_minion_return(self, *a, **kw): pass
    def on_batch_start(self, *a, **kw): pass
    def on_batch_done(self, *a, **kw): pass
```

## Driver Details

### Driver 1: Sync CLI (refactored `Batch.run()`)

This is today's behavior, restructured to use the shared core:

```
CLI starts
  -> gather_minions()
  -> create BatchState
  -> write .batch.p to JID dir
  -> loop:
       poll for returns (cmd_iter_no_block, same as today)
       call progress_batch(state, new_returns)
       if action.publish: publish next sub-batch via LocalClient
       adapter.on_minion_return() for each finished minion
       if action.halted: break
       write updated .batch.p
  -> adapter.on_batch_done()
```

The sync driver still uses `LocalClient` with `listen=True` to receive returns
via the event bus. The refactoring is primarily moving the state tracking and
decision logic out of `Batch.run()` and into `progress_batch()`.

**Important:** When the sync CLI is driving a batch, the BatchManager must not
also drive it. The `.batch.p` state includes a `driver` field (e.g.
`"driver": "cli"` vs `"driver": "master"`) so the BatchManager knows to ignore
batches that are being driven by a connected CLI. If the CLI dies mid-batch,
the BatchManager can adopt it after a staleness timeout (see Failure Modes).

### Driver 2: BatchManager (dedicated master process)

A new `salt.utils.process.SignalHandlingProcess` subclass, started by the
master's `ProcessManager` alongside the existing `Maintenance`, `Reactor`
engine, `ReqServer`, etc:

```
Master Process Tree
├── ReqServer (handles minion connections)
├── PubServer (publishes to minions)
├── Maintenance (key rotation, job cleanup, git pillar, etc.)
├── Reactor Engine (event pattern matching)
├── EventPublisher
└── BatchManager (NEW — drives async batch jobs)
```

**Process internals:**

```python
class BatchManager(salt.utils.process.SignalHandlingProcess):
    """
    Dedicated process for driving async batch jobs.

    Listens on the master event bus for minion returns belonging to
    active batch jobs. On each relevant return, advances the batch
    state machine and publishes the next sub-batch.
    """

    def __init__(self, opts, **kwargs):
        super().__init__(**kwargs)
        self.opts = opts

    def run(self):
        self.local = salt.client.get_local_client(
            self.opts["conf_file"], listen=False
        )
        self.event = salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=True
        )
        # In-memory index of active batch JIDs for fast filtering.
        # Populated from batch_active.p on startup, updated as
        # batches start/complete.
        self.active_batches = self._load_active_index()

        while True:
            # Block for events, with a timeout for periodic
            # housekeeping (timeout checks, batch_wait expiry).
            event = self.event.get_event(
                full=True,
                wait=5,  # seconds — tight enough for timeouts
            )

            if event is not None:
                self._handle_event(event)

            # Periodic: check for timed-out minions, expired
            # batch_wait windows, and newly registered batches.
            self._check_timeouts()
```

**Event handling:**

```python
def _handle_event(self, event):
    tag = event["tag"]
    data = event["data"]

    # Fast path: is this a minion return for an active batch?
    # Tag format: salt/job/<jid>/ret/<minion_id>
    if tag.startswith("salt/job/"):
        parts = tag.split("/")
        if len(parts) == 5 and parts[3] == "ret":
            jid = parts[2]
            minion_id = parts[4]
            if jid in self.active_batches:
                self._handle_batch_return(jid, minion_id, data)
                return

    # New batch registration:
    # salt/batch/<jid>/new — fired by CLI when starting async batch
    if tag.startswith("salt/batch/") and tag.endswith("/new"):
        jid = tag.split("/")[2]
        self.active_batches.add(jid)
```

**Why a dedicated process and not a hook in `AESFuncs._return()`:**

The reactor is a single process with a shared thread pool — a slow reaction
blocks other reactions. The same concern applies to hooking into
`AESFuncs._return()` directly: return processing is on the master's request
handling path, and any delay there (reading `.batch.p`, computing next batch,
publishing) would slow down return processing for ALL minions, not just batch
jobs.

A dedicated process:
- Has its own event loop — no contention with return processing or reactors.
- Can maintain in-memory state — the set of active batch JIDs lives in RAM,
  so filtering non-batch returns is a dict lookup, not a disk check.
- Has its own `LocalClient` — publishing next sub-batches doesn't share
  resources with the request server.
- Can run its own timer — `get_event(wait=5)` gives 5-second granularity
  for timeout checks, far better than the 60s maintenance loop.
- Is restartable — `ProcessManager` will restart it if it crashes, and it
  rebuilds state from `.batch.p` files on disk.

**In-memory state vs disk:**

The BatchManager keeps a lightweight in-memory index of active batch JIDs.
The full `BatchState` lives on disk (`.batch.p`) and is read only when a
relevant event arrives. This means:
- Non-batch returns are filtered with a set lookup (no disk I/O).
- Memory footprint is minimal (just a set of JID strings).
- Full state is authoritative on disk and survives process restarts.

### Driver 3: Maintenance Process (safety net)

The maintenance loop (`salt/master.py:Maintenance`) remains the fallback for
situations the BatchManager can't handle:

1. **BatchManager crash/restart** — `ProcessManager` restarts it, but there's
   a gap. Maintenance detects stale batches on its next loop and can advance
   them.

2. **Orphaned batches** — If a CLI-driven batch's client dies without cleaning
   up (e.g. kill -9), the `driver: "cli"` batch becomes stale. Maintenance
   detects this via `last_progress` staleness and either adopts it for the
   BatchManager or marks it failed.

3. **Cleanup** — Remove `.batch.p` and index entries for completed batches
   older than `keep_jobs`.

```python
def handle_batch_jobs(self):
    """Safety net: detect and recover stalled batch jobs."""
    for jid in load_active_index():
        state = read_batch_state(jid)
        if state is None:
            # Corrupt or missing — remove from index
            remove_from_index(jid)
            continue

        if state["halted"]:
            # Already done, just clean up index
            remove_from_index(jid)
            continue

        stale_threshold = (
            state["timeout"]
            + state["gather_job_timeout"]
            + 30  # buffer
        )
        if time.time() - state["last_progress"] > stale_threshold:
            log.warning("Batch job %s appears stalled, recovering", jid)
            # Fire event to notify BatchManager to adopt it,
            # or directly advance if BatchManager is down
            self.event.fire_event(
                {"jid": jid}, "salt/batch/{}/recover".format(jid)
            )
```

The maintenance process does NOT own the fast path. It only acts when something
has gone wrong. Under normal operation, it finds nothing to do.

## Async CLI Flow

```
$ salt '*' test.ping --batch 10 --async
JID: 20240610120000000000

$ salt-run jobs.lookup_jid 20240610120000000000
web1: True
web2: True
...
(returns accumulated so far)

$ salt-run batch.status 20240610120000000000
Batch job 20240610120000000000:
  Function: test.ping
  Total minions: 100
  Completed: 47
  Active: 10
  Pending: 43
  Failed: 0
```

The `batch.status` runner is new — it reads `.batch.p` and formats it. The
`jobs.lookup_jid` runner already works because individual minion returns are
stored in the normal job cache under the shared JID.

### What the CLI does in async mode

```python
# In salt/cli/salt.py, when --batch and --async are both set:

batch_jid = salt.utils.jid.gen_jid(opts)
minions = gather_minions()  # ping check
state = create_batch_state(opts, minions, batch_jid, driver="master")

# Write batch state to job cache
write_batch_state(batch_jid, state)

# Publish first sub-batch
first_batch = state["pending"][:state["batch_size"]]
local.pub(first_batch, fun, arg, jid=batch_jid, tgt_type="list", ...)

# Write .load.p and .minions.p for the first sub-batch
save_load(batch_jid, ...)
save_minions(batch_jid, first_batch)

# Update state: move first_batch from pending to active
update_batch_state(state, first_batch)
write_batch_state(batch_jid, state)

# Notify BatchManager
event.fire_event({"jid": batch_jid}, f"salt/batch/{batch_jid}/new")

# Print JID and exit
print(f"JID: {batch_jid}")
sys.exit(0)
```

After this, the CLI is gone. The BatchManager owns progression, with
Maintenance as the safety net.

## File Layout in Job Cache

```
<cachedir>/jobs/<jid_hash>/<jid>/
    jid              # JID string (existing)
    .load.p          # Job metadata (existing)
    .minions.p       # All targeted minions, merged (existing, from single-JID work)
    .batch.p         # NEW — BatchState, atomically updated
    web1/
        return.p     # Minion return (existing)
    web2/
        return.p
    ...

<cachedir>/batch_active.p   # NEW — list of active batch JIDs
```

## New Code Locations

| File | What |
|------|------|
| `salt/utils/batch_state.py` | `BatchState` creation, `progress_batch()`, serialization helpers |
| `salt/cli/batch.py` | Refactored `Batch.run()` using `progress_batch()` + CLI adapter |
| `salt/master.py` | `BatchManager` process class, maintenance safety-net hook |
| `salt/runners/batch.py` | New runner: `batch.status`, `batch.list_active`, `batch.stop` |
| `salt/utils/batch_output.py` | Output adapter classes (CLI, Event, Silent) |

## Concurrency and Safety

**Single writer for async batches:** The BatchManager is the sole process
driving async batch state transitions. Since it's a single process with a
sequential event loop, there are no concurrent-write races for a given batch
JID. Two returns for the same batch are processed sequentially by the event
loop.

**CLI-driven batches:** The sync CLI is the sole writer for its own batch.
The `driver: "cli"` field in `.batch.p` tells the BatchManager to ignore it.

**Maintenance:** Only writes to `.batch.p` as a recovery action when the
normal driver (CLI or BatchManager) has gone stale. The staleness threshold
ensures it doesn't race with a live driver.

**Atomic state updates:** `.batch.p` is always written via
`salt.utils.atomicfile.atomic_open()` (write to temp, rename). Readers never
see partial data.

**Idempotent progression:** If a minion ID is already in `done`, re-processing
it is a no-op. This makes the system safe against duplicate return events.

## Failure Modes

| Failure | Handled by |
|---------|-----------|
| Minion doesn't return within timeout | BatchManager's periodic `_check_timeouts()` (every 5s) |
| Master restarts mid-batch | BatchManager rebuilds in-memory index from `batch_active.p` and `.batch.p` files on startup |
| BatchManager crashes | `ProcessManager` restarts it; Maintenance detects stale batches as fallback |
| All minions in a sub-batch timeout | BatchManager's timer loop catches it (no event needed) |
| `failhard` triggered | `progress_batch()` sets `halted=True`. No more sub-batches dispatched |
| CLI dies mid-batch (sync mode) | `driver: "cli"` batch goes stale. Maintenance fires recovery event. BatchManager adopts it |
| Corrupt `.batch.p` | Treated as halted. Maintenance removes from active index |
| Duplicate return events | `progress_batch()` is idempotent — minion already in `done` is a no-op |

## Migration and Compatibility

- Synchronous `--batch` (without `--async`) continues to work exactly as today,
  just refactored to use `progress_batch()` internally.
- `--async --batch` is a new combination that currently does nothing useful
  (batch silently wins). After this change, it works.
- The BatchManager process is new. On older masters it doesn't exist — no
  backward compatibility concern. The process is only active when there are
  batch jobs to manage; otherwise it sits idle on `get_event()`.
- The `.batch.p` file is new. Old masters don't write it, so there's no
  backward compatibility concern. If a user downgrades, the file is simply
  ignored.
- The `batch_active.p` index file is new. If it's missing or corrupt,
  BatchManager and Maintenance rebuild it by scanning the job cache.
- No changes to the minion side. No wire protocol changes.

## Implementation Sequence

1. `salt/utils/batch_state.py` — `BatchState` data structure and
   `progress_batch()` with comprehensive unit tests.
2. Refactor `salt/cli/batch.py` — make `Batch.run()` use `progress_batch()`.
   All existing batch tests must pass.
3. Output adapters — `CLIOutput`, `EventOutput`, `SilentOutput`.
4. `BatchManager` process — event loop, return handling, timeout checking.
5. Wire `BatchManager` into master process tree (`salt/master.py`).
6. Maintenance safety-net hook — stale batch detection and recovery.
7. Async CLI wiring — handle `--batch + --async` in `salt/cli/salt.py`.
8. `salt/runners/batch.py` — status/list/stop runners.
9. Integration tests.

Each step is independently mergeable. Steps 1-3 deliver the refactoring with
no behavior change. Steps 4-6 add the server-side infrastructure. Step 7
wires up the async CLI. Step 8 adds observability.

## Open Questions

1. **batch_wait in async mode** — In sync mode, `batch_wait` adds a delay
   between sub-batches. In async mode, the BatchManager can track this as a
   timestamp in BatchState. `progress_batch()` returns an empty `publish`
   list if `batch_wait` hasn't elapsed, and the next event (or timer tick)
   re-checks. The BatchManager's `get_event(wait=5)` timeout ensures
   `batch_wait` is honored within ~5s granularity.

2. **Stopping a running async batch** — `salt-run batch.stop <jid>` could set
   `halted=True` in `.batch.p` and fire a `salt/batch/<jid>/stop` event. The
   BatchManager sees the event, removes the JID from its active set, and stops
   dispatching. Is this sufficient, or do we need to also signal active minions
   to stop?

3. **Event tags** — What schema for `salt/batch/<jid>/*` events? Suggestions:
   - `salt/batch/<jid>/new` — batch job registered with BatchManager
   - `salt/batch/<jid>/start` — batch job created (first sub-batch published)
   - `salt/batch/<jid>/iter/<n>` — sub-batch N dispatched
   - `salt/batch/<jid>/progress` — periodic summary
   - `salt/batch/<jid>/done` — all minions completed or halted
   - `salt/batch/<jid>/stop` — batch manually stopped
   - `salt/batch/<jid>/recover` — maintenance detected stale batch

4. **Permissions/eauth** — The BatchManager publishes on behalf of the
   original user. Should BatchState store the eauth token, or should internal
   master-to-minion publishes bypass eauth (as `masterapi.minion_pub()` does
   today)?

5. **BatchManager lifecycle** — Always starts with the master, idles on
   `get_event()` when no batches are active. Consistent with how Maintenance
   and Reactor are managed.

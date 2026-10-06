"""
Job-cache returner backed by ``salt.cache.Cache``.

A drop-in replacement for the default ``local_cache`` returner that
routes every read and write through the :class:`salt.cache.Cache`
abstraction.  This unlocks two operational capabilities the default
returner does not provide:

* **Pluggable storage.**  Whichever ``cache:`` driver the operator
  configures (``localfs``, ``mmap_cache``, ``redis``, …) is what
  backs the job cache.  ``master_job_cache: salt_cache`` plus
  ``cache: mmap_cache`` gives an mmap-backed job cache.

* **Multi-ring sharding.**  Because every entry flows through one
  ``salt.cache.Cache`` instance, the cluster's
  :func:`salt.cluster.ring_membership.owns_for` gate can shard job
  state across ring members, and the
  :func:`salt.runners.cluster.shed_unowned` /
  :func:`salt.runners.cluster.collect_from_peers` runners can
  enumerate and move data.

Bank layout
-----------

Each JID's state is spread across a small set of banks so per-JID
operations are atomic and ring ownership maps cleanly to a single
key per JID at the routing layer:

* ``jobs/loads`` -- key=jid -> pub load dict
* ``jobs/minions`` -- key=jid -> sorted list of minion ids
* ``jobs/returns/<jid>`` -- key=minion_id -> ``{return, retcode, success, out}``
* ``jobs/endtimes`` -- key=jid -> epoch seconds (only when
  ``job_cache_store_endtime`` is set)
* ``jobs/nocache`` -- key=jid -> True (job-was-fired-with-nocache marker)

The ``jobs/<jid>`` granularity is what the ring sites consult: the
gate at ``salt/master.py`` calls
``ring_membership.owns_for(opts, "jobs", jid)`` and only persists
when this master owns the JID.

Compatibility
-------------

API-compatible with ``local_cache`` for every function ``Salt`` calls
through the returner interface (``prep_jid``, ``returner``,
``save_load``, ``save_minions``, ``get_load``, ``get_jid``,
``get_jids``, ``get_jids_filter``, ``clean_old_jobs``,
``update_endtime``, ``get_endtime``).  The on-disk layout differs
from ``local_cache`` — operators migrating need to either drain
existing jobs or run the migration runners on the old data.

Configuration
-------------

.. code-block:: yaml

    master_job_cache: salt_cache
    cache: mmap_cache         # or localfs, redis_cache, ...

When ``mmap_cache`` is used, ``mmap_cache_max_segment_bytes`` /
``mmap_cache_dirs`` apply as usual.
"""

import logging
import time

import salt.cache
import salt.exceptions
import salt.utils.jid
import salt.utils.job
import salt.utils.minions

log = logging.getLogger(__name__)


# Bank names — single source of truth so a future refactor can move
# them without grepping the whole file.
_BANK_LOADS = "jobs/loads"
_BANK_MINIONS = "jobs/minions"
_BANK_RETURNS_FMT = "jobs/returns/{jid}"
_BANK_ENDTIMES = "jobs/endtimes"
_BANK_NOCACHE = "jobs/nocache"


def _cache():
    """
    Build a :class:`salt.cache.Cache` from ``__opts__``.

    The driver is whatever the operator set in ``cache:`` (default
    ``localfs``).  Returners get a fresh ``__opts__`` per call from
    the loader, so a per-call construction is the simplest correct
    shape — caching the instance would risk a stale driver if opts
    were reloaded mid-process.
    """
    return salt.cache.Cache(__opts__)


# ---------------------------------------------------------------------------
# Lifecycle hooks called by the master
# ---------------------------------------------------------------------------


def prep_jid(nocache=False, passed_jid=None, recurse_count=0):
    """
    Return a job id and record any pre-flight state for it.

    Mirrors ``local_cache.prep_jid``:

    * If *passed_jid* is supplied (e.g. by ``salt-call --jid …`` or a
      syndic), use it.  Otherwise generate one via
      :func:`salt.utils.jid.gen_jid`.
    * On collision (an existing ``jobs/loads`` key with the same id)
      generate a new one, up to 5 retries.  Operators who hit the
      retry cap have a deeper clock-skew problem the returner
      shouldn't paper over.
    * When *nocache* is set, write a marker so :func:`returner`
      knows to short-circuit subsequent minion returns.
    """
    if recurse_count >= 5:
        raise salt.exceptions.SaltCacheError(
            f"prep_jid could not store a jid after {recurse_count} tries."
        )
    jid = passed_jid if passed_jid else salt.utils.jid.gen_jid(__opts__)
    cache = _cache()
    if not passed_jid and cache.contains(_BANK_LOADS, jid):
        # Collision — retry with a fresh jid.
        return prep_jid(
            nocache=nocache, passed_jid=None, recurse_count=recurse_count + 1
        )
    if nocache:
        cache.store(_BANK_NOCACHE, jid, True)
    return jid


def returner(load):
    """
    Persist one minion return for a JID.

    Idempotency: a second return from the same minion for the same
    jid is treated as a replay attempt and dropped (mirrors
    ``local_cache``'s ``EEXIST`` branch).  Returning ``False`` lets
    the master's reactor flag the event.
    """
    if load["jid"] == "req":
        load["jid"] = prep_jid(nocache=load.get("nocache", False))

    cache = _cache()
    jid = load["jid"]

    if cache.contains(_BANK_NOCACHE, jid):
        # Job was fired with nocache=True — drop the return silently.
        return

    returns_bank = _BANK_RETURNS_FMT.format(jid=jid)
    if cache.contains(returns_bank, load["id"]):
        log.error(
            "An extra return was detected from minion %s, please verify "
            "the minion, this could be a replay attack",
            load["id"],
        )
        return False

    record = {key: load[key] for key in ("return", "retcode", "success") if key in load}
    if "out" in load:
        record["out"] = load["out"]
    cache.store(returns_bank, load["id"], record)
    return None


def save_load(jid, clear_load, minions=None, recurse_count=0):
    """
    Persist the pub load (``tgt``, ``fun``, ``arg``, …) for a JID.

    If the load carries a ``tgt`` we compute the matched minion set
    here (unless the caller supplied one) and pass it to
    :func:`save_minions`.  The minion set is what
    ``get_load()`` later exposes as ``Minions`` to the UI.
    """
    if recurse_count >= 5:
        raise salt.exceptions.SaltCacheError(
            f"save_load could not write job load after {recurse_count} retries."
        )
    cache = _cache()
    try:
        cache.store(_BANK_LOADS, jid, clear_load)
    except salt.exceptions.SaltCacheError as exc:
        # localfs occasionally races on the dir-create step; mirror
        # local_cache's tiny retry rather than failing the publish.
        log.warning("Could not write job invocation cache entry: %s", exc)
        time.sleep(0.1)
        return save_load(
            jid=jid, clear_load=clear_load, recurse_count=recurse_count + 1
        )

    if "tgt" in clear_load and clear_load["tgt"]:
        if minions is None:
            ckminions = salt.utils.minions.CkMinions(__opts__)
            _res = ckminions.check_minions(
                clear_load["tgt"], clear_load.get("tgt_type", "glob")
            )
            minions = _res["minions"]
        save_minions(jid, minions)


def save_minions(jid, minions, syndic_id=None):
    """
    Store the list of matched minions for a JID.

    Merge with any previously-saved list so syndic-master appends
    don't clobber the main-master record (mirrors
    ``local_cache.save_minions``).  ``syndic_id`` is accepted for
    API compatibility but folded into the same merged list; the
    distinction is preserved on-disk in ``local_cache`` only because
    its file naming scheme uses it for routing.
    """
    minions = list(minions or [])
    cache = _cache()
    existing = cache.fetch(_BANK_MINIONS, jid) or []
    merged = sorted(set(existing) | set(minions))
    cache.store(_BANK_MINIONS, jid, merged)


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------


def get_load(jid):
    """
    Return the pub load for *jid*, plus a sorted ``Minions`` list if
    the matched set was recorded by :func:`save_minions`.
    """
    cache = _cache()
    load = cache.fetch(_BANK_LOADS, jid)
    if not load:
        return {}
    minions = cache.fetch(_BANK_MINIONS, jid)
    if minions:
        load["Minions"] = sorted(minions)
    return load


def get_jid(jid):
    """
    Return ``{minion_id: return_dict}`` for every return recorded
    against *jid*.

    Each return is a dict with at least ``return``; ``retcode``,
    ``success``, and ``out`` are populated when the minion reported
    them (same shape as ``local_cache``).
    """
    cache = _cache()
    returns_bank = _BANK_RETURNS_FMT.format(jid=jid)
    try:
        raw = cache.list_all(returns_bank, include_data=True)
    except (AttributeError, salt.exceptions.SaltCacheError):
        # Fallback for drivers that don't implement list_all (or for
        # a JID that has no returns yet).
        raw = {}
        for minion_id in cache.list(returns_bank):
            record = cache.fetch(returns_bank, minion_id)
            if record is not None:
                raw[minion_id] = record
    ret = {}
    for minion_id, record in (raw or {}).items():
        if not isinstance(record, dict) or "return" not in record:
            # Backwards-compat: ``local_cache`` v1 stored just the
            # return value at this key.  Wrap into the new shape so
            # consumers get a consistent dict.
            record = {"return": record}
        ret[minion_id] = record
    return ret


def get_jids():
    """
    Return ``{jid: jid_info}`` for every load on disk.

    ``jid_info`` is what :func:`salt.utils.jid.format_jid_instance`
    produces — used by the runner / API surfaces (``salt-run
    jobs.list_jobs`` etc.).  When ``job_cache_store_endtime`` is on,
    the matching ``EndTime`` is folded in.
    """
    cache = _cache()
    ret = {}
    for jid in cache.list(_BANK_LOADS):
        load = cache.fetch(_BANK_LOADS, jid)
        if not load:
            continue
        info = salt.utils.jid.format_jid_instance(jid, load)
        if __opts__.get("job_cache_store_endtime"):
            endtime = get_endtime(jid)
            if endtime:
                info["EndTime"] = endtime
        ret[jid] = info
    return ret


def get_jids_filter(count, filter_find_job=True):
    """
    Return the *count* most-recent JIDs as ``jid_info_ext`` dicts,
    optionally filtering out ``saltutil.find_job`` traffic.

    JIDs sort lexicographically by their timestamp prefix so the
    most-recent is the last in sorted order.  We accumulate into a
    bounded list to stay O(N log count) rather than O(N log N).
    """
    cache = _cache()
    keys = []
    ret = []
    import bisect  # pylint: disable=import-outside-toplevel

    for jid in cache.list(_BANK_LOADS):
        load = cache.fetch(_BANK_LOADS, jid)
        if not load:
            continue
        job = salt.utils.jid.format_jid_instance_ext(jid, load)
        if filter_find_job and job.get("Function") == "saltutil.find_job":
            continue
        i = bisect.bisect(keys, jid)
        if len(keys) == count and i == 0:
            continue
        keys.insert(i, jid)
        ret.insert(i, job)
        if len(keys) > count:
            del keys[0]
            del ret[0]
    return ret


# ---------------------------------------------------------------------------
# Endtime helpers — populated only when ``job_cache_store_endtime`` is set
# ---------------------------------------------------------------------------


def update_endtime(jid, the_time):
    """Record (or overwrite) the end-time for *jid*."""
    _cache().store(_BANK_ENDTIMES, jid, the_time)


def get_endtime(jid):
    """Return the recorded end-time for *jid*, or ``None``."""
    return _cache().fetch(_BANK_ENDTIMES, jid) or None


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------


def clean_old_jobs():
    """
    Drop loads (and all their associated banks) older than
    ``keep_jobs_seconds`` opt.

    Uses :meth:`salt.cache.Cache.updated` to age each load; falls
    back to "keep" when the driver can't report a timestamp (some
    drivers don't implement ``updated``).  Mirrors
    ``local_cache.clean_old_jobs`` semantically; the loop is far
    simpler because we don't have to walk a two-level directory
    hierarchy.
    """
    keep_jobs_seconds = salt.utils.job.get_keep_jobs_seconds(__opts__)
    if keep_jobs_seconds == 0:
        return
    cache = _cache()
    now = time.time()
    for jid in cache.list(_BANK_LOADS):
        try:
            updated = cache.updated(_BANK_LOADS, jid)
        except (AttributeError, salt.exceptions.SaltCacheError):
            # Driver can't tell us when this was written — leave the
            # entry alone rather than risk dropping a fresh job.
            continue
        if updated is None:
            continue
        if now - updated <= keep_jobs_seconds:
            continue
        _drop_jid(cache, jid)


def _drop_jid(cache, jid):
    """Remove every per-JID entry across all banks.  Best-effort."""
    cache.flush(_BANK_LOADS, jid)
    cache.flush(_BANK_MINIONS, jid)
    cache.flush(_BANK_ENDTIMES, jid)
    cache.flush(_BANK_NOCACHE, jid)
    # The per-jid returns bank is a whole-bank flush so every minion
    # return for the jid goes in one call.
    try:
        cache.flush(_BANK_RETURNS_FMT.format(jid=jid))
    except salt.exceptions.SaltCacheError:
        # No bank for a jid that never received a return is fine.
        pass

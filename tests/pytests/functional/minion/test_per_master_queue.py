"""
Functional regression tests for the per-master queue split.

These exercise the in-process behavior of ``salt.minion.Minion`` when two
instances share a cachedir but point at different masters — the layout the
``MinionManager`` produces in a hot/hot multimaster configuration.
"""

import copy
import os
import time

import tornado.ioloop

import salt.minion
import salt.utils.files
import salt.utils.state


def _make_opts(minion_opts, master, cachedir):
    opts = copy.deepcopy(minion_opts)
    opts["master"] = master
    opts["cachedir"] = str(cachedir)
    return opts


def _make_minion(opts):
    """
    Construct a Minion in-process without going through the connection flow.
    The constructor runs the stale-lock cleanup, which is what we want to
    exercise here.
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(opts, jid_queue=[], io_loop=io_loop)
    return minion


def test_two_minions_share_cachedir_independent_locks(minion_opts, tmp_path):
    """
    Regression for FileNotFoundError on job_queue.lock in hot/hot multimaster.

    Two Minion instances pointing at the same cachedir but different masters
    must resolve to disjoint queue lock paths, and one Minion's stale-lock
    cleanup at __init__ must not touch the other Minion's live lock file.
    """
    cachedir = tmp_path / "cache"
    cachedir.mkdir()

    opts_a = _make_opts(minion_opts, "master-a", cachedir)
    opts_b = _make_opts(minion_opts, "master-b", cachedir)

    lock_a = salt.utils.state.queue_lock_path(opts_a)
    lock_b = salt.utils.state.queue_lock_path(opts_b)
    assert lock_a != lock_b
    assert os.path.dirname(lock_a) != os.path.dirname(lock_b)

    # Bring Minion A up and place a sentinel where its lock would live.
    minion_a = _make_minion(opts_a)
    try:
        os.makedirs(os.path.dirname(lock_a), exist_ok=True)
        with salt.utils.files.fopen(lock_a, "w") as fp_:
            fp_.write("held by minion_a")
        assert os.path.isfile(lock_a)

        # Constructing Minion B must NOT remove minion_a's live lock.
        # Pre-split this would call os.remove on the shared lock path.
        minion_b = _make_minion(opts_b)
        try:
            assert os.path.isfile(lock_a), (
                "Minion-B's __init__ stale-lock cleanup deleted Minion-A's "
                "live lock file — the original FileNotFoundError race."
            )
        finally:
            minion_b.destroy()
    finally:
        minion_a.destroy()


def test_queue_job_writes_to_per_master_dir(minion_opts, tmp_path):
    """
    _queue_job writes the queued payload under the per-master job_queue dir,
    never the legacy shared cachedir/job_queue path.
    """
    cachedir = tmp_path / "cache"
    cachedir.mkdir()

    opts = _make_opts(minion_opts, "master-a", cachedir)
    minion = _make_minion(opts)
    try:
        jid = str(int(time.time() * 1000000))
        data = {"fun": "test.ping", "jid": jid, "arg": [], "tgt": "*"}
        minion._queue_job(data)
    finally:
        minion.destroy()

    expected_dir = salt.utils.state.job_queue_dir(opts)
    legacy_dir = os.path.join(str(cachedir), "job_queue")

    assert os.path.isdir(expected_dir), expected_dir
    queued = [f for f in os.listdir(expected_dir) if f.startswith("queued_")]
    assert queued, f"_queue_job did not write under {expected_dir}"
    assert not os.path.exists(legacy_dir), (
        f"_queue_job wrote to the legacy shared path {legacy_dir} instead of "
        f"the per-master path {expected_dir}"
    )


def test_two_minions_queue_jobs_isolated(minion_opts, tmp_path):
    """
    Each Minion's _queue_job lands in its own per-master directory; the
    drained file from one is invisible to the other Minion's queue dir.
    """
    cachedir = tmp_path / "cache"
    cachedir.mkdir()

    opts_a = _make_opts(minion_opts, "master-a", cachedir)
    opts_b = _make_opts(minion_opts, "master-b", cachedir)

    minion_a = _make_minion(opts_a)
    minion_b = _make_minion(opts_b)
    try:
        minion_a._queue_job({"fun": "test.ping", "jid": "100", "arg": [], "tgt": "*"})
        minion_b._queue_job({"fun": "test.ping", "jid": "200", "arg": [], "tgt": "*"})
    finally:
        minion_a.destroy()
        minion_b.destroy()

    files_a = os.listdir(salt.utils.state.job_queue_dir(opts_a))
    files_b = os.listdir(salt.utils.state.job_queue_dir(opts_b))
    # Match on the trailing "_<jid>.p" suffix only. Substring-matching the
    # whole filename is unsafe because the microsecond timestamp embedded in
    # the prefix (queued_<ts>_<jid>.p) routinely contains digit sequences
    # like "100" or "200".
    assert any(fn.endswith("_100.p") for fn in files_a)
    assert not any(fn.endswith("_200.p") for fn in files_a)
    assert any(fn.endswith("_200.p") for fn in files_b)
    assert not any(fn.endswith("_100.p") for fn in files_b)

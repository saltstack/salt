"""
Unit tests for the per-master queue path helpers in salt.utils.state.
"""

import os

import pytest

import salt.utils.state


@pytest.mark.parametrize(
    "master, expected",
    [
        ("master-a", "master-a"),
        ("127.0.0.1:4506", "127.0.0.1_4506"),
        ("[fe80::1]:4506", "_fe80__1__4506"),
        ("plain-host.example.com", "plain-host.example.com"),
        ("weird/chars\\here", "weird_chars_here"),
        ("", "_default"),
        (None, "_default"),
        (["m1", "m2"], "m1_m2"),
        (("m1", "m2"), "m1_m2"),
    ],
)
def test_sanitize_master_id(master, expected):
    assert salt.utils.state._sanitize_master_id(master) == expected


def test_queue_paths_use_per_master_namespace(tmp_path):
    opts = {"cachedir": str(tmp_path), "master": "master-a"}
    base = salt.utils.state.queue_base_dir(opts)
    assert base == os.path.join(str(tmp_path), "queues", "master-a")
    assert salt.utils.state.queue_lock_path(opts) == os.path.join(base, "queue.lock")
    assert salt.utils.state.job_queue_dir(opts) == os.path.join(base, "job_queue")
    assert salt.utils.state.state_queue_dir(opts) == os.path.join(base, "state_queue")


def test_queue_paths_disjoint_per_master(tmp_path):
    """
    Two opts dicts pointing at the same cachedir but different masters must
    resolve to completely disjoint queue trees — this is the property the
    per-master split relies on to keep the two Minions out of each other's way.
    """
    opts_a = {"cachedir": str(tmp_path), "master": "master-a"}
    opts_b = {"cachedir": str(tmp_path), "master": "master-b"}

    paths_a = {
        salt.utils.state.queue_base_dir(opts_a),
        salt.utils.state.queue_lock_path(opts_a),
        salt.utils.state.job_queue_dir(opts_a),
        salt.utils.state.state_queue_dir(opts_a),
    }
    paths_b = {
        salt.utils.state.queue_base_dir(opts_b),
        salt.utils.state.queue_lock_path(opts_b),
        salt.utils.state.job_queue_dir(opts_b),
        salt.utils.state.state_queue_dir(opts_b),
    }
    assert paths_a.isdisjoint(paths_b)


def test_queue_lock_path_makedirs_parent(tmp_path):
    """
    acquire_queue_lock pre-creates the per-master queue base dir; verify the
    directory exists after the call so the underlying wait_lock has a place
    to land its lock file.
    """
    opts = {"cachedir": str(tmp_path), "master": "master-a"}
    # Just invoke the helper that builds + ensures the dir.
    lock_path = salt.utils.state.queue_lock_path(opts)
    # acquire_queue_lock side-effect: makedirs(parent).
    salt.utils.state.acquire_queue_lock(opts)
    assert os.path.isdir(os.path.dirname(lock_path))

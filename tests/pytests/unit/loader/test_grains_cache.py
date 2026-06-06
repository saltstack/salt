"""
Regression tests for _load_cached_grains exception handling.

Validates that a corrupted grains cache file does not crash the loader
(or, by extension, the master Maintenance process) but is treated the
same as a missing cache: return None so callers regenerate grains.
"""

import msgpack
import pytest

import salt.config
import salt.loader
import salt.utils.files


@pytest.fixture
def minion_opts(tmp_path):
    """
    Minion options pointing at a temporary cachedir with grains_cache on.
    """
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["cachedir"] = str(tmp_path)
    opts["grains_cache"] = True
    # Cache must not be considered expired during the test.
    opts["grains_cache_expiration"] = 86400
    return opts


def test_load_cached_grains_handles_corrupted_cache_68725(minion_opts, tmp_path):
    """
    A grains cache file containing extra trailing bytes after a valid
    msgpack frame must not raise SaltDeserializationError out of
    _load_cached_grains; it must return None so callers refresh.

    See https://github.com/saltstack/salt/issues/68725 — the uncaught
    SaltDeserializationError crashes the master Maintenance worker via
    clean_old_jobs -> MasterMinion -> mminion_config -> salt.loader.grains.
    """
    cfn = str(tmp_path / "grains.cache.p")
    valid_payload = msgpack.packb({"os": "Linux"})
    with salt.utils.files.fopen(cfn, "wb") as fp:
        # Valid msgpack frame followed by trailing garbage -> msgpack.ExtraData
        fp.write(valid_payload + b"EXTRA-GARBAGE-BYTES")

    # Must not raise; corrupted cache should be treated like a missing one.
    assert salt.loader._load_cached_grains(minion_opts, cfn) is None

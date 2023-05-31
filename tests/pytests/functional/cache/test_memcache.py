import logging

import pytest

import salt.cache
from tests.pytests.functional.cache.helpers import run_common_cache_tests

log = logging.getLogger(__name__)


@pytest.fixture
def cache(minion_opts):
    opts = minion_opts.copy()
    opts["memcache_expire_seconds"] = 42
    cache = salt.cache.factory(opts)
    return cache


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)

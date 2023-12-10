import logging
import shutil

import pytest

import salt.cache
import salt.loader
from tests.pytests.functional.cache.helpers import run_common_cache_tests

log = logging.getLogger(__name__)


@pytest.fixture
def cache(minion_opts):
    opts = minion_opts.copy()
    opts["cache"] = "localfs"
    cache = salt.cache.factory(opts)
    try:
        yield cache
    finally:
        shutil.rmtree(opts["cachedir"], ignore_errors=True)


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)

"""
Unit tests for the salt.modules.zk_concurrency module
"""

import sys

import pytest

import salt.modules.zk_concurrency as zk_concurrency
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {zk_concurrency: {"__context__": {"semaphore_map": {}}}}


@pytest.fixture
def semaphore():
    sem = MagicMock()
    sem.is_acquired = True
    # kazoo is not needed: the connection and the semaphore are replaced
    with patch.object(zk_concurrency, "_get_zk_conn", MagicMock()), patch.object(
        zk_concurrency, "_Semaphore", MagicMock(return_value=sem), create=True
    ):
        yield sem


def test_lock_force_removes_the_limit_of_leases(semaphore):
    """
    ``force`` takes the lock whatever the number of open slots is, so the
    semaphore must be allowed any number of leases.
    """
    assert zk_concurrency.lock("/lock/path", force=True) is True
    assert semaphore.max_leases == sys.maxsize
    assert semaphore.assured_path is True
    semaphore.acquire.assert_called_once_with()


def test_lock_without_force_keeps_the_limit_of_leases(semaphore):
    semaphore.max_leases = 1
    assert zk_concurrency.lock("/lock/path") is True
    assert semaphore.max_leases == 1
    semaphore.acquire.assert_called_once_with()


def test_lock_with_timeout_passes_the_timeout(semaphore):
    assert zk_concurrency.lock("/lock/path", timeout=5) is True
    semaphore.acquire.assert_called_once_with(timeout=5)

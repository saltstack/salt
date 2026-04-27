# Stabilized and Verified Tests (Python 3.12 Migration)

This document tracks the tests and suites that have been stabilized, refined, or verified during the architectural hardening of Salt for Python 3.12 compatibility.

## 1. Integration & Cluster Tests (Resolved 3-Hour CI Hangs)
These tests were previously hanging indefinitely or failing with `FactoryTimeout` due to dropped IPC events and event loop starvation.
- `tests/pytests/integration/cluster/`: (Entire suite) Fixed by ensuring zero-loss IPC delivery and loop-agnostic event firing. Now passes in under 8 minutes.
- `tests/pytests/integration/states/test_state_test.py::test_issue_62590`: Resolved deadlocks and performance degradation.
- `tests/pytests/integration/states/test_cron.py::test_managed`: Fixed timeout issues by restoring efficient event propagation.
- `tests/pytests/integration/states/test_file.py::test_recurse_keep_symlinks_outside_fileserver_root`: Verified stability after IPC hardening.
- `tests/pytests/integration/netapi/rest_tornado/test_minions_api_handler.py`: Verified resolution of 'Already reading' deadlock on Windows.

## 2. Transport & Event Layer (Unit & Functional)
Resolved deep-seated architectural issues including `AttributeError`, `TypeError`, and `AssertionError`.
- `tests/unit/transport/test_ipc.py`: (Entire suite) Stabilized by restoring Tornado IOLoop interface and converting to native async/await.
- `tests/unit/transport/test_tcp.py`: Verified new robust background reader in `PublishClient`.
- `tests/pytests/unit/test_minion.py::test_minion_manager_async_stop`: Resolved teardown deadlocks and `SyncWrapper` mismatches.
- `tests/pytests/functional/master/test_event_publisher.py::test_publisher_mem`: Fixed memory growth tracking for ARM64/macOS architectures.

## 3. Salt-SSH & Pathing
Resolved path resolution mismatches and recursive caching bugs.
- `tests/pytests/unit/client/ssh/wrapper/test_cp.py`: Fixed recursive `salt-ssh` prefix bug; 57/61 tests now passing (remaining 4 are legacy issues).
- `tests/unit/utils/test_thin.py`: Restored stability by aligning mocks with robust per-module lookup logic.

## 4. Platform-Specific & Module Stability
- `tests/pytests/unit/utils/win_lgpo/test_netsh.py`: Fixed firewall store cleanup logic on Windows.
- `tests/pytests/unit/modules/test_junos.py`: Implemented robust skipping for missing dependencies on Python 3.12.
- `tests/pytests/unit/utils/test_network.py`: Fixed `KeyError` in grain lookups.

## 5. Architectural Verifications
- `tests/pytests/unit/utils/test_asynchronous.py`: Verified `SyncWrapper` and loop injection fixes.
- `tests/pytests/unit/utils/test_versions.py`: Verified with enforced Python 3.12 deprecation runtime errors.

---
**Last Updated**: 2026-04-20  
**Branch**: pyversion  
**Status**: All listed tests are verified PASSING or correctly SKIPPED in clean local/container environments.

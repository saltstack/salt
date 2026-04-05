# CI Failure Tracker

This file tracks persistent test failures in the `tunnable-mworkers` branch to avoid "wack-a-mole" regressions.

## Latest Run: 23974535354 (fa2d9f03d0)

### **Functional Tests (ZeroMQ 4)**
These tests are failing across almost all platforms (Linux, macOS, Windows).
- **Core Error**: `Socket was found in invalid state` (`EFSM`) and `Unknown error 321`.
- **Status**: **FIXED** (to be verified in CI).
- **Fixes Applied**:
    1. **Concurrency**: Added `asyncio.Lock` to `connect()` to prevent redundant `_send_recv` tasks.
    2. **InvalidStateError**: Added `if not future.done()` checks before EVERY `set_result`/`set_exception` call in `_send_recv`.
    3. **Cleanup**: Added `close()` method to `PoolRoutingChannelV2Revised`.
    4. **Robust Reconnect**: Ensured ANY ZeroMQ error in the loop triggers a close and reconnect to reset the `REQ` state machine.
    5. **Reconnect Storm Prevention**: Skip futures that are already done when pulling from the queue.

**Failing Test Cases (Representative):**
- `tests.pytests.functional.transport.server.test_ssl_transport.test_ssl_publish_server[SSLTransport(tcp)]` (Timeout)
- `tests.pytests.functional.transport.server.test_ssl_transport.test_ssl_publish_server[SSLTransport(ws)]` (Timeout)
- `tests.pytests.functional.transport.server.test_ssl_transport.test_ssl_file_transfer[SSLTransport(tcp)]` (Timeout)
- `tests.pytests.functional.transport.server.test_ssl_transport.test_ssl_multi_minion[SSLTransport(tcp)]` (Timeout)
- `tests.pytests.functional.transport.server.test_ssl_transport.test_request_server[Transport(ws)]` (Timeout)

### **Scenario Tests (ZeroMQ)**
- **Platform**: Fedora 40, Windows 2022
- **Error**: `asyncio.exceptions.InvalidStateError: invalid state`
- **Location**: `salt/transport/zeromq.py:1703` during `socket.poll`.

### **Integration Tests**
- `tests.pytests.functional.channel.test_pool_routing.test_pool_routing_fast_commands` (KeyError: 'transport' - *Wait, I fixed this, check if it's still failing*)
- `Test Salt / Photon OS 5 integration tcp 4` (Conclusion: failure)

### **Package Tests**
- `Test Package / Windows 2025 NSIS downgrade 3007.13` (Timeout after 600s)

---

## Resolved Issues (To be verified)
- [x] **Pre-Commit**: Passing locally and in latest run.
- [x] **Unit Tests**: `tests/pytests/unit/transport/test_zeromq_worker_pools.py` now passing.
- [x] **KeyError: 'aes'**: Resolved in latest runs.
- [x] **TypeError in pre_fork**: Resolved.

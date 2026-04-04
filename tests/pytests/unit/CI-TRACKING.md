# CI Test Tracking

Tests that must pass before merging. Run with:

```
source venv311/bin/activate
python -m pytest <test> -v
```

## Tests We Own (new files)

| Test file | What it covers |
|---|---|
| `tests/pytests/unit/utils/test_minions_resources.py` | Resource index, `check_minions` augmentation + merge-mode skip |
| `tests/pytests/unit/test_minion_resources.py` | `_prefix_resource_state_key`, `_MERGE_RESOURCE_FUNS`, merge block branches |
| `tests/pytests/unit/modules/test_sshresource_state.py` | `highstate()` empty-chunks return, `_exec_state_pkg` exception recovery |
| `tests/pytests/unit/matchers/test_resource_matchers.py` | `T@` / `M@` compound matching |

## Existing Tests We've Broken (fixed)

| Test | Root cause | Fix |
|---|---|---|
| `tests/pytests/unit/states/test_saltutil.py::test_saltutil_sync_states_should_match_saltutil_module` | `sync_resources` added to module but not state | Added `sync_resources()` to `salt/states/saltutil.py` |
| `tests/pytests/unit/client/test_netapi.py::test_run_log` | `netapi.py` changed `run()` to `asyncio.run()`, test used plain `Mock` | Changed mock to `AsyncMock` |
| `tests/integration/minion/test_executor.py::ExecutorTest::test_executor_with_multijob` | Multifunction job passes `fun` as a list; `list not in frozenset` raises `TypeError`, caught by broad except → empty minion list | Guard with `isinstance(fun, str)` before set membership check |

## Known CI Noise (not our fault)

| Failure | Reason |
|---|---|
| Package upgrade tests (`test_salt_systemd_*_preservation`) | 502 downloading `salt-install-guide` release from GitHub — transient infra |
| `test_tcp_client_invalid_cert_rejected` | Functional TCP SSL timeout — pre-existing flaky test |
| `test_state.py::test_event` | `RuntimeError: There is no current event loop` — pre-existing flaky |

## Quick Regression Run

```bash
source venv311/bin/activate
python -m pytest \
  tests/pytests/unit/utils/test_minions_resources.py \
  tests/pytests/unit/test_minion_resources.py \
  tests/pytests/unit/modules/test_sshresource_state.py \
  tests/pytests/unit/matchers/test_resource_matchers.py \
  tests/pytests/unit/states/test_saltutil.py::test_saltutil_sync_states_should_match_saltutil_module \
  tests/pytests/unit/client/test_netapi.py::test_run_log \
  -v
```

# Pytest port — shared contract for wave-1 agents

Every agent building wave-1 infrastructure MUST code against the
interfaces below.  Wave-2 scenario-porter agents will import these
without wrapping them.

## `tests/resiliency/durations.py`

Already written.  Defines `TIER_*_SEC`, `RECOVER_*_SEC`,
`PACING_*_SEC`, `RSS_LEAK_KB_PER_MIN`, `MASTER_FD_LEAK_PER_MIN`,
`MASTER_RSS_LEAK_BYTES_PER_SEC`, `PING_TIMEOUT_SEC`.  All env-overridable
via `RESILIENCY_<NAME>`.

## `tests/resiliency/lib/topology.py`

```python
from dataclasses import dataclass
from typing import Iterator, List

@dataclass(frozen=True)
class MinionSample:
    fds: int
    rss_kb: int

    def __sub__(self, other: "MinionSample") -> "MinionSample":
        return MinionSample(
            fds=self.fds - other.fds,
            rss_kb=self.rss_kb - other.rss_kb,
        )

@dataclass(frozen=True)
class TopologySpec:
    """Descriptor loaded from the TOPOLOGY name.  Pure data; no side effects."""
    name: str
    masters: List[str]            # container names
    primary_master: str
    minion_ids: List[str]         # salt minion ids
    minion_containers: List[str]  # docker container names
    choke_container: str
    choke_iface: str
    compose_files: List[str]      # absolute paths; order matters
    compose_project: str

    @property
    def master_count(self) -> int:
        return len(self.masters)

    @property
    def is_cluster(self) -> bool:
        return self.master_count > 1 and "haproxy" in self.choke_container

    @property
    def is_multimaster(self) -> bool:
        return self.name.startswith("multimaster-")


class Topology:
    """Live session-scoped handle around a running compose stack.

    Does NOT bring up or tear down compose itself -- that's the
    topology fixture's responsibility.  This class wraps the running
    stack for scenarios: sampling, assertion, and docker-shelling.
    """

    def __init__(self, spec: TopologySpec):
        self.spec = spec

    # Sampling
    def sample_minions(self) -> MinionSample: ...
    def sample_container(self, container: str) -> MinionSample: ...

    # Assertions
    def assert_reconnect(
        self,
        scenario: str,
        fault_sec: int,
        before: MinionSample,
        window_sec: int | None = None,  # default: RECOVER_STANDARD_SEC
        notes: str = "",
    ) -> None:
        """Assert every minion answers test.ping within `window_sec` AND
        RSS slope stays under RSS_LEAK_KB_PER_MIN.  On failure, call
        pytest.fail with structured details.  Always records one JSONL
        row via conftest's record_result hook.
        """

    # Lifecycle
    def wait_initial_auth(self, timeout: int = 300) -> None:
        """Pytest.fail if not every $MINION_IDS visible on $MASTERS within timeout."""

    # Docker shortcuts
    def exec(self, container: str, *cmd: str, check: bool = True) -> str: ...
    def kill_signal(self, container: str, sig: str) -> None: ...  # STOP/CONT/HUP/USR1/KILL/TERM
    def pause(self, container: str) -> None: ...
    def unpause(self, container: str) -> None: ...
    def stop(self, container: str, timeout_sec: int = 30) -> None: ...
    def start(self, container: str) -> None: ...
    def restart(self, container: str) -> None: ...
```

### `load_topology(name: str) -> TopologySpec`

Named topologies:
- `single` — rs-single-salt-master + 3 minions, prom:19090
- `cluster3` — c3-salt-master-{1,2,3} + 5 minions + c3-salt-haproxy, prom:19090
- `cluster5` — c5-salt-master-{1..5} + 5 minions, prom:19093
- `multimaster-failover` — mm-salt-master-{a,b} + mm-salt-minion-1 (master_type=failover), prom:19091
- `multimaster-hothot` — same containers, master_type=standard + list, prom:19091
- `syndic` — rs-syndic-mom + rs-syndic-sub + 2 minions, prom:19092

Container names, IDs, and compose file paths MUST match
`tests/resiliency/lib/common.sh::load_topology` exactly -- the pytest
suite reuses the existing bash compose stacks under
`tests/resiliency/compose/`.

## `tests/resiliency/lib/injectors.py`

Every fault injector is a context manager that applies on `__enter__`
and reverses on `__exit__` (including on exception):

```python
from contextlib import contextmanager

@contextmanager
def inject_netem(topology: Topology, netem_args: str) -> Iterator[None]:
    """tc qdisc replace dev $iface root netem $netem_args; yield; tc qdisc del."""

@contextmanager
def tcp_reset_from_minions(topology: Topology, dport: int = 44506) -> Iterator[None]:
    """iptables -I OUTPUT ... REJECT --reject-with tcp-reset on each minion; yield; -D."""

@contextmanager
def paused_container(topology: Topology, container: str) -> Iterator[None]:
    """docker pause <c>; yield; docker unpause <c>."""

@contextmanager
def sigstopped_container(topology: Topology, container: str) -> Iterator[None]:
    """docker kill -s STOP; yield; docker kill -s CONT."""

@contextmanager
def disconnected_from_network(topology: Topology, container: str) -> Iterator[None]:
    """docker network disconnect; yield; docker network connect with same aliases."""

@contextmanager
def remounted_readonly(topology: Topology, container: str, path: str) -> Iterator[None]: ...

@contextmanager
def dns_hosts_poisoned(topology: Topology, hostnames: list[str]) -> Iterator[None]: ...
```

All injectors MUST:
- Raise `pytest.skip(reason)` on setup error (missing tc / iptables / NET_ADMIN cap).
- Guarantee `__exit__` reverses the mutation even on exception.
- Log an entry marker and an exit marker via `logging.getLogger("resiliency.injector")`.

## `tests/resiliency/lib/metrics.py`

```python
def prometheus_slope(query: str, duration: str = "30m", url: str | None = None) -> float:
    """`deriv(query[duration])` scalar; 0.0 if unreachable or no series."""

def master_fd_slope(topology: Topology) -> float: ...
def master_rss_slope(topology: Topology) -> float: ...
```

## `tests/resiliency/conftest.py`

- `--topology=NAME` CLI flag (default: `single`); `--marathon` to enable marathon tests
- Session-scoped `topology` fixture: brings up compose, waits auth, yields `Topology`, tears down
- Function-scoped `workload` fixture: starts `workload.sh` in background pgroup, kills on teardown
- `record_result` hook: `pytest_runtest_makereport` → append one JSONL row to `$RESILIENCY_WORKDIR/results.jsonl`
- `@pytest.mark.topology("cluster3", "cluster5")` — skip the test if the current session topology isn't in the list
- `@pytest.mark.marathon` — skip unless `--marathon` was passed

## Where things live

```
tests/resiliency/
├── durations.py                  # tier constants (DONE)
├── CONTRACT.md                   # this file
├── conftest.py                   # fixtures + hooks (WAVE 1)
├── lib/
│   ├── __init__.py
│   ├── topology.py               # Topology + TopologySpec + load_topology (WAVE 1)
│   ├── injectors.py              # context managers for every fault class (WAVE 1)
│   └── metrics.py                # prometheus slope queries (WAVE 1)
├── test_baseline.py              # WAVE 2
├── test_master_restart.py        # WAVE 2
├── ...                           # one test_*.py per scenario (WAVE 2)
├── compose/                      # UNCHANGED — bash compose stacks stay
├── run_resiliency.sh             # WAVE 4: thin wrapper that invokes pytest
├── workload.sh                   # UNCHANGED — bash is right for this
├── lib/common.sh                 # WAVE 4: deleted when pytest port verified
└── scenarios/*.sh                # WAVE 4: deleted when pytest port verified
```

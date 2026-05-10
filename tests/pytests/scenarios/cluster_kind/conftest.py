"""
Fixtures that drive Salt cluster scenarios on a real Kubernetes cluster
running inside Docker (``kind``).

Why bother
----------
The ``tests/pytests/integration/cluster/`` and
``tests/pytests/scenarios/cluster/`` suites use loopback aliases —
masters bind to 127.0.0.1, 127.0.0.2, 127.0.0.3, etc.  That works for
the basic happy-path checks but doesn't exercise:

* real distinct IPs (rather than aliases on the same loopback);
* DNS-based peer addressing (most production deployments use FQDNs);
* network isolation between processes (every loopback master shares
  the host kernel, so ``iptables`` partition tests are impossible);
* the cluster bootstrap path on a non-``localhost`` interface, which
  is the path real operators take.

This fixture set spins up a single-node ``kind`` cluster inside Docker
and deploys 3 salt-master Pods on a headless Service.  Each Pod gets a
stable DNS name (``salt-master-0.salt-cluster.<ns>.svc.cluster.local``
and friends), pip-installs the consensus Salt source from a hostPath
mount, then runs ``salt-master``.  Tests interact with the cluster by
shelling ``kubectl exec`` into a chosen pod.

Requirements (skipped cleanly if any are missing)
-------------------------------------------------
* ``docker``, ``kind``, ``kubectl`` on ``$PATH``
* a reachable Docker daemon (the ``--privileged`` test container in
  :mod:`tools.container` already provides one)
* Linux host (kind runs on macOS too, but the salt-master Pods we
  deploy expect Linux semantics)
"""

import logging
import os
import pathlib
import shutil
import subprocess
import textwrap
import time
import uuid

import pytest
import yaml

log = logging.getLogger(__name__)

# Top of the consensus repo — used as the hostPath we mount into the
# kind node so Pods can pip install the in-tree Salt source.
SALT_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]

# Default base image for salt-master Pods.  Has Python, build deps, and
# Salt's runtime requirements pre-installed; we add the consensus source
# at Pod-startup time via ``pip install -e /salt``.
DEFAULT_SALT_IMAGE = "ghcr.io/saltstack/salt-ci-containers/testing:debian-12"

# Names of the three masters.  Predictable so tests can address them.
MASTER_NAMES = ("salt-master-0", "salt-master-1", "salt-master-2")

# Headless service name (subdomain) — combined with each Pod's
# ``hostname`` field, gives every master a stable DNS record.
CLUSTER_SUBDOMAIN = "salt-cluster"

# How long fixtures wait for k8s objects to settle.  Pulling the salt
# image + pip-installing consensus into three Pods runs ~3 min cold.
_DEFAULT_DEADLINE = 360


# ---------------------------------------------------------------------------
# Skip-if-deps-missing
# ---------------------------------------------------------------------------


def _have(binary):
    """
    True iff *binary* is on ``PATH`` *and* actually runs.

    ``shutil.which`` alone is not enough: some CI images (notably
    Photon OS 5 Arm64) ship a stub or a wrong-arch ``kind`` /
    ``kubectl`` / ``docker`` binary that ``which`` happily finds but
    that fails ``execve`` with ``FileNotFoundError``.  Invoking
    ``--version`` proves the binary is loadable on this arch.
    """
    if shutil.which(binary) is None:
        return False
    try:
        subprocess.run(
            [binary, "--version"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def _docker_reachable():
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not (
        _have("kind") and _have("kubectl") and _have("docker") and _docker_reachable()
    ),
    reason="kind / kubectl / docker daemon not available",
)


# ---------------------------------------------------------------------------
# Cluster lifecycle
# ---------------------------------------------------------------------------


class KindCluster:
    """
    Handle to a running ``kind`` cluster.

    Tests rarely use this directly; use :func:`kubectl` /
    :func:`salt_in_pod` instead.
    """

    def __init__(self, name, kubeconfig, namespace):
        self.name = name
        self.kubeconfig = kubeconfig
        self.namespace = namespace

    def kubectl(self, *args, check=True, capture=True, timeout=120, input=None):
        """
        Run ``kubectl`` against this cluster's kubeconfig.

        On non-zero exit with ``check=True``, raises ``RuntimeError``
        with both stdout and stderr (subprocess.CalledProcessError
        swallows stderr by default in some pytest output modes).
        """
        cmd = ["kubectl", "--kubeconfig", str(self.kubeconfig), *args]
        log.debug("kubectl %s", " ".join(args))
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=capture,
            timeout=timeout,
            text=True,
            input=input,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"kubectl {' '.join(args)} failed (rc={proc.returncode})\n"
                f"--- stdout ---\n{proc.stdout}\n"
                f"--- stderr ---\n{proc.stderr}"
            )
        return proc


@pytest.fixture(scope="module")
def kind_cluster(tmp_path_factory):
    """
    Create a single-node kind cluster with the consensus Salt repo
    bind-mounted into the node at ``/salt``.

    Module-scoped: spinning kind up + pulling the salt image is the
    expensive bit; we want to amortise across multiple tests.
    """
    name = f"salt-{uuid.uuid4().hex[:8]}"
    work_dir = pathlib.Path(tmp_path_factory.mktemp(f"kind-{name}"))
    kind_config = work_dir / "kind-config.yaml"
    kubeconfig = work_dir / "kubeconfig"

    kind_config.write_text(
        textwrap.dedent(
            f"""\
            kind: Cluster
            apiVersion: kind.x-k8s.io/v1alpha4
            nodes:
            - role: control-plane
              extraMounts:
              - hostPath: {SALT_REPO_ROOT}
                containerPath: /salt
                readOnly: true
            """
        )
    )

    log.info("Creating kind cluster %s", name)
    try:
        create_proc = subprocess.run(
            [
                "kind",
                "create",
                "cluster",
                "--name",
                name,
                "--config",
                str(kind_config),
                "--kubeconfig",
                str(kubeconfig),
                "--wait",
                "120s",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,  # we inspect returncode + skip on non-zero below
        )
    except (FileNotFoundError, OSError) as exc:
        # ``_have`` checks at import time should have already skipped
        # the test when these binaries aren't available, but a CI image
        # could remove them between collection and execution.  Treat
        # the same as an unmet dependency.
        pytest.skip(f"kind binary unavailable at fixture time: {exc}")
    if create_proc.returncode != 0:
        pytest.skip(
            f"kind create cluster failed (likely no nested-Docker support): "
            f"{create_proc.stderr.strip() or create_proc.stdout.strip()}"
        )

    namespace = "salt-test"
    cluster = KindCluster(name=name, kubeconfig=kubeconfig, namespace=namespace)

    # Create the test namespace so we don't pollute "default".
    cluster.kubectl("create", "namespace", namespace)

    try:
        yield cluster
    finally:
        log.info("Tearing down kind cluster %s", name)
        subprocess.run(
            ["kind", "delete", "cluster", "--name", name],
            capture_output=True,
            check=False,
            timeout=120,
        )


# ---------------------------------------------------------------------------
# Manifests + helpers
# ---------------------------------------------------------------------------


def _master_startup_script(pod_name, headless_fqdn, expected_peer_count):
    """
    Return the startup script for a salt-master Pod.

    Built without ``textwrap.dedent`` because the dedent algorithm
    "common-leading-whitespace minimum" interacts badly with multi-line
    interpolations like the cluster-peers list — a 2-space-indented
    second line will redefine the common prefix and pull the heredoc
    terminator out of column 0, silently breaking the script.  Each
    line is written at column 0 here, with explicit indentation only
    inside the YAML body of the master config heredoc.

    Identity wiring
    ---------------
    Salt's ``cli/daemons.py`` calls ``ip_bracket(opts["interface"])``
    which rejects hostnames, and the consensus layer uses
    ``opts["interface"]`` as the Raft node-id (see
    ``salt/cluster/consensus/service.py:73``).  So we *must* use a
    literal IP for ``interface``, AND every peer in ``cluster_peers``
    must be the IP that peer is using as its interface.

    The fixture solves the chicken-and-egg by:

    1. Exposing each Pod's IP via the Downward API as ``$POD_IP``.
    2. Setting the headless Service's ``publishNotReadyAddresses: true``
       so DNS returns all 3 endpoint IPs even before the readiness
       probe passes.
    3. The startup script polls ``getent hosts <headless-fqdn>`` until
       it returns all ``expected_peer_count + 1`` IPs, then writes
       ``interface: $POD_IP`` and ``cluster_peers: <other IPs>``.

    Source install
    --------------
    /salt is mounted read-only from the kind node so the host tree
    stays untouched.  Setuptools wants to write ``salt.egg-info`` back
    into the source during ``pip install -e``, so we copy a slim
    subset (excluding venv* / .git / artifacts / __pycache__) to a
    writable location and install from there.  Non-editable install:
    ``-e`` triggers ``setup.py develop``, which shells out to ``python
    -m pip`` for deps — the system Python in
    salt-ci-containers/testing:debian-12 ships pip as a script only,
    not as an importable module, so that fails.  A plain
    ``pip install <dir>`` builds a wheel and installs it via pip's
    own resolver, dodging the setup.py develop path entirely.
    """
    expected_total = expected_peer_count + 1
    lines = [
        "set -euxo pipefail",
        "mkdir -p /tmp/salt-src",
        "cd /salt && find . -maxdepth 1 -mindepth 1 \\",
        "    ! -name 'venv*' \\",
        "    ! -name '.git' \\",
        "    ! -name '.pytest_cache' \\",
        "    ! -name '.tox' \\",
        "    ! -name 'artifacts' \\",
        "    ! -name 'build' \\",
        "    ! -name 'salt.egg-info' \\",
        "    -exec cp -a -t /tmp/salt-src/ {} +",
        "cd /tmp/salt-src",
        "pip install --quiet --break-system-packages /tmp/salt-src",
        # Wait for the headless Service DNS to return every peer's IP.
        # publishNotReadyAddresses=true means we get the IPs as soon as
        # the Pod objects are scheduled, not just when they're Ready —
        # so this loop converges before any salt-master is listening.
        f'echo "Waiting for {expected_total} peer IPs from {headless_fqdn}..."',
        "for i in $(seq 1 60); do",
        f"  IPS=$(getent hosts {headless_fqdn} 2>/dev/null | awk '{{print $1}}' | sort -u || true)",
        '  COUNT=$(printf "%s\\n" "$IPS" | grep -c . || true)',
        f'  if [ "$COUNT" -ge "{expected_total}" ]; then',
        "    break",
        "  fi",
        "  sleep 1",
        "done",
        f"IPS=$(getent hosts {headless_fqdn} | awk '{{print $1}}' | sort -u)",
        # POD_IP comes from the Downward API env injected on the Pod.
        'PEER_IPS=$(echo "$IPS" | grep -v "^${POD_IP}$" || true)',
        'echo "POD_IP=$POD_IP" >&2',
        'echo "Discovered peers:" >&2',
        'echo "$PEER_IPS" | sed "s/^/  /" >&2',
        "mkdir -p /etc/salt /var/cache/salt/master /etc/salt/pki/master",
        # ``id`` and ``interface`` MUST match — salt's cluster code uses
        # ``opts["id"]`` to route ``cluster/peer/<id>`` events but
        # ``opts["interface"]`` for the entries in ``data["peers"]``;
        # diverging them produces ``KeyError: 'aes'`` on every cluster
        # event broadcast (``salt/channel/server.py:3012``).  The
        # loopback fixture (127.0.0.X for both id and interface) hides
        # this; the kind fixture has to align them explicitly.
        "{",
        '  echo "id: $POD_IP"',
        '  echo "interface: $POD_IP"',
        '  echo "cluster_id: kind-cluster"',
        '  echo "cluster_peers:"',
        '  echo "$PEER_IPS" | sed "s/^/  - /"',
        '  echo "cluster_pki_dir: /etc/salt/pki/master"',
        '  echo "cache_dir: /var/cache/salt/master"',
        '  echo "cluster_isolated_filesystem: true"',
        # Route salt-master logs to stderr so ``kubectl logs`` captures
        # them — the default ``/var/log/salt/master`` is invisible to k8s.
        '  echo "log_file: /dev/stderr"',
        '  echo "log_level: info"',
        '  echo "open_mode: true"',
        "} > /etc/salt/master",
        'echo "--- /etc/salt/master ---" >&2',
        "cat /etc/salt/master >&2",
        "exec salt-master",
    ]
    return "\n".join(lines) + "\n"


def _master_pod_manifest(name, image, headless_fqdn, expected_peers, namespace):
    """
    Return a Pod manifest (YAML string) for one salt-master.

    Built from a Python dict + ``yaml.safe_dump`` so multi-line
    script content embeds cleanly without indentation hand-holding.
    """
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {"app": "salt-master", "instance": name},
        },
        "spec": {
            "hostname": name,
            "subdomain": CLUSTER_SUBDOMAIN,
            "restartPolicy": "Never",
            "containers": [
                {
                    "name": "master",
                    "image": image,
                    "imagePullPolicy": "IfNotPresent",
                    "command": ["/bin/bash", "-c"],
                    "args": [
                        _master_startup_script(name, headless_fqdn, expected_peers)
                    ],
                    "env": [
                        {
                            "name": "POD_IP",
                            "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}},
                        }
                    ],
                    "volumeMounts": [
                        {
                            "name": "salt-source",
                            "mountPath": "/salt",
                            "readOnly": True,
                        }
                    ],
                    "ports": [
                        {"name": "ret", "containerPort": 4506},
                        {"name": "pub", "containerPort": 4505},
                        {"name": "cluster-pool", "containerPort": 55596},
                    ],
                    # Three probes per the 2026 Kubernetes guidance for
                    # consensus-based services (etcd's lesson: liveness
                    # must NOT reflect cluster state, or kubelet kills
                    # pods mid-election and prevents recovery).
                    #
                    # * startupProbe: blocks the other probes until the
                    #   master finished init.  failureThreshold * period
                    #   = 5 minutes, generous enough for slow joiners
                    #   on isolated-FS state-sync.
                    # * readinessProbe: ``health/ready`` lands when the
                    #   Raft commit gate fires; until then the headless
                    #   Service should not route to this master.
                    # * livenessProbe: ``health/alive`` mtime advances
                    #   from the parent's asyncio loop every 5 s; if it
                    #   ages past 30 s the loop is wedged and only a
                    #   restart will fix it.
                    "startupProbe": {
                        "exec": {
                            "command": [
                                "test",
                                "-f",
                                "/var/cache/salt/master/health/startup",
                            ]
                        },
                        "periodSeconds": 5,
                        "failureThreshold": 60,
                    },
                    "readinessProbe": {
                        "exec": {
                            "command": [
                                "test",
                                "-f",
                                "/var/cache/salt/master/health/ready",
                            ]
                        },
                        "periodSeconds": 5,
                        "failureThreshold": 3,
                    },
                    "livenessProbe": {
                        "exec": {
                            "command": [
                                "/bin/sh",
                                "-c",
                                # Stale mtime -> unhealthy.  Threshold is
                                # 6× DEFAULT_ALIVE_INTERVAL so a
                                # transient stall doesn't trip a restart.
                                'test "$(($(date +%s) - $(stat -c %Y '
                                '/var/cache/salt/master/health/alive)))" '
                                "-lt 30",
                            ]
                        },
                        "periodSeconds": 15,
                        "failureThreshold": 3,
                    },
                }
            ],
            "volumes": [
                {
                    "name": "salt-source",
                    "hostPath": {"path": "/salt", "type": "Directory"},
                }
            ],
        },
    }
    return yaml.safe_dump(pod, default_flow_style=False)


def _headless_service_manifest(namespace):
    """
    Headless ClusterIP=None service.  Combined with each Pod's
    ``hostname`` + ``subdomain``, gives every master a stable DNS
    name like ``salt-master-0.salt-cluster.<ns>.svc.cluster.local``.
    """
    svc = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": CLUSTER_SUBDOMAIN, "namespace": namespace},
        "spec": {
            "clusterIP": "None",
            "selector": {"app": "salt-master"},
            "ports": [
                {"name": "ret", "port": 4506},
                {"name": "pub", "port": 4505},
                {"name": "cluster-pool", "port": 55596},
            ],
            "publishNotReadyAddresses": True,
        },
    }
    return yaml.safe_dump(svc, default_flow_style=False)


def _wait_for_pod_ready(cluster, name, deadline):
    """Poll until *name* reports Ready=True or *deadline* is reached."""
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        proc = cluster.kubectl(
            "get",
            "pod",
            name,
            "-n",
            cluster.namespace,
            "-o",
            "jsonpath={.status.conditions[?(@.type=='Ready')].status}",
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip() == "True":
            return True
        time.sleep(2)
    # Dump diagnostics before failing.
    diag = cluster.kubectl(
        "describe", "pod", name, "-n", cluster.namespace, check=False
    )
    logs = cluster.kubectl(
        "logs", name, "-n", cluster.namespace, "--tail=100", check=False
    )
    raise TimeoutError(
        f"Pod {name} not ready within {deadline}s.\n"
        f"--- describe ---\n{diag.stdout}\n"
        f"--- logs ---\n{logs.stdout}\n"
    )


# ---------------------------------------------------------------------------
# Cluster of three masters
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def salt_master_image():
    """Image used for the salt-master Pods.  Override-able for local builds."""
    return os.environ.get("SALT_KIND_IMAGE", DEFAULT_SALT_IMAGE)


@pytest.fixture(scope="module")
def cluster_masters(kind_cluster, salt_master_image):
    """
    Deploy a 3-master Salt cluster on the kind node.

    Returns a dict ``{name: dns_name}`` for the three masters.  Tests
    use :func:`salt_in_pod` to run salt CLIs inside any of them.
    """
    namespace = kind_cluster.namespace
    headless_fqdn = f"{CLUSTER_SUBDOMAIN}.{namespace}.svc.cluster.local"
    expected_peers = len(MASTER_NAMES) - 1
    # Per-master FQDN — exposed to tests for ``salt_in_pod`` callers
    # that prefer DNS over Pod IPs (which change every kind run).
    dns_for = {
        name: f"{name}.{CLUSTER_SUBDOMAIN}.{namespace}.svc.cluster.local"
        for name in MASTER_NAMES
    }

    kind_cluster.kubectl(
        "apply", "-f", "-", input=_headless_service_manifest(namespace)
    )

    for name in MASTER_NAMES:
        manifest = _master_pod_manifest(
            name, salt_master_image, headless_fqdn, expected_peers, namespace
        )
        kind_cluster.kubectl("apply", "-f", "-", input=manifest)

    for name in MASTER_NAMES:
        _wait_for_pod_ready(kind_cluster, name, _DEFAULT_DEADLINE)

    yield dns_for


@pytest.fixture
def salt_in_pod(kind_cluster):
    """
    Return a callable ``salt_in_pod(pod_name, *args)`` that shells
    ``kubectl exec`` to run any salt CLI inside the named Pod.
    """

    def _run(pod_name, *args, timeout=60):
        proc = kind_cluster.kubectl(
            "exec",
            "-n",
            kind_cluster.namespace,
            pod_name,
            "--",
            *args,
            check=False,
            timeout=timeout,
        )
        return proc

    return _run

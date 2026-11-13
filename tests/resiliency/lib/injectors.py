"""
Fault injectors for the resiliency pytest port.

Each injector is a ``@contextlib.contextmanager`` that:
  - applies a mutation on ``__enter__``
  - yields ``None`` back to the test body
  - reverses the mutation on ``__exit__``, even if the body raised

Design rules (from ``tests/resiliency/CONTRACT.md`` and the parent-agent
prompt):

* Every setup failure translates to ``pytest.skip(reason)``, never a
  pytest failure.  Scenarios that can't physically run on the current
  compose stack should quietly fall through.
* All shell commands go through ``topology.exec(container, *argv)``; we
  never ``docker exec`` directly.  ``topology.exec`` is a thin wrapper
  around ``subprocess.run`` so we need no docker-py dependency.
* No host-side ``/tmp``; per-container ``/tmp`` is acceptable for small
  backup files (per the CONTRACT).  Any host-side scratch MUST go under
  ``$RESILIENCY_WORKDIR`` (we don't use any here).
* Every injector logs an ``INJECT`` marker on entry and a ``REVERT``
  marker on exit via ``logging.getLogger("resiliency.injector")``.
* Install helpers (``ensure_tc_in`` / ``ensure_iptables_in``) probe the
  binary with ``command -v`` first, then try apt/apk/dnf/yum in that
  order with ``|| true`` fallbacks, and ``pytest.skip`` if the binary is
  still absent.
"""

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict

from __future__ import annotations

import contextlib
import logging
import subprocess
from collections.abc import Iterator

import pytest

log = logging.getLogger("resiliency.injector")


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _mark_inject(name: str, args: dict, container: str | None) -> None:
    log.info("INJECT %s args=%r container=%s", name, args, container)


def _mark_revert(name: str, container: str | None) -> None:
    log.info("REVERT %s container=%s", name, container)


def _exec(
    topology,
    container: str,
    *cmd: str,
    check: bool = True,
) -> str:
    """Thin wrapper around topology.exec that always returns a string."""
    out = topology.exec(container, *cmd, check=check)
    if out is None:
        return ""
    return out


def _exec_quiet(topology, container: str, *cmd: str) -> bool:
    """Run a command, return True on exit-0, False otherwise.  Never raises."""
    try:
        topology.exec(container, *cmd, check=False)
        return True
    except Exception:  # noqa: BLE001 - never let injector crash on bad exec
        return False


def _binary_available(topology, container: str, binary: str) -> bool:
    """Probe for ``binary`` inside ``container`` via ``command -v``."""
    try:
        topology.exec(
            container,
            "sh",
            "-c",
            f"command -v {binary} >/dev/null 2>&1",
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception:  # noqa: BLE001
        return False


def _pick_container(topology, container: str | None, attr: str) -> str:
    """Return explicit container name if provided, else ``topology.spec.<attr>``."""
    if container is not None:
        return container
    return getattr(topology.spec, attr)


def _pick_iface(topology, iface: str | None) -> str:
    if iface is not None:
        return iface
    return topology.spec.choke_iface


# ---------------------------------------------------------------------------
# Install helpers
# ---------------------------------------------------------------------------


_INSTALL_SH_TMPL = r"""
(command -v apt-get >/dev/null 2>&1 \
    && apt-get update -qq >/dev/null 2>&1 \
    && apt-get install -y --no-install-recommends {apt_pkg} >/dev/null 2>&1) \
|| (command -v apk >/dev/null 2>&1 \
    && apk add --no-cache {apk_pkg} >/dev/null 2>&1) \
|| (command -v dnf >/dev/null 2>&1 \
    && dnf install -y {dnf_pkg} >/dev/null 2>&1) \
|| (command -v yum >/dev/null 2>&1 \
    && yum install -y {yum_pkg} >/dev/null 2>&1) \
|| true
"""


def _install_package(
    topology,
    container: str,
    binary: str,
    apt_pkg: str,
    apk_pkg: str,
    dnf_pkg: str,
    yum_pkg: str,
) -> bool:
    """Install the package providing ``binary`` using whichever package
    manager is present.  Returns True if ``binary`` is available after the
    install attempt, False otherwise.  Always best-effort; never raises."""
    if _binary_available(topology, container, binary):
        return True
    install_sh = _INSTALL_SH_TMPL.format(
        apt_pkg=apt_pkg,
        apk_pkg=apk_pkg,
        dnf_pkg=dnf_pkg,
        yum_pkg=yum_pkg,
    )
    _exec_quiet(topology, container, "sh", "-c", install_sh)
    return _binary_available(topology, container, binary)


@contextlib.contextmanager
def ensure_tc_in(topology, container: str | None = None) -> Iterator[None]:
    """Ensure the ``tc`` binary is present inside ``container``.

    Install ``iproute2``/``iproute-tc`` on the fly if missing.  Noop on
    exit.  ``pytest.skip`` if tc still isn't available after the install
    attempt (missing network / unprivileged image / etc.)."""
    c = _pick_container(topology, container, "choke_container")
    _mark_inject("ensure_tc_in", {"binary": "tc"}, c)
    try:
        ok = _install_package(
            topology,
            c,
            "tc",
            apt_pkg="iproute2",
            apk_pkg="iproute2",
            dnf_pkg="iproute-tc",
            yum_pkg="iproute-tc",
        )
        if not ok:
            pytest.skip(f"tc unavailable in {c}: install failed")
        try:
            yield
        finally:
            # Nothing to undo -- installing iproute2 is non-destructive.
            pass
    finally:
        _mark_revert("ensure_tc_in", c)


@contextlib.contextmanager
def ensure_iptables_in(topology, container: str) -> Iterator[None]:
    """Ensure ``iptables`` is present inside ``container``.

    ``pytest.skip`` if iptables still isn't available after the install
    attempt (missing NET_ADMIN, no network, locked-down image, etc.)."""
    _mark_inject("ensure_iptables_in", {"binary": "iptables"}, container)
    try:
        ok = _install_package(
            topology,
            container,
            "iptables",
            apt_pkg="iptables",
            apk_pkg="iptables",
            dnf_pkg="iptables",
            yum_pkg="iptables",
        )
        if not ok:
            pytest.skip(f"iptables unavailable in {container}: install failed")
        try:
            yield
        finally:
            pass
    finally:
        _mark_revert("ensure_iptables_in", container)


# ---------------------------------------------------------------------------
# tc / netem injectors
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def inject_netem(
    topology,
    netem_args: str,
    container: str | None = None,
    iface: str | None = None,
) -> Iterator[None]:
    """``tc qdisc replace dev $iface root netem $netem_args`` in the choke
    container.  On exit: ``tc qdisc del dev $iface root``.  Skip if tc is
    unavailable or if the replace fails.

    Multimaster special: when ``container`` is None (default) AND the
    topology is multimaster (no haproxy VIP; two independent masters
    the minion talks to), the netem rule is applied to EVERY master so
    both legs experience the same fault at the same time.  Applying it
    to only one master would leave the minion reachable via the other
    leg and silently neuter the phase.  Cluster3 gets one application
    (choke_container == haproxy) because that is the shared VIP.
    """
    if_ = _pick_iface(topology, iface)

    if container is not None:
        targets = [container]
    elif getattr(topology.spec, "is_multimaster", False):
        # Multimaster: iterate ALL masters so neither leg stays alive.
        targets = list(topology.spec.masters)
    else:
        targets = [_pick_container(topology, container, "choke_container")]

    _mark_inject(
        "inject_netem",
        {"netem_args": netem_args, "iface": if_, "targets": targets},
        ",".join(targets),
    )

    applied: list[str] = []
    for c in targets:
        if not _binary_available(topology, c, "tc"):
            # Reverse any already-applied targets before bailing out.
            for a in applied:
                _exec_quiet(
                    topology,
                    a,
                    "sh",
                    "-c",
                    f"tc qdisc del dev {if_} root 2>/dev/null || true",
                )
            _mark_revert("inject_netem", ",".join(targets))
            pytest.skip(f"tc unavailable in {c}: cannot inject netem")

        cmd = f"tc qdisc replace dev {if_} root netem {netem_args}"
        try:
            topology.exec(c, "sh", "-c", cmd, check=True)
            applied.append(c)
        except subprocess.CalledProcessError as exc:
            for a in applied:
                _exec_quiet(
                    topology,
                    a,
                    "sh",
                    "-c",
                    f"tc qdisc del dev {if_} root 2>/dev/null || true",
                )
            _mark_revert("inject_netem", ",".join(targets))
            pytest.skip(f"tc qdisc replace netem failed in {c}: {exc}")

    try:
        yield
    finally:
        try:
            for c in applied:
                _exec_quiet(
                    topology,
                    c,
                    "sh",
                    "-c",
                    f"tc qdisc del dev {if_} root 2>/dev/null || true",
                )
        finally:
            _mark_revert("inject_netem", ",".join(targets))


@contextlib.contextmanager
def inject_tbf(
    topology,
    rate: str,
    burst: str,
    latency: str,
    container: str | None = None,
    iface: str | None = None,
) -> Iterator[None]:
    """tbf rate-limit on the choke container's choke iface.

    ``tc qdisc replace dev $iface root tbf rate $rate burst $burst latency $latency``.
    On exit: ``tc qdisc del dev $iface root``.  Skip on setup errors."""
    c = _pick_container(topology, container, "choke_container")
    if_ = _pick_iface(topology, iface)
    _mark_inject(
        "inject_tbf",
        {"rate": rate, "burst": burst, "latency": latency, "iface": if_},
        c,
    )

    if not _binary_available(topology, c, "tc"):
        _mark_revert("inject_tbf", c)
        pytest.skip(f"tc unavailable in {c}: cannot inject tbf")

    cmd = (
        f"tc qdisc replace dev {if_} root tbf rate {rate} "
        f"burst {burst} latency {latency}"
    )
    try:
        topology.exec(c, "sh", "-c", cmd, check=True)
    except subprocess.CalledProcessError as exc:
        _mark_revert("inject_tbf", c)
        pytest.skip(f"tc qdisc replace tbf failed in {c}: {exc}")

    try:
        yield
    finally:
        try:
            _exec_quiet(
                topology,
                c,
                "sh",
                "-c",
                f"tc qdisc del dev {if_} root 2>/dev/null || true",
            )
        finally:
            _mark_revert("inject_tbf", c)


@contextlib.contextmanager
def inject_ingress_netem(
    topology,
    netem_args: str,
    container: str | None = None,
    iface: str | None = None,
) -> Iterator[None]:
    """Asymmetric-inbound netem via ifb + mirred redirect.

    Steps on enter:
      modprobe ifb numifbs=1
      ip link set dev ifb0 up
      tc qdisc add dev $iface ingress
      tc filter add dev $iface parent ffff: protocol all u32 \
          match u32 0 0 action mirred egress redirect dev ifb0
      tc qdisc replace dev ifb0 root netem $netem_args

    On exit, everything is torn down in reverse order.  Skip if tc or
    ifb isn't available."""
    c = _pick_container(topology, container, "choke_container")
    if_ = _pick_iface(topology, iface)
    _mark_inject(
        "inject_ingress_netem",
        {"netem_args": netem_args, "iface": if_},
        c,
    )

    if not _binary_available(topology, c, "tc"):
        _mark_revert("inject_ingress_netem", c)
        pytest.skip(f"tc unavailable in {c}: cannot inject ingress netem")

    probe = (
        "modprobe ifb numifbs=1 2>/dev/null "
        "|| (ls /sys/class/net/ifb0 >/dev/null 2>&1)"
    )
    try:
        topology.exec(c, "sh", "-c", probe, check=True)
    except subprocess.CalledProcessError as exc:
        _mark_revert("inject_ingress_netem", c)
        pytest.skip(f"modprobe ifb failed in {c} (unprivileged container?): {exc}")

    setup = (
        "set -e; "
        "ip link set dev ifb0 up; "
        f"tc qdisc add dev {if_} ingress; "
        f"tc filter add dev {if_} parent ffff: protocol all u32 "
        "match u32 0 0 action mirred egress redirect dev ifb0; "
        f"tc qdisc replace dev ifb0 root netem {netem_args}"
    )
    try:
        topology.exec(c, "sh", "-c", setup, check=True)
    except subprocess.CalledProcessError as exc:
        # Best-effort partial teardown before we bail.
        _exec_quiet(
            topology,
            c,
            "sh",
            "-c",
            f"tc qdisc del dev {if_} ingress 2>/dev/null || true; "
            "tc qdisc del dev ifb0 root 2>/dev/null || true; "
            "ip link set dev ifb0 down 2>/dev/null || true",
        )
        _mark_revert("inject_ingress_netem", c)
        pytest.skip(f"ifb/mirred setup failed in {c}: {exc}")

    try:
        yield
    finally:
        try:
            _exec_quiet(
                topology,
                c,
                "sh",
                "-c",
                f"tc qdisc del dev {if_} ingress 2>/dev/null || true; "
                "tc qdisc del dev ifb0 root 2>/dev/null || true; "
                "ip link set dev ifb0 down 2>/dev/null || true",
            )
        finally:
            _mark_revert("inject_ingress_netem", c)


@contextlib.contextmanager
def drop_interface_mtu(
    topology,
    mtu: int,
    container: str | None = None,
    iface: str | None = None,
) -> Iterator[None]:
    """Lower ``$iface`` MTU to ``$mtu``; restore 1500 on exit.

    Skip if ``ip`` is missing or ``ip link set`` fails (usually missing
    NET_ADMIN)."""
    c = _pick_container(topology, container, "choke_container")
    if_ = _pick_iface(topology, iface)
    _mark_inject("drop_interface_mtu", {"mtu": mtu, "iface": if_}, c)

    if not _binary_available(topology, c, "ip"):
        _mark_revert("drop_interface_mtu", c)
        pytest.skip(f"iproute2 (ip) unavailable in {c}: cannot change MTU")

    try:
        topology.exec(
            c,
            "sh",
            "-c",
            f"ip link set dev {if_} mtu {mtu}",
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        _mark_revert("drop_interface_mtu", c)
        pytest.skip(f"ip link set mtu {mtu} failed on {c} (missing NET_ADMIN?): {exc}")

    try:
        yield
    finally:
        try:
            _exec_quiet(
                topology,
                c,
                "sh",
                "-c",
                f"ip link set dev {if_} mtu 1500 2>/dev/null || true",
            )
        finally:
            _mark_revert("drop_interface_mtu", c)


# ---------------------------------------------------------------------------
# iptables injectors
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def tcp_reset_from_minions(
    topology,
    dport: int = 44506,
) -> Iterator[None]:
    """Install ``iptables -I OUTPUT -p tcp --dport $dport -j REJECT
    --reject-with tcp-reset`` on every minion in
    ``topology.spec.minion_containers``.

    Install iptables via apt/apk/dnf/yum if missing.  Skip the whole
    phase if NET_ADMIN is absent on *all* minions (every ``-I`` fails);
    phases where some minions succeed still run, and only successful
    minions get their rule deleted on exit."""
    minions: list[str] = list(topology.spec.minion_containers)
    _mark_inject(
        "tcp_reset_from_minions",
        {"dport": dport, "minions": minions},
        None,
    )

    # Ensure iptables is available on every minion first; record any that
    # we couldn't equip.
    setup_failed: list[str] = []
    for m in minions:
        ok = _install_package(
            topology,
            m,
            "iptables",
            apt_pkg="iptables",
            apk_pkg="iptables",
            dnf_pkg="iptables",
            yum_pkg="iptables",
        )
        if not ok:
            setup_failed.append(m)

    if setup_failed and len(setup_failed) == len(minions):
        # No minion got iptables -- can't run the phase at all.
        _mark_revert("tcp_reset_from_minions", None)
        pytest.skip(
            f"iptables unavailable in all minions: {setup_failed} "
            "(NET_ADMIN missing?)"
        )

    rule = (
        f"iptables -I OUTPUT -p tcp --dport {dport} "
        "-j REJECT --reject-with tcp-reset"
    )
    unrule = (
        f"iptables -D OUTPUT -p tcp --dport {dport} "
        "-j REJECT --reject-with tcp-reset"
    )

    applied: list[str] = []
    for m in minions:
        if m in setup_failed:
            continue
        try:
            topology.exec(m, "sh", "-c", rule, check=True)
            applied.append(m)
        except subprocess.CalledProcessError as exc:
            log.warning("tcp_reset_from_minions: -I failed on %s: %s", m, exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("tcp_reset_from_minions: -I crashed on %s: %s", m, exc)

    if not applied:
        _mark_revert("tcp_reset_from_minions", None)
        pytest.skip(
            "iptables -I OUTPUT rejected on all minions (missing NET_ADMIN cap)"
        )

    try:
        yield
    finally:
        for m in applied:
            _exec_quiet(topology, m, "sh", "-c", f"{unrule} 2>/dev/null || true")
        _mark_revert("tcp_reset_from_minions", None)


@contextlib.contextmanager
def iptables_reject(
    topology,
    container: str,
    dport: int,
    proto: str = "tcp",
    reject_with: str = "tcp-reset",
) -> Iterator[None]:
    """Generic ``iptables -I OUTPUT`` REJECT for a single container.

    Mirrors ``tcp_reset_from_minions`` but for arbitrary container+port
    combos (e.g. a master-side ingress REJECT on 4506)."""
    _mark_inject(
        "iptables_reject",
        {"dport": dport, "proto": proto, "reject_with": reject_with},
        container,
    )

    ok = _install_package(
        topology,
        container,
        "iptables",
        apt_pkg="iptables",
        apk_pkg="iptables",
        dnf_pkg="iptables",
        yum_pkg="iptables",
    )
    if not ok:
        _mark_revert("iptables_reject", container)
        pytest.skip(
            f"iptables unavailable in {container}: install failed "
            "(NET_ADMIN missing?)"
        )

    rule = (
        f"iptables -I OUTPUT -p {proto} --dport {dport} "
        + f"-j REJECT --reject-with {reject_with}"
    )
    unrule = (
        f"iptables -D OUTPUT -p {proto} --dport {dport} "
        + f"-j REJECT --reject-with {reject_with}"
    )
    try:
        topology.exec(container, "sh", "-c", rule, check=True)
    except subprocess.CalledProcessError as exc:
        _mark_revert("iptables_reject", container)
        pytest.skip(
            f"iptables -I OUTPUT failed on {container} " f"(missing NET_ADMIN?): {exc}"
        )

    try:
        yield
    finally:
        try:
            _exec_quiet(
                topology,
                container,
                "sh",
                "-c",
                f"{unrule} 2>/dev/null || true",
            )
        finally:
            _mark_revert("iptables_reject", container)


# ---------------------------------------------------------------------------
# Container-lifecycle injectors
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def paused_container(topology, container: str) -> Iterator[None]:
    """``docker pause`` / ``docker unpause`` via ``topology.pause/unpause``."""
    _mark_inject("paused_container", {}, container)
    try:
        topology.pause(container)
    except Exception as exc:  # noqa: BLE001
        _mark_revert("paused_container", container)
        pytest.skip(f"docker pause {container} failed: {exc}")

    try:
        yield
    finally:
        try:
            topology.unpause(container)
        except Exception as exc:  # noqa: BLE001
            # Last-ditch unpause via direct docker call -- never leave a
            # container paused on the way out.
            log.warning(
                "paused_container: unpause via topology failed (%s); "
                "falling back to subprocess",
                exc,
            )
            subprocess.run(
                ["docker", "unpause", container],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            _mark_revert("paused_container", container)


@contextlib.contextmanager
def sigstopped_container(topology, container: str) -> Iterator[None]:
    """``docker kill -s STOP`` / ``docker kill -s CONT`` -- SIGSTOP freeze.

    Belt-and-braces: always try to send CONT on exit even if the STOP
    initially failed, so we never leave a container frozen."""
    _mark_inject("sigstopped_container", {}, container)
    stop_ok = True
    try:
        try:
            topology.kill_signal(container, "STOP")
        except Exception as exc:  # noqa: BLE001
            stop_ok = False
            _mark_revert("sigstopped_container", container)
            pytest.skip(f"docker kill -s STOP {container} failed: {exc}")

        try:
            yield
        finally:
            # Always try CONT, even if STOP failed earlier (defensive).
            try:
                topology.kill_signal(container, "CONT")
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "sigstopped_container: CONT via topology failed (%s); "
                    "falling back to subprocess",
                    exc,
                )
                subprocess.run(
                    ["docker", "kill", "-s", "CONT", container],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    finally:
        if stop_ok:
            _mark_revert("sigstopped_container", container)


@contextlib.contextmanager
def stopped_container(
    topology,
    container: str,
    timeout: int = 30,
) -> Iterator[None]:
    """``docker stop --time=$timeout`` on entry; ``docker start`` on exit."""
    _mark_inject("stopped_container", {"timeout": timeout}, container)
    try:
        try:
            topology.stop(container, timeout_sec=timeout)
        except Exception as exc:  # noqa: BLE001
            _mark_revert("stopped_container", container)
            pytest.skip(f"docker stop {container} failed: {exc}")

        try:
            yield
        finally:
            try:
                topology.start(container)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "stopped_container: start via topology failed (%s); "
                    "falling back to subprocess",
                    exc,
                )
                subprocess.run(
                    ["docker", "start", container],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    finally:
        _mark_revert("stopped_container", container)


# ---------------------------------------------------------------------------
# Network / filesystem injectors
# ---------------------------------------------------------------------------


def _resolve_container_network(container: str) -> str:
    """Return the first docker network attached to ``container``.

    Uses ``docker inspect`` directly rather than ``topology.exec`` because
    this is a host-side query, not an in-container command."""
    try:
        out = subprocess.run(
            [
                "docker",
                "inspect",
                container,
                "--format",
                "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"docker inspect {container} failed: {exc}") from exc
    net = (out or "").split()
    if not net:
        raise RuntimeError(f"no networks attached to {container}")
    return net[0]


@contextlib.contextmanager
def disconnected_from_network(
    topology,
    container: str,
) -> Iterator[None]:
    """``docker network disconnect`` on enter / ``connect`` on exit.

    The network is the first attached network reported by
    ``docker inspect`` -- for compose-managed containers that's
    ``<project>_salt-net`` in practice, but we don't hardcode the
    convention."""
    _mark_inject("disconnected_from_network", {}, container)
    try:
        net = _resolve_container_network(container)
    except RuntimeError as exc:
        _mark_revert("disconnected_from_network", container)
        pytest.skip(str(exc))

    try:
        subprocess.run(
            ["docker", "network", "disconnect", net, container],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        _mark_revert("disconnected_from_network", container)
        pytest.skip(f"docker network disconnect {net} {container} failed: {exc}")

    try:
        yield
    finally:
        try:
            subprocess.run(
                ["docker", "network", "connect", net, container],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            _mark_revert("disconnected_from_network", container)


@contextlib.contextmanager
def remounted_readonly(
    topology,
    container: str,
    path: str,
) -> Iterator[None]:
    """Make ``path`` inside ``container`` read-only.

    Tries ``mount -o remount,ro $path`` under ``--privileged`` first.
    If that fails (not a mount point, or CAP_SYS_ADMIN absent), falls
    back to ``chmod -R u-w $path``.  Remembers which mode worked and
    reverses the corresponding mutation on exit.  Skip if both modes
    fail."""
    _mark_inject("remounted_readonly", {"path": path}, container)
    mode: str | None = None

    # Try mount -o remount,ro first (direct).
    try:
        topology.exec(
            container,
            "sh",
            "-c",
            f"mount -o remount,ro '{path}' 2>/dev/null",
            check=True,
        )
        mode = "mount"
    except Exception:  # noqa: BLE001
        pass

    # Fallback 1: self bind-mount then remount ro.  Covers "not a mount
    # point" errors when CAP_SYS_ADMIN is present.
    if mode is None:
        try:
            topology.exec(
                container,
                "sh",
                "-c",
                (
                    f"mount --bind '{path}' '{path}' 2>/dev/null "
                    f"&& mount -o remount,ro,bind '{path}' 2>/dev/null"
                ),
                check=True,
            )
            mode = "mount"
        except Exception:  # noqa: BLE001
            pass

    # Fallback 2: chmod -R u-w.  Works without CAP_SYS_ADMIN but only
    # blocks the owning user.
    if mode is None:
        try:
            topology.exec(
                container,
                "sh",
                "-c",
                f"chmod -R u-w '{path}' 2>/dev/null",
                check=True,
            )
            mode = "chmod"
        except Exception:  # noqa: BLE001
            pass

    if mode is None:
        _mark_revert("remounted_readonly", container)
        pytest.skip(
            f"remounted_readonly({path}) failed on {container}: "
            "neither mount -o remount,ro nor chmod -w worked"
        )

    try:
        yield
    finally:
        try:
            if mode == "mount":
                _exec_quiet(
                    topology,
                    container,
                    "sh",
                    "-c",
                    f"mount -o remount,rw '{path}' 2>/dev/null || true",
                )
            else:
                _exec_quiet(
                    topology,
                    container,
                    "sh",
                    "-c",
                    f"chmod -R u+w '{path}' 2>/dev/null || true",
                )
        finally:
            _mark_revert("remounted_readonly", container)


@contextlib.contextmanager
def dns_hosts_poisoned(
    topology,
    container: str,
    hostnames: list[str],
) -> Iterator[None]:
    """Prepend ``127.0.0.1`` entries for each hostname to
    ``/etc/hosts`` inside ``container``.

    A per-container backup is kept inside the *container's* ``/tmp``
    (not the host's /tmp -- see "No host /tmp" rule).  Restored on exit
    from that backup.  Skip if we can't read /etc/hosts or write the
    backup."""
    _mark_inject(
        "dns_hosts_poisoned",
        {"hostnames": list(hostnames)},
        container,
    )

    if not hostnames:
        # Nothing to do; yield without touching state.
        try:
            yield
        finally:
            _mark_revert("dns_hosts_poisoned", container)
        return

    # Container-local backup path.  "/tmp" inside the container is fine;
    # the rule bans HOST /tmp, not container /tmp (see CONTRACT).
    backup_path = "/tmp/__resiliency_hosts.bak"

    # Back up /etc/hosts into the container.
    try:
        topology.exec(
            container,
            "sh",
            "-c",
            f"cp -f /etc/hosts {backup_path}",
            check=True,
        )
    except Exception as exc:  # noqa: BLE001
        _mark_revert("dns_hosts_poisoned", container)
        pytest.skip(
            f"dns_hosts_poisoned: cannot back up /etc/hosts on " f"{container}: {exc}"
        )

    # Build the poisoned file in a tmp path inside the container, then
    # cp over /etc/hosts.  Strategy: start from the backup, strip any
    # existing lines whose host/alias columns mention one of the
    # poisoned names (awk-based because busybox images lack sort -R /
    # shuf; awk is universal), then append 127.0.0.1 entries.
    names_sh = " ".join(hostnames)
    poison_sh = (
        "set -e; "
        f'NAMES="{names_sh}"; '
        f"cp -f {backup_path} /tmp/__resiliency_hosts.new; "
        # Strip existing lines mentioning any poisoned name.
        'awk -v names="$NAMES" \''
        'BEGIN { n = split(names, a, " "); '
        "        for (i = 1; i <= n; i++) bad[a[i]] = 1 } "
        "/^#/ || /^[[:space:]]*$/ { print; next } "
        "{ keep = 1; "
        "  for (j = 2; j <= NF; j++) if ($j in bad) keep = 0; "
        "  if (keep) print }' "
        "/tmp/__resiliency_hosts.new > /tmp/__resiliency_hosts.stripped; "
        "mv /tmp/__resiliency_hosts.stripped /tmp/__resiliency_hosts.new; "
        # Append poisoned entries.
        "for n in $NAMES; do "
        "    printf '127.0.0.1\\t%s\\n' \"$n\" "
        ">> /tmp/__resiliency_hosts.new; "
        "done; "
        "cp -f /tmp/__resiliency_hosts.new /etc/hosts; "
        "rm -f /tmp/__resiliency_hosts.new"
    )
    try:
        topology.exec(container, "sh", "-c", poison_sh, check=True)
    except Exception as exc:  # noqa: BLE001
        # Restore defensively and skip.
        _exec_quiet(
            topology,
            container,
            "sh",
            "-c",
            f"[ -f {backup_path} ] && cp -f {backup_path} /etc/hosts; "
            f"rm -f {backup_path} /tmp/__resiliency_hosts.new "
            "/tmp/__resiliency_hosts.stripped",
        )
        _mark_revert("dns_hosts_poisoned", container)
        pytest.skip(
            f"dns_hosts_poisoned: failed to write poisoned hosts "
            f"in {container}: {exc}"
        )

    try:
        yield
    finally:
        try:
            _exec_quiet(
                topology,
                container,
                "sh",
                "-c",
                f"[ -f {backup_path} ] && cp -f {backup_path} /etc/hosts; "
                f"rm -f {backup_path} /tmp/__resiliency_hosts.new "
                "/tmp/__resiliency_hosts.stripped",
            )
        finally:
            _mark_revert("dns_hosts_poisoned", container)


@contextlib.contextmanager
def filled_filesystem(
    topology,
    container: str,
    path: str,
    size_mb: int,
) -> Iterator[None]:
    """Create a ``$size_mb``-MB filler file under ``$path`` in ``$container``.

    Prefers ``fallocate`` for instant sparse allocation; falls back to
    ``dd`` (bounded at the requested size to avoid filling the host
    disk).  Deletes the filler file on exit."""
    fill_file = f"{path.rstrip('/')}/__resiliency_fill"
    _mark_inject(
        "filled_filesystem",
        {"path": path, "size_mb": size_mb, "fill_file": fill_file},
        container,
    )

    applied = False
    # Prefer fallocate.
    if _binary_available(topology, container, "fallocate"):
        try:
            topology.exec(
                container,
                "sh",
                "-c",
                f"fallocate -l {size_mb}M '{fill_file}' 2>/dev/null",
                check=True,
            )
            applied = True
        except Exception:  # noqa: BLE001
            applied = False

    # Fallback to dd.  Bounded at size_mb so we never exceed the request.
    if not applied:
        _exec_quiet(
            topology,
            container,
            "sh",
            "-c",
            f"dd if=/dev/zero of='{fill_file}' bs=1M count={size_mb} " "2>/dev/null",
        )
        # Verify the file has non-zero size.
        try:
            topology.exec(
                container,
                "sh",
                "-c",
                f"[ -s '{fill_file}' ]",
                check=True,
            )
            applied = True
        except Exception:  # noqa: BLE001
            applied = False

    if not applied:
        _mark_revert("filled_filesystem", container)
        pytest.skip(
            f"filled_filesystem({path}, {size_mb}M) failed on "
            f"{container}: neither fallocate nor dd produced the filler"
        )

    try:
        yield
    finally:
        try:
            _exec_quiet(
                topology,
                container,
                "sh",
                "-c",
                f"rm -f '{fill_file}' 2>/dev/null || true",
            )
        finally:
            _mark_revert("filled_filesystem", container)

"""
SSH resource module — exposes remote Linux/Unix machines as Salt Resources
using the salt-ssh Shell transport layer.

Each ``ssh`` resource maps to one remote host reachable via SSH.  Because
resources share a single loader per type, a minion managing 500 SSH hosts
uses one loader rather than 500 proxy processes, each with its own key pair.

This module uses :class:`salt.client.ssh.shell.Shell` for raw command
execution (``cmd_run``, ``ping``) and :class:`salt.client.ssh.Single` with
the salt-thin bundle for grain collection (``grains.items``), giving the same
complete, accurate grain set that ``salt-ssh`` provides.

Configuration (via Pillar; top-level key defaults to ``resources``, overridable
with minion option ``resource_pillar_key``)::

    resources:
      ssh:
        hosts:
          web-01:
            host: 192.168.1.10
            user: root
            priv: /etc/salt/ssh_keys/web-01
          web-02:
            host: 192.168.1.11
            user: admin
            passwd: secretpassword
            no_host_keys: true

Per-host connection parameters:

``host``
    Hostname or IP address of the remote machine (required).
``user``
    SSH login user (default: ``root``).
``port``
    SSH port (default: ``22``).
``priv``
    Path to the SSH private key file.  Mutually exclusive with ``passwd``
    but both may be specified; when ``priv`` is set Salt uses key-based
    option strings even if ``passwd`` is also set.
``passwd``
    SSH password.  Prefer key-based authentication for production.
``priv_passwd``
    Passphrase protecting the private key.
``sudo``
    Run commands as root via sudo (default: ``False``).
``timeout``
    SSH connection timeout in seconds (default: ``30``).
``identities_only``
    Pass ``-o IdentitiesOnly=yes`` to prevent the SSH agent from offering
    unrelated keys (default: ``False``).
``no_host_keys``
    Disable host key checking entirely — sets both
    ``StrictHostKeyChecking=no`` and ``UserKnownHostsFile=/dev/null``
    (default: ``False``).
``ignore_host_keys``
    Pass ``-o StrictHostKeyChecking=no`` without discarding the
    known-hosts database (default: ``False``).
``known_hosts_file``
    Path to a custom ``known_hosts`` file for this host.
``ssh_options``
    List of additional ``-o Key=Value`` options passed verbatim to the
    ``ssh`` binary.
``keepalive``
    Enable TCP keepalives (default: ``True``).
``keepalive_interval``
    ``ServerAliveInterval`` in seconds (default: from Salt opts or ``60``).
``keepalive_count_max``
    ``ServerAliveCountMax`` (default: from Salt opts or ``3``).
"""

import logging
import os
import uuid

import salt.client.ssh
import salt.client.ssh.shell
import salt.config
import salt.fileclient
import salt.utils.json
import salt.utils.network
import salt.utils.path
import salt.utils.resources

log = logging.getLogger(__name__)

CONTEXT_KEY = "ssh_resource"


# ---------------------------------------------------------------------------
# Module availability
# ---------------------------------------------------------------------------


def __virtual__():
    """
    Only load when the ``ssh`` binary is present on the minion's PATH.
    """
    if not salt.utils.path.which("ssh"):
        return False, "ssh binary not found on PATH"
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resource_id():
    """Return the ID of the resource currently being operated on."""
    return __resource__["id"]  # pylint: disable=undefined-variable


def _host_cfg(resource_id):
    """Return the Pillar-sourced connection config dict for *resource_id*."""
    return __context__[CONTEXT_KEY]["hosts"].get(
        resource_id, {}
    )  # pylint: disable=undefined-variable


def _shell_opts(cfg):
    """
    Build a merged opts dict for :class:`~salt.client.ssh.shell.Shell`.

    ``Shell`` reads ``ignore_host_keys``, ``no_host_keys``,
    ``known_hosts_file``, and ``_ssh_version`` out of its opts dict rather
    than out of constructor kwargs.  This helper layers per-host overrides on
    top of ``__opts__`` so each Shell instance honours its resource's config.
    """
    merged = dict(__opts__)  # pylint: disable=undefined-variable
    for key in ("ignore_host_keys", "no_host_keys", "known_hosts_file"):
        if key in cfg:
            merged[key] = cfg[key]
    # Ensure _ssh_version is always present.  _passwd_opts() accesses it via
    # [] without a default and would raise KeyError without this guard.
    if "_ssh_version" not in merged:
        cached = __context__.get(CONTEXT_KEY, {}).get(
            "_ssh_version"
        )  # pylint: disable=undefined-variable
        merged["_ssh_version"] = (
            cached if cached is not None else salt.client.ssh.ssh_version()
        )
    return merged


def _make_shell(resource_id, cfg_override=None):
    """
    Return a :class:`~salt.client.ssh.shell.Shell` instance for *resource_id*.

    :param str resource_id: The bare resource ID.
    :param dict cfg_override: Optional dict of per-call overrides (e.g.
        ``{"timeout": 5}``).  Values are layered on top of the stored host
        config; the stored config is not mutated.
    """
    cfg = _host_cfg(resource_id)
    if cfg_override:
        cfg = dict(cfg)
        cfg.update(cfg_override)

    return salt.client.ssh.shell.Shell(
        _shell_opts(cfg),
        host=cfg["host"],
        user=cfg.get("user", "root"),
        port=cfg.get("port", 22),
        passwd=cfg.get("passwd"),
        priv=cfg.get("priv"),
        priv_passwd=cfg.get("priv_passwd"),
        timeout=cfg.get("timeout", 30),
        sudo=cfg.get("sudo", False),
        tty=cfg.get("tty", False),
        identities_only=cfg.get("identities_only", False),
        ssh_options=cfg.get("ssh_options"),
        keepalive=cfg.get("keepalive", True),
        keepalive_interval=cfg.get("keepalive_interval", 60),
        keepalive_count_max=cfg.get("keepalive_count_max", 3),
    )


def _thin_dir(cfg):
    """
    Return the remote working directory for the salt-thin bundle.

    Uses the per-host ``thin_dir`` config key when provided.  Otherwise
    computes a path under ``/tmp/`` (always world-writable) using the same
    ``.<user>_<fqdnuuid>_salt`` naming convention as Salt's DEFAULT_THIN_DIR,
    but avoiding ``/var/tmp/`` which may be root-only on some systems.
    """
    if "thin_dir" in cfg:
        return cfg["thin_dir"]
    fqdn_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, salt.utils.network.get_fqhostname()).hex[
        :6
    ]
    return "/tmp/.{}_{}_salt".format(cfg.get("user", "root"), fqdn_uuid)


def _relenv_path():
    """
    Return the path to a pre-built relenv tarball if one exists locally, otherwise
    ``None`` so ``Single.__init__`` can detect the remote arch and fetch the right
    tarball (same strategy as :func:`salt.modules.sshresource_state._relenv_path`).

    Pre-resolving an existing local path avoids an extra SSH round-trip during
    ``Single`` construction when ``Single`` was instantiated inside a minion job
    worker (where ``detect_os_arch()`` hung or added latency).
    """
    cachedir = __opts__.get("cachedir", "")  # pylint: disable=undefined-variable
    for arch in ("x86_64", "arm64"):
        path = os.path.join(cachedir, "relenv", "linux", arch, "salt-relenv.tar.xz")
        if os.path.exists(path):
            return path
    return None


def _file_client():
    """
    Return a file client for ``Single.cmd_block()`` to use when regenerating
    extension modules via ``mod_data(fsclient)``.

    Uses the master opts cached during :func:`init` to build an ``FSClient``
    (local-filesystem, no network channel) — the same approach used by
    ``sshresource_state._file_client()``.  Falls back to a ``RemoteClient``
    when no cached master opts are available.
    """
    master_opts = __context__.get(
        CONTEXT_KEY, {}
    ).get(  # pylint: disable=undefined-variable
        "master_opts"
    )
    if master_opts:
        mo = dict(master_opts)
        mo.setdefault(
            "cachedir", __opts__.get("cachedir", "")
        )  # pylint: disable=undefined-variable
        return salt.fileclient.FSClient(mo)
    log.warning(
        "ssh resource: no cached master opts in context, "
        "falling back to RemoteClient for fsclient"
    )
    return salt.fileclient.get_file_client(
        __opts__
    )  # pylint: disable=undefined-variable


def _make_single(resource_id, argv):
    """
    Return a :class:`~salt.client.ssh.Single` instance for *resource_id*
    configured to run *argv* via the salt-thin bundle.

    We call :meth:`~salt.client.ssh.Single.cmd_block` directly rather than
    :meth:`~salt.client.ssh.Single.run` to stay on the thin-bundle code path
    and avoid the wrapper-function path that requires a master file client.
    """
    cfg = _host_cfg(resource_id)
    ctx = __context__.get(CONTEXT_KEY, {})  # pylint: disable=undefined-variable

    single_opts = dict(__opts__)  # pylint: disable=undefined-variable
    single_opts["no_host_keys"] = cfg.get(
        "no_host_keys", single_opts.get("no_host_keys", False)
    )
    single_opts["ignore_host_keys"] = cfg.get(
        "ignore_host_keys", single_opts.get("ignore_host_keys", False)
    )
    if "known_hosts_file" in cfg:
        single_opts["known_hosts_file"] = cfg["known_hosts_file"]
    single_opts["_ssh_version"] = (
        ctx.get("_ssh_version") or salt.client.ssh.ssh_version()
    )

    single_opts["relenv"] = True
    return salt.client.ssh.Single(
        single_opts,
        argv,
        resource_id,
        thin=_relenv_path(),
        fsclient=_file_client(),
        host=cfg["host"],
        user=cfg.get("user", "root"),
        port=cfg.get("port", 22),
        passwd=cfg.get("passwd"),
        priv=cfg.get("priv"),
        priv_passwd=cfg.get("priv_passwd"),
        timeout=cfg.get("timeout", 30),
        sudo=cfg.get("sudo", False),
        tty=cfg.get("tty", False),
        identities_only=cfg.get("identities_only", False),
        ssh_options=cfg.get("ssh_options"),
        keepalive=cfg.get("keepalive", True),
        keepalive_interval=cfg.get("keepalive_interval", 60),
        keepalive_count_max=cfg.get("keepalive_count_max", 3),
        thin_dir=_thin_dir(cfg),
    )


# ---------------------------------------------------------------------------
# Required resource interface
# ---------------------------------------------------------------------------


def init(opts):
    """
    Initialize the ``ssh`` resource type for this minion.

    Called once when the resource type is loaded, before any per-resource
    operations are dispatched.  Reads host configs from the ``ssh`` entry under
    the pillar subtree selected by ``resource_pillar_key`` (see
    :func:`salt.utils.resources.pillar_resources_tree`), caches them in
    ``__context__["ssh_resource"]``, and pre-resolves the SSH binary version
    so that :func:`_shell_opts` never has to run a subprocess during a job.

    :param dict opts: The Salt opts dict.
    """
    resource_cfg = salt.utils.resources.pillar_resources_tree(opts).get("ssh", {})
    hosts = resource_cfg.get("hosts", {})
    __context__[CONTEXT_KEY] = {  # pylint: disable=undefined-variable
        "initialized": True,
        "hosts": hosts,
        "_ssh_version": salt.client.ssh.ssh_version(),
    }

    # Cache master opts so sshresource_state can build an FSClient for state
    # compilation without creating a new network channel inside a job thread.
    # We read the master config from disk (same conf dir as the minion) to get
    # the full config with all defaults, rather than the partial dict returned
    # by RemoteClient.master_opts() which omits keys like fileserver_backend.
    try:
        conf_dir = os.path.dirname(opts.get("conf_file", ""))
        master_conf = os.path.join(conf_dir, "master")
        if os.path.isfile(master_conf):
            master_opts = salt.config.master_config(master_conf)
            # roots.FSChan expects cachedir; minimal or test master configs may omit it.
            master_opts.setdefault("cachedir", opts.get("cachedir", ""))
            __context__[CONTEXT_KEY][
                "master_opts"
            ] = master_opts  # pylint: disable=undefined-variable
            log.debug("ssh resource init: loaded master opts from %s", master_conf)
        else:
            # Fall back to RemoteClient if we can't find the master config on disk.
            file_client = salt.fileclient.get_file_client(opts)
            master_opts = file_client.master_opts()
            if isinstance(master_opts, dict) and master_opts:
                master_opts.setdefault("fileserver_backend", ["roots"])
                master_opts.setdefault("cachedir", opts.get("cachedir", ""))
                __context__[CONTEXT_KEY][
                    "master_opts"
                ] = master_opts  # pylint: disable=undefined-variable
            file_client.destroy()
    except Exception as exc:  # pylint: disable=broad-except
        log.warning("ssh resource init: failed to load master opts: %s", exc)

    log.debug("ssh resource init() called, managing: %s", list(hosts))


def initialized():
    """
    Return ``True`` if :func:`init` has completed successfully.

    :rtype: bool
    """
    return __context__.get(CONTEXT_KEY, {}).get(
        "initialized", False
    )  # pylint: disable=undefined-variable


def discover(opts):
    """
    Return the list of SSH resource IDs managed by this minion.

    The list is the set of keys under ``hosts`` for the ``ssh`` type under the
    configured resource pillar subtree.  Adding or removing a
    host from that Pillar key and running ``saltutil.refresh_resources``
    updates the Master's Resource Registry without any process restart.

    :param dict opts: The Salt opts dict.
    :rtype: list[str]
    """
    hosts = (
        salt.utils.resources.pillar_resources_tree(opts).get("ssh", {}).get("hosts", {})
    )
    resource_ids = list(hosts)
    log.debug("ssh resource discover() returning: %s", resource_ids)
    return resource_ids


def grains():
    """
    Return full Salt grains for the current SSH resource.

    Runs ``grains.items`` on the remote host via the salt-thin bundle
    (the same mechanism used by ``salt-ssh``), giving us the complete,
    accurate grain set rather than a hand-crafted subset.

    Results are cached in ``__context__`` per resource ID.  Call
    :func:`grains_refresh` to force re-collection.

    :rtype: dict
    """
    resource_id = _resource_id()

    ctx = __context__.get(CONTEXT_KEY, {})  # pylint: disable=undefined-variable
    cached = ctx.get("grains", {}).get(resource_id)
    if cached is not None:
        return cached

    cfg = _host_cfg(resource_id)
    single = _make_single(resource_id, ["grains.items"])
    stdout, stderr, retcode = single.cmd_block()

    if retcode != 0 or stdout.startswith("ERROR"):
        log.warning(
            "ssh resource grains: grains.items failed for %s (rc=%d): %s",
            resource_id,
            retcode,
            stderr or stdout,
        )
        return {
            "resource_type": "ssh",
            "resource_id": resource_id,
            "host": cfg.get("host", ""),
        }

    try:
        parsed = salt.utils.json.loads(stdout)
        # thin bundle wraps result as {"local": {"jid": "...", "return": {...}}}
        data = parsed.get("local", {}).get("return", parsed)
    except Exception as exc:  # pylint: disable=broad-except
        log.warning(
            "ssh resource grains: failed to parse output for %s: %s", resource_id, exc
        )
        return {
            "resource_type": "ssh",
            "resource_id": resource_id,
            "host": cfg.get("host", ""),
        }

    data["resource_type"] = "ssh"
    data["resource_id"] = resource_id

    ctx.setdefault("grains", {})[resource_id] = data
    return data


def grains_refresh():
    """
    Invalidate the grains cache for the current SSH resource and re-collect.

    :rtype: dict
    """
    resource_id = _resource_id()
    ctx = __context__.get(CONTEXT_KEY, {})  # pylint: disable=undefined-variable
    ctx.get("grains", {}).pop(resource_id, None)
    return grains()


def ping():
    """
    Return ``True`` if the current SSH resource is reachable via SSH.

    Runs ``echo ping`` on the remote host.  A zero exit code and the
    expected output indicate that the SSH connection is healthy.
    """
    resource_id = _resource_id()
    try:
        shell = _make_shell(resource_id, cfg_override={"timeout": 10})
        stdout, _stderr, retcode = shell.exec_cmd("echo ping")
        return retcode == 0 and "ping" in stdout
    except Exception as exc:  # pylint: disable=broad-except
        log.warning("ssh resource ping() failed for %s: %s", resource_id, exc)
        return False


def shutdown(opts):
    """
    Tear down the ``ssh`` resource type.

    Called when the minion shuts down or the resource type is unloaded.
    Clears shared type-level state from ``__context__``.

    :param dict opts: The Salt opts dict.
    """
    log.debug("ssh resource shutdown() called")
    __context__.pop(CONTEXT_KEY, None)  # pylint: disable=undefined-variable


# ---------------------------------------------------------------------------
# Per-resource operations
# ---------------------------------------------------------------------------


def cmd_run(cmd, timeout=None):
    """
    Execute a shell command on the current SSH resource.

    This is the primary building block for execution modules that target
    SSH resources — analogous to ``__proxy__["ssh_sample.cmd"]()`` in the
    proxy model.  Execution module overrides for the ``ssh`` resource type
    delegate their work here.

    Returns a dict with keys:

    * ``stdout``  — standard output from the remote command
    * ``stderr``  — standard error from the remote command
    * ``retcode`` — exit code (0 on success)

    :param str cmd: The shell command to run on the remote host.
    :param int timeout: Optional per-call SSH timeout in seconds.  When
        provided, overrides the connection-level ``timeout`` for this
        call only.
    :rtype: dict

    CLI Example (via resource execution module):

    .. code-block:: bash

        salt -C 'T@ssh:web-01' ssh_cmd.run 'uptime'
    """
    resource_id = _resource_id()
    override = {"timeout": timeout} if timeout is not None else None
    shell = _make_shell(resource_id, override)
    stdout, stderr, retcode = shell.exec_cmd(cmd)
    return {"stdout": stdout, "stderr": stderr, "retcode": retcode}

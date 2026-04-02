"""
State module for the ``ssh`` resource type.

Implements ``state.highstate``, ``state.sls``, and ``state.apply`` for SSH
resources by replicating the salt-ssh state-execution pipeline on the
managing minion:

1. **Compile** — ``SSHHighState`` reads state and pillar files from the
   master via the minion's ``RemoteClient``.  The resource ID is used as
   the top-file target, so only states mapped to that ID are compiled.

2. **Package** — ``prep_trans_tar`` bundles the compiled low state, all
   referenced ``salt://`` files, and the rendered pillar into a transport
   tar (``salt_state.tgz``).

3. **Execute** — The tar is SCP'd to the remote host's ``thin_dir`` and
   ``state.pkg`` is invoked via the salt-thin bundle, returning structured
   JSON results.

This mirrors what ``salt-ssh state.highstate`` does when invoked from the
master, but runs from the managing minion's process so the salt-ssh
initiator is the minion, not the master.
"""

import logging
import os
import uuid

import salt.client.ssh
import salt.client.ssh.shell
import salt.client.ssh.state
import salt.client.ssh.wrapper
import salt.defaults.exitcodes
import salt.fileclient
import salt.utils.hashutils
import salt.utils.network
import salt.utils.state
from salt.client.ssh.wrapper.state import (
    _cleanup_slsmod_low_data,
    _merge_extra_filerefs,
)
from salt.resource.ssh import CONTEXT_KEY

log = logging.getLogger(__name__)
log.info("sshresource_state: module imported, __name__=%s", __name__)

__virtualname__ = "state"
__func_alias__ = {"apply_": "apply"}


def __virtual__():
    if __opts__.get("resource_type") == "ssh":  # pylint: disable=undefined-variable
        log.info(
            "sshresource_state: LOADING for ssh resource type (opts id=%s)",
            __opts__.get("id"),
        )  # pylint: disable=undefined-variable
        return __virtualname__
    return False, "sshresource_state: only loads in an ssh-resource-type loader."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resource_id():
    return __resource__["id"]  # pylint: disable=undefined-variable


def _host_cfg():
    resource_id = _resource_id()
    return __context__[CONTEXT_KEY]["hosts"].get(
        resource_id, {}
    )  # pylint: disable=undefined-variable


def _relenv_path():
    """Return the local path of our pre-built custom relenv tarball."""
    cachedir = __opts__.get("cachedir", "")  # pylint: disable=undefined-variable
    return os.path.join(cachedir, "relenv", "linux", "x86_64", "salt-relenv.tar.xz")


def _target_opts():
    """
    Build a copy of ``__opts__`` suitable for ``SSHHighState`` and ``Single``.

    * Sets ``id`` to the resource ID so the top file matches the right host.
    * Injects ``_ssh_version`` and host-key policy from the resource config.
    * ``thin_dir`` is populated later as a side-effect of ``Single.__init__``.
    """
    resource_id = _resource_id()
    cfg = _host_cfg()
    opts = dict(__opts__)  # pylint: disable=undefined-variable
    opts["id"] = resource_id
    opts.pop("resource_type", None)
    opts["_ssh_version"] = (
        __context__.get(CONTEXT_KEY, {}).get(
            "_ssh_version"
        )  # pylint: disable=undefined-variable
        or salt.client.ssh.ssh_version()
    )
    opts["no_host_keys"] = cfg.get("no_host_keys", opts.get("no_host_keys", False))
    opts["ignore_host_keys"] = cfg.get(
        "ignore_host_keys", opts.get("ignore_host_keys", False)
    )
    if "known_hosts_file" in cfg:
        opts["known_hosts_file"] = cfg["known_hosts_file"]
    opts["relenv"] = True
    return opts


def _connection_kwargs():
    """Return SSH connection kwargs for ``Single`` from the resource config."""
    cfg = _host_cfg()
    return {
        "host": cfg["host"],
        "user": cfg.get("user", "root"),
        "port": cfg.get("port", 22),
        "passwd": cfg.get("passwd"),
        "priv": cfg.get("priv"),
        "priv_passwd": cfg.get("priv_passwd"),
        "timeout": cfg.get("timeout", 60),
        "sudo": cfg.get("sudo", False),
        "tty": cfg.get("tty", False),
        "identities_only": cfg.get("identities_only", False),
        "ssh_options": cfg.get("ssh_options"),
        "keepalive": cfg.get("keepalive", True),
        "keepalive_interval": cfg.get("keepalive_interval", 60),
        "keepalive_count_max": cfg.get("keepalive_count_max", 3),
    }


def _thin_dir():
    """
    Return the remote working directory for the salt-thin bundle.

    Mirrors the logic in ``salt.resource.ssh._thin_dir``: uses the per-host
    ``thin_dir`` config key when set, otherwise builds a path under ``/tmp/``
    (always world-writable) to avoid ``/var/tmp/`` which may be root-only.
    """
    cfg = _host_cfg()
    if "thin_dir" in cfg:
        return cfg["thin_dir"]
    fqdn_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, salt.utils.network.get_fqhostname()).hex[
        :6
    ]
    return "/tmp/.{}_{}_salt".format(cfg.get("user", "root"), fqdn_uuid)


def _seed_thin_dir(opts):
    """
    Compute ``thin_dir`` and write it into *opts* so that ``SSHHighState``
    and ``prep_trans_tar`` use a consistent, writable path.
    """
    thin = _thin_dir()
    opts["thin_dir"] = thin
    return thin


def _get_initial_pillar(opts):
    """
    Return the managing minion's rendered pillar for state compilation.

    Passing a non-None, non-empty value as ``initial_pillar`` to ``SSHHighState``
    causes ``State.__init__`` to skip ``_gather_pillar()`` (which would otherwise
    try to compile pillar for the resource ID as a regular minion).  We use the
    managing minion's own pillar — it contains the resource configuration anyway
    and avoids a spurious pillar-compile for an unknown minion ID.

    Returns ``None`` only as a last resort so the caller can decide how to handle
    missing pillar.
    """
    raw = __opts__.get("pillar")  # pylint: disable=undefined-variable
    if raw is None:
        return None
    try:
        val = raw.value()
    except AttributeError:
        val = raw
    # An empty dict is falsy in state.py's `if initial_pillar` check, which
    # would re-trigger _gather_pillar.  Return None explicitly so callers know
    # there is no cached pillar rather than silently skipping the right path.
    return val if isinstance(val, dict) and val else None


def _file_client():
    """
    Return a file client suitable for ``SSHHighState`` state compilation.

    Uses the master opts cached during ``ssh.init()`` to create an
    ``FSClient`` — a local-filesystem file client identical to the one the
    salt-ssh master uses.  This avoids creating a new authenticated network
    channel from inside a minion job thread (which has tornado IO-loop
    complications).

    Falls back to a ``RemoteClient`` if no cached master opts are available
    (e.g. on first run before a full restart).
    """
    master_opts = __context__.get(CONTEXT_KEY, {}).get(
        "master_opts"
    )  # pylint: disable=undefined-variable
    log.debug(
        "sshresource_state._file_client: master_opts cached=%s, file_roots=%s",
        master_opts is not None,
        (master_opts or {}).get("file_roots"),
    )
    if master_opts:
        return salt.fileclient.FSClient(master_opts)
    log.warning(
        "sshresource_state: no cached master opts in context, "
        "falling back to RemoteClient for file access"
    )
    return salt.fileclient.get_file_client(
        __opts__
    )  # pylint: disable=undefined-variable


# ---------------------------------------------------------------------------
# Public state functions
# ---------------------------------------------------------------------------


def highstate(test=None, **kwargs):
    """
    Apply the highstate to the targeted SSH resource.

    Compiles the highstate on the managing minion using the resource ID as the
    top-file target, packages all state files into a transport tar, SCPs the
    tar to the remote host, and runs ``state.pkg`` via the salt-thin bundle.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:node1' state.highstate
        salt -C 'T@ssh:node1' state.highstate test=True
    """
    opts = _target_opts()
    _seed_thin_dir(opts)

    initial_pillar = _get_initial_pillar(opts)
    pillar_override = kwargs.get("pillar")
    extra_filerefs = kwargs.get("extra_filerefs", "")

    opts = salt.utils.state.get_sls_opts(opts, **kwargs)
    if test is None:
        test = opts.get("test", False)
    opts["test"] = test

    file_client = _file_client()
    log.debug(
        "sshresource_state.highstate: file_client=%s initial_pillar_type=%s",
        type(file_client).__name__,
        type(initial_pillar).__name__,
    )
    log.debug(
        "sshresource_state.highstate: file_client.envs()=%s",
        file_client.envs(),
    )
    # SSHHighState.__exit__ calls file_client.destroy(), so no separate finally needed.
    with salt.client.ssh.state.SSHHighState(
        opts,
        pillar_override,
        __salt__,  # pylint: disable=undefined-variable
        file_client,
        initial_pillar=initial_pillar,
    ) as st_:
        try:
            pillar = st_.opts["pillar"].value()
        except AttributeError:
            pillar = st_.opts["pillar"]

        st_.push_active()
        chunks_or_errors = st_.compile_low_chunks()
        log.debug(
            "sshresource_state.highstate: compile_low_chunks returned %s",
            chunks_or_errors,
        )

        for chunk in chunks_or_errors:
            if not isinstance(chunk, dict):
                return chunks_or_errors

        file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks_or_errors,
            _merge_extra_filerefs(
                extra_filerefs,
                opts.get("extra_filerefs", ""),
            ),
        )
        _cleanup_slsmod_low_data(chunks_or_errors)
        trans_tar = salt.client.ssh.state.prep_trans_tar(
            file_client,
            chunks_or_errors,
            file_refs,
            pillar,
            _resource_id(),
        )

    return _exec_state_pkg(opts, trans_tar, test)


def sls(mods, saltenv="base", test=None, **kwargs):
    """
    Apply one or more state SLS files to the targeted SSH resource.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:node1' state.sls node1
        salt -C 'T@ssh:node1' state.sls node1,common test=True
    """
    opts = _target_opts()
    _seed_thin_dir(opts)

    initial_pillar = _get_initial_pillar(opts)
    pillar_override = kwargs.get("pillar")
    extra_filerefs = kwargs.get("extra_filerefs", "")

    opts = salt.utils.state.get_sls_opts(opts, **kwargs)
    if test is None:
        test = opts.get("test", False)
    opts["test"] = test

    if isinstance(mods, str):
        mods = [m.strip() for m in mods.split(",") if m.strip()]

    file_client = _file_client()
    with salt.client.ssh.state.SSHHighState(
        opts,
        pillar_override,
        __salt__,  # pylint: disable=undefined-variable
        file_client,
        initial_pillar=initial_pillar,
    ) as st_:
        try:
            pillar = st_.opts["pillar"].value()
        except AttributeError:
            pillar = st_.opts["pillar"]

        st_.push_active()
        high_data, errors = st_.render_highstate({saltenv: mods})
        if kwargs.get("exclude"):
            exclude = kwargs["exclude"]
            if isinstance(exclude, str):
                exclude = exclude.split(",")
            high_data.setdefault("__exclude__", []).extend(exclude)

        high_data, ext_errors = st_.state.reconcile_extend(high_data)
        errors += ext_errors
        errors += st_.state.verify_high(high_data)
        if errors:
            return errors

        high_data, req_in_errors = st_.state.requisite_in(high_data)
        errors += req_in_errors
        high_data = st_.state.apply_exclude(high_data)
        if errors:
            return errors

        chunks, errors = st_.state.compile_high_data(high_data)
        if errors:
            return errors

        file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                extra_filerefs,
                opts.get("extra_filerefs", ""),
            ),
        )
        _cleanup_slsmod_low_data(chunks)
        trans_tar = salt.client.ssh.state.prep_trans_tar(
            file_client,
            chunks,
            file_refs,
            pillar,
            _resource_id(),
        )

    return _exec_state_pkg(opts, trans_tar, test)


def apply_(mods=None, **kwargs):
    """
    Apply states to the SSH resource — ``state.highstate`` if no mods are
    given, ``state.sls`` otherwise.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:node1' state.apply
        salt -C 'T@ssh:node1' state.apply node1
    """
    if mods:
        return sls(mods, **kwargs)
    return highstate(**kwargs)


# ---------------------------------------------------------------------------
# Shared execution helper
# ---------------------------------------------------------------------------


def _exec_state_pkg(opts, trans_tar, test):
    """
    SCP ``trans_tar`` to the remote host and run ``state.pkg`` via the
    salt-thin bundle.  Cleans up the local tar file regardless of outcome.

    Returns the state result dict directly (what the minion dispatcher
    expects) rather than the full ``{"local": {"return": ...}}`` envelope.
    """
    try:
        trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, opts["hash_type"])
        cmd = "state.pkg {thin_dir}/salt_state.tgz test={test} pkg_sum={pkg_sum} hash_type={hash_type}".format(
            thin_dir=opts["thin_dir"],
            test=test,
            pkg_sum=trans_tar_sum,
            hash_type=opts["hash_type"],
        )
        single = salt.client.ssh.Single(
            opts,
            cmd,
            _resource_id(),
            thin=_relenv_path(),
            thin_dir=opts["thin_dir"],
            **_connection_kwargs(),
        )
        single.shell.send(trans_tar, "{}/salt_state.tgz".format(opts["thin_dir"]))
        stdout, stderr, retcode = single.cmd_block()
    finally:
        try:
            os.remove(trans_tar)
        except OSError:
            pass

    # parse_ret returns data["local"] = {"jid": ..., "return": {states}, "retcode": N}
    # The minion dispatcher expects the state dict directly (not the envelope).
    envelope = salt.client.ssh.wrapper.parse_ret(stdout, stderr, retcode)
    if isinstance(envelope, dict) and "return" in envelope:
        ret = envelope["return"]
        # Propagate non-zero retcode into context so caller can signal failure.
        remote_retcode = envelope.get("retcode", 0)
        if remote_retcode:
            __context__["retcode"] = (
                remote_retcode  # pylint: disable=undefined-variable
            )
        return ret
    return envelope

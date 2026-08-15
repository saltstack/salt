"""
Cgroup-aware memory-headroom helpers.

Shared by opt-in queue-admission memory checks:

* ``salt/minion.py`` — legacy queue-admission check
  (see :conf_minion:`minion_memory_headroom`)
* ``salt/channel/server.py`` MasterPubServerChannel — event-bus fan-out
  backpressure (see :conf_master:`event_publisher_memory_headroom`)
* ``salt/transport/zeromq.py`` MWorkerQueue pooled device — request-accept
  backpressure (see :conf_master:`mworker_queue_memory_headroom`)

The reference-memory resolution precedence and parser semantics match the
minion-side implementation added in issue #69884 so operators can reason
about all three subjects with a single mental model.
"""

import logging
import os

import salt.utils.files
import salt.utils.stringutils

log = logging.getLogger(__name__)


# Paths for cgroup-aware memory-limit detection. Module-level so tests can
# monkeypatch to a synthetic cgroup filesystem laid out under tmp_path.
_CGROUP_PROC_PATH = "/proc/self/cgroup"
_CGROUP_FS_ROOT = "/sys/fs/cgroup"

# cgroup v1 kernel "no limit" sentinel is (LONG_MAX / PAGE_SIZE) * PAGE_SIZE,
# i.e. ~9.22 EB. We compare against 2**62 (~4.6 EB) which is comfortably
# above any real limit but below the sentinel — anything at or above this
# is treated as "unlimited".
_CGROUP_V1_UNLIMITED_THRESHOLD = 1 << 62


def _read_cgroup_file(path):
    """
    Read a cgroup pseudo-file. Return the stripped contents on success or
    ``None`` on any error. Cgroup files are stable on Linux; we intentionally
    swallow every failure (missing file, permission denied, non-Linux host,
    exotic mount layout) and let the caller fall back to system-wide memory.
    """
    try:
        with salt.utils.files.fopen(path, "r") as fh:
            return fh.read().strip()
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _parse_self_cgroup(content):
    """
    Parse ``/proc/self/cgroup`` content. Return a tuple
    ``(v2_path, v1_memory_path)`` where each element is a string starting
    with ``/`` or ``None`` if that hierarchy isn't present.

    v2 line format:  ``0::/system.slice/salt-minion.service``
    v1 line format:  ``5:memory:/system.slice/salt-minion.service``
    """
    v2_path = None
    v1_memory_path = None
    if not content:
        return v2_path, v1_memory_path
    for line in content.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        hierarchy_id, controllers, cgroup_path = parts
        if hierarchy_id == "0" and controllers == "":
            v2_path = cgroup_path or "/"
        elif "memory" in controllers.split(","):
            v1_memory_path = cgroup_path or "/"
    return v2_path, v1_memory_path


def _detect_cgroup_memory(proc_path=None, fs_root=None):
    """
    Detect the memory limit and current usage that apply to this process
    via cgroups.

    Returns ``(limit_bytes, used_bytes, source)`` where ``source`` is
    ``"cgroup-v2"``, ``"cgroup-v1"``, or ``None``. When no cgroup limit
    applies (unified hierarchy reports ``"max"``, v1 reports the unlimited
    sentinel, or the files can't be read) returns ``(None, None, None)``.

    Any I/O or parse failure is logged at DEBUG and swallowed — this helper
    must never raise into the caller.
    """
    proc_path = proc_path or _CGROUP_PROC_PATH
    fs_root = fs_root or _CGROUP_FS_ROOT
    content = _read_cgroup_file(proc_path)
    if content is None:
        log.debug(
            "No cgroup information at %s; skipping cgroup memory detection", proc_path
        )
        return None, None, None
    v2_path, v1_memory_path = _parse_self_cgroup(content)

    # Prefer cgroup v2 (unified hierarchy) when both are present. On a
    # v1 host the v2 line will be absent; on a hybrid host the v2 line
    # exists but has no controllers, in which case v2 memory files simply
    # won't be found and we'll fall through to v1.
    if v2_path is not None:
        max_str = _read_cgroup_file(
            os.path.join(fs_root, v2_path.lstrip("/"), "memory.max")
        )
        cur_str = _read_cgroup_file(
            os.path.join(fs_root, v2_path.lstrip("/"), "memory.current")
        )
        if max_str is not None and cur_str is not None and max_str != "max":
            try:
                limit = int(max_str)
                used = int(cur_str)
                return limit, used, "cgroup-v2"
            except ValueError:
                log.debug(
                    "Malformed cgroup v2 memory.max/current: %r / %r", max_str, cur_str
                )

    if v1_memory_path is not None:
        limit_str = _read_cgroup_file(
            os.path.join(
                fs_root, "memory", v1_memory_path.lstrip("/"), "memory.limit_in_bytes"
            )
        )
        usage_str = _read_cgroup_file(
            os.path.join(
                fs_root, "memory", v1_memory_path.lstrip("/"), "memory.usage_in_bytes"
            )
        )
        if limit_str is not None and usage_str is not None:
            try:
                limit = int(limit_str)
                used = int(usage_str)
                if limit < _CGROUP_V1_UNLIMITED_THRESHOLD:
                    return limit, used, "cgroup-v1"
            except ValueError:
                log.debug(
                    "Malformed cgroup v1 memory.limit/usage: %r / %r",
                    limit_str,
                    usage_str,
                )

    return None, None, None


def parse_size(value):
    """
    Parse a size expressed as int-bytes or a string (``"5G"``, ``"500M"``,
    or plain digits). Return an int number of bytes, or ``None`` on any
    parse failure. Zero and negatives are treated as invalid.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int — reject to avoid True->1-byte surprise.
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = int(text)
        if parsed > 0:
            return parsed
    except ValueError:
        pass
    bytes_ = salt.utils.stringutils.human_to_bytes(text)
    return bytes_ if bytes_ > 0 else None


def parse_headroom(value, reference):
    """
    Convert a ``*_memory_headroom`` opt to an absolute byte count relative
    to ``reference``. Accepts a percentage string (``"5%"``), a size string
    / int (``"500M"``, ``5368709120``), or ``None``. Returns ``None`` on
    any parse failure or when ``value`` is ``None``.
    """
    if value is None:
        return None
    if isinstance(value, str) and value.strip().endswith("%"):
        text = value.strip()[:-1].strip()
        try:
            pct = float(text)
        except ValueError:
            log.debug("Unparseable percentage in memory_headroom: %r", value)
            return None
        if not 0 < pct <= 100:
            log.debug("memory_headroom percentage out of range: %r", value)
            return None
        return int(reference * pct / 100.0)
    bytes_ = parse_size(value)
    if bytes_ is None:
        log.debug("Unparseable memory_headroom: %r", value)
    return bytes_


def resolve_memory_reference(max_opt):
    """
    Resolve the reference "total memory available" and the current used
    bytes.

    Precedence:
        1. ``max_opt`` if set (int bytes or size string).
        2. cgroup v2 ``memory.max`` (with ``memory.current`` for used).
        3. cgroup v1 ``memory.limit_in_bytes`` (with ``memory.usage_in_bytes``).
        4. ``psutil.virtual_memory().total`` (with ``.used``).

    Returns ``(reference_bytes, used_bytes, source)`` where ``source`` is
    one of ``"config"``, ``"cgroup-v2"``, ``"cgroup-v1"``, ``"system"``.
    """
    import psutil  # local import mirrors the caller's guarded pattern

    if max_opt is not None:
        configured = parse_size(max_opt)
        if configured is not None:
            vm = psutil.virtual_memory()
            # If the operator's cap is <= system total we assume they're
            # describing a per-process cap and use it as the reference; we
            # still need a "used" number so we consult cgroup usage first
            # (accurate for the process) then fall back to system used.
            cg_limit, cg_used, cg_source = _detect_cgroup_memory()
            if cg_source is not None:
                used = cg_used
            else:
                used = vm.used
            return configured, used, "config"
        log.debug("Unparseable memory_max: %r", max_opt)

    cg_limit, cg_used, cg_source = _detect_cgroup_memory()
    if cg_source is not None:
        return cg_limit, cg_used, cg_source

    vm = psutil.virtual_memory()
    return vm.total, vm.used, "system"


def has_memory_headroom(opts, headroom_opt_key, max_opt_key, subject=None):
    """
    Return True if the process has enough free memory to accept more work.

    ``opts`` is the Salt options dict (either master or minion). The two
    key names identify the config entries this caller uses -- e.g. for the
    master EventPublisher::

        has_memory_headroom(
            self.opts,
            "event_publisher_memory_headroom",
            "event_publisher_memory_max",
            subject="EventPublisher",
        )

    Semantics match the minion-side check added in #69884 / #70038:

    * If neither opt is set, returns True (no check configured).
    * Otherwise resolves the reference total via
      :func:`resolve_memory_reference` (opt > cgroup v2 > cgroup v1 >
      psutil) and returns True iff
      ``used + headroom_bytes <= reference``.

    ``subject`` is a short label included in the WARNING message when
    headroom is exhausted (e.g. ``"EventPublisher"``); it defaults to
    ``headroom_opt_key`` if not given.
    """
    try:
        # Presence check only -- resolve_memory_reference imports it below.
        import psutil  # pylint: disable=import-outside-toplevel,unused-import,unused-variable  # noqa: F401
    except ImportError:
        # No psutil, no check -- permissive by default.
        return True

    headroom_opt = opts.get(headroom_opt_key)
    max_opt = opts.get(max_opt_key)

    if headroom_opt is None and max_opt is None:
        return True

    try:
        reference, used, source = resolve_memory_reference(max_opt)
        headroom_bytes = parse_headroom(headroom_opt, reference)
        if headroom_bytes is None:
            # Parse failure already logged at DEBUG; fall back to a 5%
            # headroom on the resolved reference so operator intent (they
            # asked for cgroup-aware behavior) is honored.
            headroom_bytes = int(reference * 0.05)

        if used + headroom_bytes > reference:
            log.warning(
                "%s memory headroom exhausted "
                "(used %s of %s, headroom %s, source %s); pausing accept.",
                subject or headroom_opt_key,
                used,
                reference,
                headroom_bytes,
                source,
            )
            return False
        return True
    except Exception:  # pylint: disable=broad-exception-caught
        # Never raise into the caller — the whole point of the check is
        # to be a safety valve, not a new failure mode.
        log.debug(
            "Memory headroom check failed for %s; permitting accept",
            subject or headroom_opt_key,
            exc_info=True,
        )
        return True

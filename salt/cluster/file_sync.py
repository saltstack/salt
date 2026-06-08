"""
Helpers for replicating ``file_roots`` and ``pillar_roots`` between
cluster masters that don't share a filesystem.

The cluster join-reply embeds the responder's current local state-tree
contents alongside the keys dump.  A late-joining master applies the
contents into its own local roots before becoming a Raft learner so it
can serve states/pillars it would otherwise know nothing about.

Used by :mod:`salt.channel.server` for the join handshake and (later)
by a ``cluster.sync_roots`` runner for ad-hoc updates after roots are
edited on a peer.
"""

import logging
import os
from pathlib import Path

import salt.utils.files

log = logging.getLogger(__name__)

# File and directory names skipped when collecting a roots tree.
# These are version-control artefacts and editor-temporary files that
# we never want to ship to peers.
_SKIP_DIR_NAMES = frozenset({".git", ".hg", ".svn", "__pycache__", ".tox"})


def _is_skipped_path(rel_parts):
    """Return ``True`` if any path component is on the skip list."""
    return any(part in _SKIP_DIR_NAMES for part in rel_parts)


def collect_root_tree(roots_map):
    """
    Build a wire-friendly snapshot of a ``file_roots``/``pillar_roots``
    mapping.

    :param roots_map: ``{env: [path, path, ...]}`` from ``opts``.
    :return: ``{env: [{"path": rel, "mode": int, "data": bytes}, ...]}``.

    Only regular files are included; symlinks, sockets and unreadable
    entries are skipped.  Multiple roots for the same env are flattened
    in declaration order — earlier roots win on path conflicts.
    """
    out = {}
    for env, paths in (roots_map or {}).items():
        files = []
        seen = set()
        for root in paths or []:
            root_p = Path(root)
            if not root_p.is_dir():
                continue
            for sub in root_p.rglob("*"):
                try:
                    if sub.is_symlink() or not sub.is_file():
                        continue
                    rel_parts = sub.relative_to(root_p).parts
                except (OSError, ValueError):
                    continue
                if not rel_parts or _is_skipped_path(rel_parts):
                    continue
                rel = "/".join(rel_parts)
                if rel in seen:
                    continue
                try:
                    data = sub.read_bytes()
                    mode = sub.stat().st_mode & 0o777
                except OSError as exc:
                    log.warning("file_sync: skipping unreadable %s: %s", sub, exc)
                    continue
                files.append({"path": rel, "mode": mode, "data": data})
                seen.add(rel)
        if files:
            out[env] = files
    return out


def apply_root_tree(roots_map, dump):
    """
    Materialise *dump* (from :func:`collect_root_tree`) under the local
    ``roots_map``.

    :param roots_map: ``{env: [path, path, ...]}`` from ``opts``.  Files
        for env *e* are written under ``roots_map[e][0]``; envs that are
        absent or empty are skipped.
    :param dump: the snapshot dict to apply.
    :return: number of files written.
    """
    written = 0
    for env, files in (dump or {}).items():
        roots = (roots_map or {}).get(env)
        if not roots:
            log.debug(
                "file_sync: env %r not configured locally; skipping %d files",
                env,
                len(files),
            )
            continue
        target = Path(roots[0])
        target.mkdir(parents=True, exist_ok=True)
        for entry in files:
            rel = entry.get("path") if isinstance(entry, dict) else None
            data = entry.get("data") if isinstance(entry, dict) else None
            mode = entry.get("mode", 0o644) if isinstance(entry, dict) else 0o644
            if not rel or data is None:
                continue
            # msgpack round-trip via salt.payload may turn bytes back into
            # str; coerce so binary files round-trip cleanly.
            if isinstance(data, str):
                data = data.encode("utf-8", errors="surrogateescape")
            dst = target / rel
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                with salt.utils.files.fopen(dst, "wb") as fp:
                    fp.write(data)
                os.chmod(dst, mode)
                written += 1
            except OSError as exc:
                log.warning("file_sync: write failed for %s: %s", dst, exc)
    return written

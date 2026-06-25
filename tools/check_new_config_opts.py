"""
Verify that every config option declared in ``salt/config/__init__.py``
is documented in the matching ``conf/`` sample and in
``doc/ref/configuration/`` reference page.

This is the enforcement side of the "new option needs documentation"
process described in ``CONTRIBUTING.rst`` (#59908). It is intended
to run as a pre-commit hook and as a standalone CLI:

::

    /path/to/venv/bin/python tools/check_new_config_opts.py
    /path/to/venv/bin/python tools/check_new_config_opts.py --baseline /tmp/old-keys.txt

Exit codes:

* ``0`` — every key in the runtime opts dicts is documented in both
  the matching ``conf/<daemon>`` sample and the matching
  ``doc/ref/configuration/<daemon>.rst`` reference page.
* ``1`` — at least one key is undocumented. The CLI prints one line
  per offending key as ``key: missing in conf|missing in ref`` so
  the pre-commit output is easy to scan.

The check inspects three sources:

* ``DEFAULT_MASTER_OPTS`` / ``DEFAULT_MINION_OPTS`` /
  ``DEFAULT_PROXY_MINION_OPTS`` from ``salt/config/__init__.py``.
* ``conf/master`` / ``conf/minion`` / ``conf/proxy`` (commented YAML
  is matched as ``#?<key>:`` at the start of a line).
* ``doc/ref/configuration/master.rst`` /
  ``doc/ref/configuration/minion.rst`` /
  ``doc/ref/configuration/proxy.rst``
  (the option is documented when it appears in a
  ``.. conf_master::`` / ``.. conf_minion::`` directive).

A key can opt out of the check by placing the marker
``# noqa: undocumented`` on the same line that adds it to the opts
dict. The marker is logged but not enforced.

The ``--baseline`` flag takes a path to a previously-emitted list of
keys; only keys *not* in that baseline are checked. This is the form
the pre-commit hook uses to gate net-new options without forcing the
many pre-existing undocumented options to be backfilled in the same
PR.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "salt" / "config" / "__init__.py"

CONF_FILE = {
    "master": REPO_ROOT / "conf" / "master",
    "minion": REPO_ROOT / "conf" / "minion",
    "proxy": REPO_ROOT / "conf" / "proxy",
}
REF_FILE = {
    "master": REPO_ROOT / "doc" / "ref" / "configuration" / "master.rst",
    "minion": REPO_ROOT / "doc" / "ref" / "configuration" / "minion.rst",
    "proxy": REPO_ROOT / "doc" / "ref" / "configuration" / "proxy.rst",
}

OPTS_DICT_NAME = {
    "master": "DEFAULT_MASTER_OPTS",
    "minion": "DEFAULT_MINION_OPTS",
    "proxy": "DEFAULT_PROXY_MINION_OPTS",
}

NOQA_MARKER = "# noqa: undocumented"

CONF_KEY_RE = re.compile(r"^#?\s*([A-Za-z_][A-Za-z0-9_.]*)\s*:")
REF_DIRECTIVE_RE = re.compile(r"^\.\.\s+conf_(master|minion|proxy)::\s+(\S+)\s*$")


def parse_opts_dict(source: str, dict_name: str) -> tuple[set[str], set[str]]:
    """
    Return ``(documented_keys, noqa_keys)`` for the dictionary named
    ``dict_name`` in ``source``.

    A key is "noqa" when its declaration line ends with the literal
    ``# noqa: undocumented`` marker; the check skips it but the
    caller can still log it.
    """
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == dict_name:
                    target = node.value
                    break
        if target is not None:
            break
    if target is None or not isinstance(target, ast.Dict):
        return set(), set()
    src_lines = source.splitlines()
    keys: set[str] = set()
    noqa: set[str] = set()
    for key_node in target.keys:
        if not isinstance(key_node, ast.Constant) or not isinstance(
            key_node.value, str
        ):
            continue
        keys.add(key_node.value)
        # Look at the source line of this key; if it carries the marker
        # the key is opting out.
        line_no = getattr(key_node, "lineno", None)
        if line_no is None:
            continue
        line = src_lines[line_no - 1]
        if NOQA_MARKER in line:
            noqa.add(key_node.value)
    return keys, noqa


def parse_conf_file(path: pathlib.Path) -> set[str]:
    """
    Return the set of option names that appear as ``key:`` or
    ``#key:`` at the start of a logical line in a Salt sample config
    file.
    """
    if not path.exists():
        return set()
    found: set[str] = set()
    with path.open() as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            # Skip pure-comment lines like ``# ===== Section =====``
            # and indented YAML values.
            if line.startswith(" "):
                continue
            match = CONF_KEY_RE.match(line)
            if not match:
                continue
            found.add(match.group(1))
    return found


def parse_ref_file(path: pathlib.Path) -> set[str]:
    """
    Return the set of option names documented in a configuration
    reference page via ``.. conf_<daemon>:: <name>`` directives.
    """
    if not path.exists():
        return set()
    found: set[str] = set()
    with path.open() as fh:
        for raw_line in fh:
            match = REF_DIRECTIVE_RE.match(raw_line.rstrip("\n"))
            if match:
                found.add(match.group(2))
    return found


def check_daemon(daemon: str, source: str, baseline: set[str]) -> list[str]:
    """
    Return a list of ``"<key>: missing in <where>"`` strings — one
    per undocumented key. Empty list means clean.
    """
    keys, noqa = parse_opts_dict(source, OPTS_DICT_NAME[daemon])
    conf_keys = parse_conf_file(CONF_FILE[daemon])
    ref_keys = parse_ref_file(REF_FILE[daemon])
    issues: list[str] = []
    for key in sorted(keys):
        if key in noqa:
            continue
        if key in baseline:
            continue
        if key not in conf_keys:
            issues.append(f"{daemon}:{key}: missing in {CONF_FILE[daemon]}")
        if key not in ref_keys:
            issues.append(f"{daemon}:{key}: missing in {REF_FILE[daemon]}")
    return issues


def run(
    config_source: str = None,
    daemons: tuple[str, ...] = ("master", "minion", "proxy"),
    baseline: set[str] = None,
) -> list[str]:
    """
    Library entry point — returns the same list of issue strings as
    the CLI emits. ``config_source`` lets tests inject a synthetic
    ``salt/config/__init__.py`` body without touching the real file.
    """
    if config_source is None:
        config_source = CONFIG_FILE.read_text()
    baseline = baseline or set()
    issues: list[str] = []
    for daemon in daemons:
        issues.extend(check_daemon(daemon, config_source, baseline))
    return issues


def _load_baseline(path: pathlib.Path) -> set[str]:
    if path is None:
        return set()
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def main(argv: list[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=pathlib.Path,
        default=None,
        help=(
            "Path to a file of pre-existing undocumented keys to ignore. "
            "One key per line; comments start with '#'."
        ),
    )
    parser.add_argument(
        "--daemon",
        choices=("master", "minion", "proxy"),
        action="append",
        help="Limit the check to one or more daemons. Default: all.",
    )
    args = parser.parse_args(argv)
    daemons = tuple(args.daemon) if args.daemon else ("master", "minion", "proxy")
    baseline = _load_baseline(args.baseline)
    issues = run(daemons=daemons, baseline=baseline)
    for issue in issues:
        print(issue)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

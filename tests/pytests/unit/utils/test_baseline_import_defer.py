"""
Regression tests: heavy or platform-specific modules must not be imported
when ``salt.config.minion_config`` is loaded on a non-Windows platform.

Historically the baseline utility modules that every minion process
loads pulled in several categories of expensive Python code at
module-import time even though every use-site was gated by role
(``__role == "master"``) or platform (``salt.utils.platform.is_windows()``):

* Windows-only helpers: ``salt.utils.win_functions`` /
  ``salt.utils.win_network`` / ``salt.utils.win_reg`` /
  ``salt.utils.win_dacl`` / ``salt.utils.win_chcp``.  On Linux these are
  importable (their inner ``import win32...`` guards fall through) so
  they were loaded even though every call site is Windows-guarded.

* Master-role helpers: ``salt.master`` and ``salt.utils.master``.
  ``salt.master`` was imported by ``salt.transport.tcp`` with zero use
  sites; ``salt.utils.master`` was imported by ``salt.pillar`` (zero use
  sites) and ``salt.utils.schedule`` (used only in the ``__role ==
  "master"`` branch of one method).

* The state compiler: ``salt.state`` was pulled in by
  ``salt.utils.state`` for two functions (``search_onfail_requisites`` /
  ``check_onfail_requisites``) that are not on the minion baseline path.

* Optional HTTP transitive: ``requests`` and ``certifi`` were imported
  eagerly by ``salt.utils.http`` but are only exercised when a caller
  opts into ``backend="requests"`` or explicitly asks for a session.

These tests run in *fresh* Python subprocesses (so the test harness's
own imports don't taint ``sys.modules``) and assert the modules above
stay unloaded on the minion baseline on non-Windows.
"""

import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="This regression only applies to non-Windows minion processes",
)


WIN_ONLY_MODULES = (
    "salt.utils.win_dacl",
    "salt.utils.win_reg",
    "salt.utils.win_chcp",
    "salt.utils.win_functions",
    "salt.utils.win_network",
    "salt.utils.winapi",
    "salt.platform.win",
)

MASTER_ROLE_MODULES = (
    "salt.master",
    "salt.utils.master",
)

STATE_COMPILER_MODULES = ("salt.state",)

OPTIONAL_HTTP_MODULES = ("requests", "certifi")

# Modules that should NEVER be imported when the minion baseline
# initializes ``salt.config``.
BASELINE_MUST_NOT_LOAD = (
    WIN_ONLY_MODULES
    + MASTER_ROLE_MODULES
    + STATE_COMPILER_MODULES
    + OPTIONAL_HTTP_MODULES
)


def _run_probe(preload_code, watch=BASELINE_MUST_NOT_LOAD):
    """
    Run ``preload_code`` in a fresh interpreter and return the set of
    modules from ``watch`` that are present in ``sys.modules`` afterwards.
    """
    script = textwrap.dedent(
        f"""
        import sys
        {preload_code}
        for name in {watch!r}:
            if name in sys.modules:
                print(name)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line.strip()}


def test_minion_config_does_not_import_heavy_modules(tmp_path):
    """
    Loading a minion config in a fresh interpreter must not pull in any
    of the Windows-only helpers, master-role helpers, the state
    compiler, or the optional ``requests``/``certifi`` HTTP transitive.
    """
    minion_cfg = tmp_path / "minion"
    minion_cfg.write_text("master: localhost\n")
    loaded = _run_probe(
        f"import salt.config; salt.config.minion_config({str(minion_cfg)!r})"
    )
    assert (
        not loaded
    ), f"Heavy modules leaked into Linux minion baseline: {sorted(loaded)}"


@pytest.mark.parametrize(
    "target",
    [
        # Windows-utils defers
        "salt.utils.atomicfile",
        "salt.utils.args",
        "salt.syspaths",
        "salt.utils.parsers",
        "salt.utils.user",
        "salt.utils.network",
        # Master-role / state-compiler / http defers
        "salt.transport.tcp",
        "salt.pillar",
        "salt.utils.schedule",
        "salt.modules.mine",
        "salt.utils.state",
        "salt.utils.http",
    ],
)
def test_baseline_util_does_not_import_heavy_helpers(target):
    """
    Importing any of the baseline utils that a minion process typically
    loads must not drag in Windows-only helpers, master-role helpers,
    the state compiler, or the ``requests``/``certifi`` chain on Linux.
    """
    loaded = _run_probe(f"import {target}")
    assert (
        not loaded
    ), f"{target} leaked heavy modules on Linux minion baseline: {sorted(loaded)}"

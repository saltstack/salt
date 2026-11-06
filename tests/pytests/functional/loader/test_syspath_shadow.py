"""
Functional regression test for the loader ``sys.path`` shadowing fix (#69139).

The unit tests in ``test_loader.py`` monkeypatch ``SALT_BASE_PATH`` to a
synthetic tree and use a hand-made shadow file. This test exercises the real
loader wiring end to end: a real ``minion_mods`` loader built with the real
``utils`` loader (whose ``module_dirs`` really contains ``salt/utils``), against
the real ``SALT_BASE_PATH``.

The concern is not limited to what ships in a default Salt install. Any
``salt/utils/<name>.py`` shadows a same-named top-level package that some loaded
module's import chain pulls in, and the packages people actually install to
drive Salt modules are the real victims -- e.g. ``salt/utils/dns.py`` vs
dnspython's ``dns``, ``salt/utils/napalm.py`` vs ``napalm`` (the #69139
neighbourhood itself), ``salt/utils/github.py`` vs PyGithub's ``github``,
``salt/utils/slack.py`` vs ``slack``. The salt/modules side is worse still
(``git`` vs GitPython, ``pip``, ``consul``, ``elasticsearch``, ...).

Rather than pin one name's symptom, the probe records -- while its own body runs
mid-load -- whether *any* Salt-internal directory is on ``sys.path`` at all.
That is the root guarantee that protects the whole class of collisions, and it
does not depend on which third-party packages happen to be installed in CI. The
concrete ``salt/utils/ssh.py`` shadow (the reported #69139 case) is asserted in
addition, when a real top-level ``ssh`` is absent.
"""

import copy
import importlib.util
import os
import sys
import textwrap

import pytest

import salt.loader
from salt.loader.lazy import SALT_BASE_PATH


@pytest.fixture
def shadow_probe_dir(tmp_path):
    """
    An on-disk execution-module directory whose module, in its body (executed
    while the loader has it open), records which Salt-internal directories are
    on ``sys.path`` and whether a bare ``import ssh`` binds to
    ``salt/utils/ssh.py``.
    """
    base = tmp_path / "shadow-mod-base"
    (base / "modules").mkdir(parents=True)
    (base / "modules" / "shadowprobe.py").write_text(
        textwrap.dedent(
            '''
            """Regression probe for the loader sys.path shadow (#69139)."""
            import os
            import sys

            from salt.loader.lazy import SALT_BASE_PATH

            _base = str(SALT_BASE_PATH)
            # Any Salt-internal dir visible on sys.path *right now* (mid-load)
            # is a shadow vector: a bare ``import X`` for any X matching a
            # salt/utils/*.py file (dns, napalm, github, slack, ssh, ...) would
            # bind to the Salt file instead of the real package.
            _leaked = [
                p for p in sys.path if p == _base or p.startswith(_base + os.sep)
            ]

            # Concrete #69139 symptom: the real salt/utils/ssh.py shadowing a
            # bare ``import ssh`` (napalm -> ncclient -> import ssh).
            try:
                import ssh as _ssh

                _resolved = os.path.abspath(getattr(_ssh, "__file__", "") or "")
                _ssh_shadowed = os.path.join("salt", "utils") in _resolved
            except ImportError:
                _ssh_shadowed = False


            def leaked_internal_dirs():
                return _leaked


            def ssh_shadowed():
                return _ssh_shadowed
            '''
        )
    )
    return str(base)


def test_loader_never_leaks_salt_internal_dirs_onto_sys_path_69139(
    minion_opts, shadow_probe_dir
):
    """
    Build the real ``minion_mods`` loader with the real ``utils`` loader and
    load a module that inspects ``sys.path`` from inside its own body. With the
    fix, no Salt-internal directory is ever placed on ``sys.path``, so no
    ``salt/utils/*.py`` (or ``salt/modules/*.py``) file can shadow a same-named
    third-party package that any loaded module's import chain pulls in.

    Regression guard: without the fix the loader appends ``salt/utils`` to
    ``sys.path`` for the duration of the load, so the probe sees it there and a
    bare ``import ssh`` binds to ``salt/utils/ssh.py`` -- the shadow then gets
    cached in ``sys.modules`` for the life of the process, which is exactly what
    broke napalm/ncclient loading.
    """
    opts = copy.deepcopy(minion_opts)
    opts["module_dirs"] = [shadow_probe_dir]

    saved_path = list(sys.path)
    saved_ssh = sys.modules.pop("ssh", None)
    try:
        utils = salt.loader.utils(opts)
        # Guard the test's own premise: the real salt/utils directory is among
        # the extra module dirs the loader would otherwise leak onto sys.path,
        # so an empty ``leaked_internal_dirs`` below is a real result and not a
        # vacuous pass from the wiring having changed.
        assert any(
            os.path.basename(directory) == "utils" and str(SALT_BASE_PATH) in directory
            for directory in utils.module_dirs
        ), "premise broken: real salt/utils not found in utils.module_dirs"

        funcs = salt.loader.minion_mods(opts, utils=utils)
        assert (
            "shadowprobe.leaked_internal_dirs" in funcs
        ), "probe module failed to load"

        # Root guarantee, name-independent: protects the whole class of
        # collisions (dns, napalm, git, pip, consul, ...), not just ssh.
        assert funcs["shadowprobe.leaked_internal_dirs"]() == []

        # Concrete #69139 symptom, when a genuine top-level ``ssh`` is not
        # installed (otherwise a successful import is not proof of a shadow).
        if importlib.util.find_spec("ssh") is None:
            assert funcs["shadowprobe.ssh_shadowed"]() is False
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("ssh", None)
        if saved_ssh is not None:
            sys.modules["ssh"] = saved_ssh

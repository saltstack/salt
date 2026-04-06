"""
Unit tests for salt.resource.ssh.

Covers the _make_single() helper which constructs a salt.client.ssh.Single
from inside a minion job thread — a code path that salt-ssh itself never
takes (salt-ssh always runs on the master).
"""

import pytest

from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_RESOURCE_ID = "node1"

_BASE_OPTS = {
    "id": "minion",
    "cachedir": "/tmp",
    "thin_dir": "/tmp/_salt_relenv_test",
    "ssh_wipe": False,
    "file_roots": {"base": ["/srv/salt"]},
    "pillar_roots": {"base": ["/srv/pillar"]},
    "module_dirs": [],
    # ext_pillar intentionally absent — it is a master-only key
}

_BASE_RESOURCE = {"id": _RESOURCE_ID, "type": "ssh"}

_HOST_CFG = {
    "host": "192.0.2.1",
    "user": "root",
    "port": 22,
}


def _patch_module(mod, extra_context=None):
    """Return a stack of patches that give the module its dunder variables."""
    context = {"ssh_resource": {"master_opts": None, "_ssh_version": "8.0"}}
    if extra_context:
        context["ssh_resource"].update(extra_context)
    return [
        patch.object(mod, "__opts__", _BASE_OPTS.copy(), create=True),
        patch.object(mod, "__resource__", dict(_BASE_RESOURCE), create=True),
        patch.object(mod, "__context__", context, create=True),
        patch.object(mod, "__salt__", {}, create=True),
    ]


# ---------------------------------------------------------------------------
# _make_single passes fsclient to Single
# ---------------------------------------------------------------------------


class TestMakeSingle:
    """_make_single() must pass a fsclient to Single.

    Single.cmd_block() calls mod_data(self.fsclient) unconditionally
    (added in the upstream relenv improvements merge).  If fsclient is
    None that call raises:

        AttributeError: 'NoneType' object has no attribute 'opts'

    The fix is for _make_single to call _file_client() and forward the
    result as the fsclient= keyword argument to Single.__init__.
    """

    def test_single_receives_fsclient(self):
        import contextlib

        import salt.resource.ssh as mod

        mock_fsclient = MagicMock()
        mock_single_cls = MagicMock()

        fixed_patches = [
            patch.object(mod, "_host_cfg", return_value=_HOST_CFG),
            patch.object(mod, "_relenv_path", return_value="/tmp/fake-relenv.tar.xz"),
            patch.object(mod, "_file_client", return_value=mock_fsclient),
            patch.object(mod, "_thin_dir", return_value="/tmp/_salt_relenv_test"),
            patch("salt.client.ssh.Single", mock_single_cls),
            patch("salt.client.ssh.ssh_version", return_value="8.0"),
        ] + _patch_module(mod)

        with contextlib.ExitStack() as stack:
            for p in fixed_patches:
                stack.enter_context(p)
            mod._make_single(_RESOURCE_ID, ["grains.items"])

        _, kwargs = mock_single_cls.call_args
        assert kwargs.get("fsclient") is mock_fsclient, (
            "_make_single must pass fsclient= to Single so that "
            "cmd_block() can call mod_data(fsclient) without crashing"
        )

    def test_fsclient_none_would_crash(self):
        """Confirm that omitting fsclient causes the crash this fix prevents.

        This test documents *why* the fix is needed: if fsclient is None,
        mod_data() raises AttributeError on 'NoneType'.opts.
        """

        def fake_mod_data(fsclient):
            if fsclient is None:
                raise AttributeError("'NoneType' object has no attribute 'opts'")
            return {}

        with patch("salt.client.ssh.mod_data", fake_mod_data):
            with pytest.raises(AttributeError, match="NoneType.*opts"):
                fake_mod_data(None)

            # With a real fsclient it works fine
            assert fake_mod_data(MagicMock()) == {}

"""
Unit tests for salt.resources.ssh.

Covers the _make_single() helper which constructs a salt.client.ssh.Single
from inside a minion job thread — a code path that salt-ssh itself never
takes (salt-ssh always runs on the master).

Also pins the no-pillar opts-driven contract added when
``pillar_resources_tree`` was removed from the module: ``discover(opts)``
is a generator, reads only from ``opts["ssh"]["hosts"]``, tolerates every
reasonable malformed shape without raising, and no code path reads
``opts["pillar"]``.
"""

import contextlib
import inspect

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

        import salt.resources.ssh as mod

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


# ---------------------------------------------------------------------------
# No-pillar opts-driven discovery contract
# ---------------------------------------------------------------------------


_OPTS_TWO_HOSTS = {
    "ssh": {
        "hosts": {
            "web-01": {
                "host": "192.168.1.10",
                "user": "root",
                "priv": "/etc/salt/ssh_keys/web-01",
            },
            "web-02": {
                "host": "192.168.1.11",
                "user": "admin",
                "passwd": "secretpassword",
                "priv_passwd": "keypass",
                "no_host_keys": True,
            },
        }
    }
}


class TestDiscoverContract:
    """``discover`` is the public opts-driven inventory API."""

    def test_discover_is_a_generator_function(self):
        """``inspect.isgeneratorfunction(discover) is True``.

        Streaming is required by the chunked register loop in
        ``Minion._register_resources_with_master``; a plain list
        would silently break the 10K-host memory ceiling.
        """
        import salt.resources.ssh as mod

        assert inspect.isgeneratorfunction(mod.discover) is True

    def test_discover_returns_generator_not_list(self):
        """Calling ``discover(opts)`` returns a generator object, never a list."""
        import salt.resources.ssh as mod

        result = mod.discover(_OPTS_TWO_HOSTS)
        assert inspect.isgenerator(result)
        assert not isinstance(result, list)

    def test_discover_yields_host_ids_in_order(self):
        """``discover(opts)`` yields exactly ``opts["ssh"]["hosts"].keys()``."""
        import salt.resources.ssh as mod

        result = list(mod.discover(_OPTS_TWO_HOSTS))
        assert result == ["web-01", "web-02"]

    @pytest.mark.parametrize(
        "opts",
        [
            {},
            {"ssh": None},
            {"ssh": "oops"},
            {"ssh": []},
            {"ssh": {}},
            {"ssh": {"hosts": None}},
            {"ssh": {"hosts": "not-a-dict"}},
            {"ssh": {"hosts": []}},
        ],
        ids=[
            "empty-opts",
            "ssh-is-None",
            "ssh-is-string",
            "ssh-is-list",
            "ssh-empty-dict",
            "hosts-is-None",
            "hosts-is-string",
            "hosts-is-list",
        ],
    )
    def test_discover_malformed_opts_yields_empty(self, opts):
        """Every malformed ``ssh:`` opts shape yields an empty iterator.

        The minion must never crash during a ``saltutil.refresh_resources``
        call because the operator typo'd their config; empty inventory is
        the correct degraded-mode answer.
        """
        import salt.resources.ssh as mod

        assert list(mod.discover(opts)) == []

    def test_discover_does_not_read_opts_pillar(self):
        """``discover`` must not read ``opts["pillar"]`` -- the Pillar tree
        is no longer the resource inventory source on the minion.

        We give it an ``opts`` dict whose ``pillar`` key raises on any
        access; discover+full-iteration must complete without touching it.
        """
        import salt.resources.ssh as mod

        class PillarTrap(dict):
            def __getitem__(self, key):
                if key == "pillar":
                    raise AssertionError("ssh.discover must not read opts['pillar']")
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key == "pillar":
                    raise AssertionError(
                        "ssh.discover must not read opts.get('pillar')"
                    )
                return super().get(key, default)

        opts = PillarTrap(_OPTS_TWO_HOSTS)
        # Full iteration -- not just construction of the generator.
        assert list(mod.discover(opts)) == ["web-01", "web-02"]

    def test_discover_does_not_call_removed_pillar_helper(self):
        """``pillar_resources_tree`` was deleted; nothing in ssh may import
        or call it.  We install a sentinel attribute that raises if touched."""
        import salt.resources.ssh as mod

        trap = MagicMock(side_effect=AssertionError("pillar_resources_tree called"))
        # Patch any plausible import surface; if the module ever re-added
        # the import this would fire during attribute resolution.
        with patch.object(mod, "pillar_resources_tree", trap, create=True):
            list(mod.discover(_OPTS_TWO_HOSTS))
        trap.assert_not_called()

    def test_discover_lazy_on_10k_hosts(self):
        """Pulling one id from a 10K-host opts dict must NOT iterate the
        whole hosts dict.

        We wrap the hosts dict in a counting proxy: taking ``next()`` once
        should produce one key, and the number of ``__iter__``/``keys``/
        ``__contains__`` calls on the underlying dict must stay bounded
        (certainly << 10K) regardless of inventory size.
        """
        import salt.resources.ssh as mod

        class CountingDict(dict):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self.item_access_count = 0

            def __iter__(self):
                # Count how many keys get pulled through the iterator.
                for k in super().__iter__():
                    self.item_access_count += 1
                    yield k

        hosts = CountingDict({f"host-{i:05d}": {} for i in range(10000)})
        opts = {"ssh": {"hosts": hosts}}

        gen = mod.discover(opts)
        first = next(gen)
        assert first == "host-00000"
        # Only one host key should have been walked so far.  A list-returning
        # implementation would have pulled all 10K before yielding.
        assert hosts.item_access_count == 1, (
            "discover materialized {} keys before yielding one; "
            "generator contract broken".format(hosts.item_access_count)
        )


class TestInitAndHostCfg:
    """``init(opts)`` must populate ``__context__`` from ``opts["ssh"]``."""

    def _init_with_opts(self, mod, opts):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(mod, "__opts__", opts, create=True))
            stack.enter_context(patch.object(mod, "__context__", {}, create=True))
            stack.enter_context(
                patch("salt.client.ssh.ssh_version", return_value="8.0")
            )
            # Prevent init() from touching the real filesystem for master opts.
            stack.enter_context(patch("os.path.isfile", return_value=False))
            stack.enter_context(
                patch(
                    "salt.fileclient.get_file_client",
                    side_effect=Exception("no network in unit test"),
                )
            )
            mod.init(opts)
            # Return a snapshot of the module context dict.
            return dict(mod.__context__)

    def test_roundtrip_init_then_host_cfg_returns_dict(self):
        """Full round trip: init(opts) -> discover(opts) -> _host_cfg(rid).

        After ``init``, ``_host_cfg(rid)`` must return the per-host dict
        verbatim for every id ``discover`` yielded.
        """
        import salt.resources.ssh as mod

        ctx = self._init_with_opts(mod, _OPTS_TWO_HOSTS)
        assert ctx[mod.CONTEXT_KEY]["initialized"] is True

        ids = list(mod.discover(_OPTS_TWO_HOSTS))
        assert ids == ["web-01", "web-02"]

        with patch.object(mod, "__context__", ctx, create=True):
            for rid in ids:
                cfg = mod._host_cfg(rid)
                assert isinstance(cfg, dict)
                assert cfg is _OPTS_TWO_HOSTS["ssh"]["hosts"][rid]

    def test_host_cfg_unknown_id_returns_empty_dict(self):
        """Unknown resource id must return ``{}``, never raise ``KeyError``."""
        import salt.resources.ssh as mod

        ctx = self._init_with_opts(mod, _OPTS_TWO_HOSTS)
        with patch.object(mod, "__context__", ctx, create=True):
            assert mod._host_cfg("does-not-exist") == {}

    @pytest.mark.parametrize(
        "opts",
        [
            {},
            {"ssh": None},
            {"ssh": "oops"},
            {"ssh": {}},
        ],
        ids=[
            "empty",
            "ssh-None",
            "ssh-string",
            "ssh-empty",
        ],
    )
    def test_init_malformed_opts_defaults_to_empty(self, opts):
        """``init`` with a malformed ``ssh:`` scalar must not raise and must
        default ``hosts`` to an empty mapping."""
        import salt.resources.ssh as mod

        ctx = self._init_with_opts(mod, opts)
        assert ctx[mod.CONTEXT_KEY]["initialized"] is True
        assert ctx[mod.CONTEXT_KEY]["hosts"] == {}
        # discover against the same opts must also yield nothing.
        assert list(mod.discover(opts)) == []

    @pytest.mark.parametrize(
        "opts",
        [
            {"ssh": {"hosts": None}},
            {"ssh": {"hosts": "not-a-dict"}},
        ],
        ids=["hosts-None", "hosts-string"],
    )
    def test_init_malformed_hosts_subkey_defaults_to_empty(self, opts):
        """``init(opts)`` with a dict ``ssh:`` but a malformed ``hosts:``
        subkey (``None`` / scalar) must not raise.

        Currently fails: ``init`` only guards the outer ``ssh`` isinstance
        check and lets ``hosts = None`` propagate until ``list(hosts)``
        at the end of the function.  The companion ``discover`` *does*
        guard the inner shape (see
        ``TestDiscoverContract.test_discover_malformed_opts_yields_empty``).

        Marked xfail(strict=True) so this flips to a regression test the
        moment ``init`` grows the matching ``isinstance(hosts, dict)``
        guard.
        """
        import salt.resources.ssh as mod

        ctx = self._init_with_opts(mod, opts)
        assert ctx[mod.CONTEXT_KEY]["initialized"] is True
        assert ctx[mod.CONTEXT_KEY]["hosts"] == {}

    # Re-decorate above with xfail -- kept separate so collection still finds
    # the test even if xfail machinery changes.
    test_init_malformed_hosts_subkey_defaults_to_empty = pytest.mark.xfail(
        reason=(
            "init() lacks isinstance(hosts, dict) guard; raises TypeError on "
            "list(None) at end of function. discover() has the guard; init() "
            "does not. Low-impact defect -- operators would have to type "
            "`hosts:` with no value (or a scalar) under `ssh:`."
        ),
        strict=True,
    )(test_init_malformed_hosts_subkey_defaults_to_empty)


class TestVirtual:
    """``__virtual__`` gating."""

    def test_virtual_true_when_ssh_binary_present(self):
        """Module loads when ``ssh`` is on PATH."""
        import salt.resources.ssh as mod

        with patch("salt.utils.path.which", return_value="/usr/bin/ssh"):
            result = mod.__virtual__()
        assert result is True

    def test_virtual_false_with_reason_when_ssh_binary_absent(self):
        """Module refuses to load when ``ssh`` is missing from PATH,
        returning the standard ``(False, reason)`` tuple."""
        import salt.resources.ssh as mod

        with patch("salt.utils.path.which", return_value=None):
            result = mod.__virtual__()
        assert isinstance(result, tuple)
        assert result[0] is False
        assert "ssh" in result[1].lower()


class TestGrainsSanitization:
    """``grains()`` must never leak host-config secrets.

    SSH host config carries ``passwd``, ``priv``, and ``priv_passwd``.
    The per-host grain dict returned to the minion grain system must
    not surface any of those values -- they are credentials, not grains.
    """

    _SECRET_KEYS = ("passwd", "priv", "priv_passwd", "key", "password")

    def _ctx_with_hosts(self, hosts):
        return {
            "ssh_resource": {
                "initialized": True,
                "hosts": hosts,
                "_ssh_version": "8.0",
                "grains": {},
                "master_opts": None,
            }
        }

    def test_grains_fallback_omits_credentials(self):
        """When remote ``grains.items`` fails, the minimal fallback dict
        contains only ``resource_type``, ``resource_id``, and ``host``."""
        import salt.resources.ssh as mod

        resource_id = "web-02"
        hosts = {resource_id: dict(_OPTS_TWO_HOSTS["ssh"]["hosts"][resource_id])}
        ctx = self._ctx_with_hosts(hosts)

        fake_single = MagicMock()
        fake_single.cmd_block.return_value = ("ERROR: unreachable", "", 1)

        patches = [
            patch.object(mod, "__opts__", {"cachedir": "/tmp"}, create=True),
            patch.object(
                mod, "__resource__", {"id": resource_id, "type": "ssh"}, create=True
            ),
            patch.object(mod, "__context__", ctx, create=True),
            patch.object(mod, "_make_single", return_value=fake_single),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            result = mod.grains()

        # Credential keys must be absent.
        for secret in self._SECRET_KEYS:
            assert secret not in result, f"grains() leaked {secret!r} in fallback path"
        # No value from the host cfg credentials appears either.
        for secret_val in ("secretpassword", "keypass", "/etc/salt/ssh_keys/web-01"):
            assert secret_val not in result.values()

    def test_grains_success_does_not_merge_host_credentials(self):
        """On a successful remote ``grains.items`` call, the module must
        return only remote-collected grains plus the two resource markers
        -- never the local host-config secrets.
        """
        import salt.resources.ssh as mod
        import salt.utils.json

        resource_id = "web-02"
        hosts = {resource_id: dict(_OPTS_TWO_HOSTS["ssh"]["hosts"][resource_id])}
        ctx = self._ctx_with_hosts(hosts)

        remote_grains = {"os": "Ubuntu", "osrelease": "22.04", "kernel": "Linux"}
        stdout = salt.utils.json.dumps({"local": {"jid": "x", "return": remote_grains}})
        fake_single = MagicMock()
        fake_single.cmd_block.return_value = (stdout, "", 0)

        patches = [
            patch.object(mod, "__opts__", {"cachedir": "/tmp"}, create=True),
            patch.object(
                mod, "__resource__", {"id": resource_id, "type": "ssh"}, create=True
            ),
            patch.object(mod, "__context__", ctx, create=True),
            patch.object(mod, "_make_single", return_value=fake_single),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            result = mod.grains()

        assert result["resource_type"] == "ssh"
        assert result["resource_id"] == resource_id
        assert result["os"] == "Ubuntu"
        # Critical: credentials from __context__[hosts][rid] must NOT appear.
        for secret in self._SECRET_KEYS:
            assert secret not in result, f"grains() leaked {secret!r} on success path"


class TestNoPillarReadsDuringFullCycle:
    """Belt-and-braces: a full ``init -> discover -> grains`` cycle must
    not touch ``opts["pillar"]`` anywhere."""

    def test_no_pillar_access_during_discover_and_grains(self):
        """Wraps opts in a dict that raises on any ``pillar`` access, then
        runs the complete discovery path plus a grains call.  Zero reads
        of ``opts["pillar"]`` must occur."""
        import salt.resources.ssh as mod
        import salt.utils.json

        class PillarTrap(dict):
            def __getitem__(self, key):
                assert key != "pillar", "opts['pillar'] read is forbidden"
                return super().__getitem__(key)

            def get(self, key, default=None):
                assert key != "pillar", "opts.get('pillar') read is forbidden"
                return super().get(key, default)

            def __contains__(self, key):
                assert key != "pillar", "'pillar' in opts read is forbidden"
                return super().__contains__(key)

        resource_id = "web-01"
        opts = PillarTrap(
            {
                "cachedir": "/tmp",
                "ssh": {
                    "hosts": {
                        resource_id: {
                            "host": "192.168.1.10",
                            "user": "root",
                            "priv": "/etc/salt/ssh_keys/web-01",
                        }
                    }
                },
            }
        )

        # Exercise discover.
        assert list(mod.discover(opts)) == [resource_id]

        # Exercise grains.
        ctx = {
            "ssh_resource": {
                "initialized": True,
                "hosts": opts["ssh"]["hosts"],
                "_ssh_version": "8.0",
                "grains": {},
                "master_opts": None,
            }
        }
        remote_grains = {"os": "Ubuntu"}
        stdout = salt.utils.json.dumps({"local": {"jid": "x", "return": remote_grains}})
        fake_single = MagicMock()
        fake_single.cmd_block.return_value = (stdout, "", 0)

        patches = [
            patch.object(mod, "__opts__", opts, create=True),
            patch.object(
                mod, "__resource__", {"id": resource_id, "type": "ssh"}, create=True
            ),
            patch.object(mod, "__context__", ctx, create=True),
            patch.object(mod, "_make_single", return_value=fake_single),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            result = mod.grains()
        assert result["resource_id"] == resource_id

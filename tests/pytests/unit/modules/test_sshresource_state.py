"""
Unit tests for salt.modules.sshresource_state.

Covers:
- highstate(): empty chunks → returns the 'no top file' state dict with
  result=False rather than None/empty so the merge block displays it cleanly.
- _exec_state_pkg(): catches SSHCommandExecutionError and extracts the state
  result dict from the exception's parsed data when it contains a valid return.
  Re-raises the exception when the parsed data does not contain a valid state dict.
"""

import pytest

from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RESOURCE_ID = "node1"

_VALID_STATE_RETURN = {
    "pkg_|-curl_|-curl_|-installed": {
        "result": False,
        "comment": "Package curl is not installed",
        "name": "curl",
        "changes": {},
        "__run_num__": 0,
    }
}

_BASE_OPTS = {
    "id": "minion",
    "resource_type": "ssh",
    "cachedir": "/tmp",
    "hash_type": "sha256",
    "thin_dir": "/tmp/.test_salt",
    "test": False,
    "pillar": {},
}

_BASE_RESOURCE = {"id": _RESOURCE_ID, "type": "ssh"}


# ---------------------------------------------------------------------------
# _relenv_path(): returns tarball or None
# ---------------------------------------------------------------------------


class TestRelenvPath:
    """_relenv_path() returns the first existing tarball or None."""

    def _run(self, existing_files=()):
        import salt.modules.sshresource_state as mod

        opts = _BASE_OPTS.copy()
        with patch.object(mod, "__opts__", opts, create=True), patch.object(
            mod, "__resource__", dict(_BASE_RESOURCE), create=True
        ), patch.object(mod, "__context__", {}, create=True), patch.object(
            mod, "__salt__", {}, create=True
        ), patch(
            "os.path.exists", side_effect=lambda p: p in existing_files
        ):
            return mod._relenv_path()

    def test_returns_x86_64_when_present(self):
        path = "/tmp/relenv/linux/x86_64/salt-relenv.tar.xz"
        assert self._run(existing_files=(path,)) == path

    def test_returns_arm64_when_present(self):
        path = "/tmp/relenv/linux/arm64/salt-relenv.tar.xz"
        assert self._run(existing_files=(path,)) == path

    def test_returns_none_when_no_tarball(self):
        assert self._run(existing_files=()) is None

    def test_prefers_x86_64_over_arm64(self):
        x86 = "/tmp/relenv/linux/x86_64/salt-relenv.tar.xz"
        arm = "/tmp/relenv/linux/arm64/salt-relenv.tar.xz"
        assert self._run(existing_files=(x86, arm)) == x86


def _make_ssh_error(parsed):
    """Build a fake SSHCommandExecutionError with .parsed attribute."""
    import salt.client.ssh.wrapper

    return salt.client.ssh.wrapper.SSHCommandExecutionError(
        "stdout", "stderr", 2, parsed=parsed
    )


# ---------------------------------------------------------------------------
# highstate(): empty chunks → no-top-file state dict
# ---------------------------------------------------------------------------


class TestHighstateEmptyChunks:
    """highstate() with no top-file match must return a proper state dict."""

    def _run_highstate(self):
        import salt.modules.sshresource_state as mod

        opts = _BASE_OPTS.copy()

        mock_state = MagicMock()
        mock_state.__enter__ = MagicMock(return_value=mock_state)
        mock_state.__exit__ = MagicMock(return_value=False)
        mock_state.opts = {"pillar": {}, "test": False}
        mock_state.compile_low_chunks.return_value = []  # no chunks → no top file

        with patch.object(mod, "__opts__", opts, create=True), patch.object(
            mod, "__resource__", dict(_BASE_RESOURCE), create=True
        ), patch.object(mod, "__context__", {}, create=True), patch.object(
            mod, "__salt__", {}, create=True
        ), patch.object(
            mod, "_target_opts", return_value=opts
        ), patch.object(
            mod, "_seed_thin_dir", return_value="/tmp/.test_salt"
        ), patch.object(
            mod, "_get_initial_pillar", return_value=None
        ), patch.object(
            mod, "_file_client", return_value=MagicMock()
        ), patch(
            "salt.client.ssh.state.SSHHighState", return_value=mock_state
        ), patch(
            "salt.utils.state.get_sls_opts", return_value=opts
        ):
            return mod.highstate()

    def test_returns_dict(self):
        result = self._run_highstate()
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    def test_uses_no_state_key(self):
        result = self._run_highstate()
        assert "no_|-states_|-states_|-None" in result

    def test_result_is_false(self):
        result = self._run_highstate()
        entry = result["no_|-states_|-states_|-None"]
        assert entry["result"] is False

    def test_comment_mentions_resource_id(self):
        result = self._run_highstate()
        comment = result["no_|-states_|-states_|-None"]["comment"]
        assert _RESOURCE_ID in comment

    def test_changes_empty(self):
        result = self._run_highstate()
        assert result["no_|-states_|-states_|-None"]["changes"] == {}


# ---------------------------------------------------------------------------
# _exec_state_pkg(): SSHCommandExecutionError recovery
# ---------------------------------------------------------------------------


class TestExecStatePkg:
    """_exec_state_pkg must recover valid state dicts from SSHCommandExecutionError."""

    def _run(self, exc_parsed):
        """
        Run _exec_state_pkg with a mocked Single that raises SSHCommandExecutionError.
        Returns (result, context_dict).
        """
        import salt.modules.sshresource_state as mod

        opts = _BASE_OPTS.copy()
        context = {}
        exc = _make_ssh_error(exc_parsed)

        with patch.object(mod, "__opts__", opts, create=True), patch.object(
            mod, "__resource__", dict(_BASE_RESOURCE), create=True
        ), patch.object(mod, "__context__", context, create=True), patch.object(
            mod, "__salt__", {}, create=True
        ), patch.object(
            mod, "_resource_id", return_value=_RESOURCE_ID
        ), patch.object(
            mod, "_relenv_path", return_value="/tmp/relenv.tar.xz"
        ), patch.object(
            mod, "_file_client", return_value=MagicMock()
        ), patch.object(
            mod, "_connection_kwargs", return_value={}
        ), patch(
            "salt.utils.hashutils.get_hash", return_value="abc123"
        ), patch(
            "os.remove"
        ), patch(
            "salt.client.ssh.Single"
        ) as mock_single_cls, patch(
            "salt.client.ssh.wrapper.parse_ret", side_effect=exc
        ):
            mock_single = MagicMock()
            mock_single.cmd_block.return_value = ('{"local": {}}', "", 2)
            mock_single.shell = MagicMock()
            mock_single_cls.return_value = mock_single

            result = mod._exec_state_pkg(opts, "/tmp/fake.tgz", False)
            return result, context

    def test_extracts_state_dict_from_exception(self):
        parsed = {"local": {"return": _VALID_STATE_RETURN, "retcode": 2}}
        result, _ = self._run(parsed)
        assert result == _VALID_STATE_RETURN

    def test_sets_retcode_from_exception(self):
        parsed = {"local": {"return": _VALID_STATE_RETURN, "retcode": 2}}
        _, context = self._run(parsed)
        assert context.get("retcode") == 2

    def test_reraises_when_local_missing(self):
        import salt.client.ssh.wrapper

        with pytest.raises(salt.client.ssh.wrapper.SSHCommandExecutionError):
            self._run({})  # no "local" key

    def test_reraises_when_return_not_dict(self):
        import salt.client.ssh.wrapper

        parsed = {"local": {"return": "raw string output", "retcode": 1}}
        with pytest.raises(salt.client.ssh.wrapper.SSHCommandExecutionError):
            self._run(parsed)

    def test_reraises_when_parsed_is_none(self):
        import salt.client.ssh.wrapper
        import salt.modules.sshresource_state as mod

        opts = _BASE_OPTS.copy()
        context = {}

        exc = salt.client.ssh.wrapper.SSHCommandExecutionError(
            "stdout", "stderr", 1, parsed=None
        )

        with patch.object(mod, "__opts__", opts, create=True), patch.object(
            mod, "__resource__", dict(_BASE_RESOURCE), create=True
        ), patch.object(mod, "__context__", context, create=True), patch.object(
            mod, "__salt__", {}, create=True
        ), patch.object(
            mod, "_resource_id", return_value=_RESOURCE_ID
        ), patch.object(
            mod, "_relenv_path", return_value="/tmp/relenv.tar.xz"
        ), patch.object(
            mod, "_file_client", return_value=MagicMock()
        ), patch.object(
            mod, "_connection_kwargs", return_value={}
        ), patch(
            "salt.utils.hashutils.get_hash", return_value="abc123"
        ), patch(
            "os.remove"
        ), patch(
            "salt.client.ssh.Single"
        ) as mock_single_cls, patch(
            "salt.client.ssh.wrapper.parse_ret", side_effect=exc
        ):
            mock_single = MagicMock()
            mock_single.cmd_block.return_value = ("", "", 1)
            mock_single.shell = MagicMock()
            mock_single_cls.return_value = mock_single

            with pytest.raises(salt.client.ssh.wrapper.SSHCommandExecutionError):
                mod._exec_state_pkg(opts, "/tmp/fake.tgz", False)


# ---------------------------------------------------------------------------
# _exec_state_pkg(): normal (non-exception) path
# ---------------------------------------------------------------------------


class TestExecStatePkgNormalPath:
    """_exec_state_pkg must unwrap the envelope dict returned by parse_ret."""

    def _run(self, envelope):
        import salt.modules.sshresource_state as mod

        opts = _BASE_OPTS.copy()
        context = {}

        with patch.object(mod, "__opts__", opts, create=True), patch.object(
            mod, "__resource__", dict(_BASE_RESOURCE), create=True
        ), patch.object(mod, "__context__", context, create=True), patch.object(
            mod, "__salt__", {}, create=True
        ), patch.object(
            mod, "_resource_id", return_value=_RESOURCE_ID
        ), patch.object(
            mod, "_relenv_path", return_value="/tmp/relenv.tar.xz"
        ), patch.object(
            mod, "_file_client", return_value=MagicMock()
        ), patch.object(
            mod, "_connection_kwargs", return_value={}
        ), patch(
            "salt.utils.hashutils.get_hash", return_value="abc123"
        ), patch(
            "os.remove"
        ), patch(
            "salt.client.ssh.Single"
        ) as mock_single_cls, patch(
            "salt.client.ssh.wrapper.parse_ret", return_value=envelope
        ):
            mock_single = MagicMock()
            mock_single.cmd_block.return_value = ("", "", 0)
            mock_single.shell = MagicMock()
            mock_single_cls.return_value = mock_single

            result = mod._exec_state_pkg(opts, "/tmp/fake.tgz", False)
            return result, context

    def test_returns_state_dict_from_envelope(self):
        envelope = {"return": _VALID_STATE_RETURN, "retcode": 0}
        result, _ = self._run(envelope)
        assert result == _VALID_STATE_RETURN

    def test_sets_retcode_on_non_zero_envelope(self):
        envelope = {"return": _VALID_STATE_RETURN, "retcode": 2}
        _, context = self._run(envelope)
        assert context.get("retcode") == 2

    def test_zero_retcode_does_not_set_context_retcode(self):
        """A clean run (retcode 0) must not inject a non-zero retcode into context."""
        envelope = {"return": _VALID_STATE_RETURN, "retcode": 0}
        _, context = self._run(envelope)
        assert context.get("retcode", 0) == 0

    def test_single_receives_fsclient(self):
        """Single must be constructed with a fsclient so cmd_block can call mod_data."""
        import salt.modules.sshresource_state as mod

        opts = _BASE_OPTS.copy()
        mock_fsclient = MagicMock()

        with patch.object(mod, "__opts__", opts, create=True), patch.object(
            mod, "__resource__", dict(_BASE_RESOURCE), create=True
        ), patch.object(mod, "__context__", {}, create=True), patch.object(
            mod, "__salt__", {}, create=True
        ), patch.object(
            mod, "_resource_id", return_value=_RESOURCE_ID
        ), patch.object(
            mod, "_relenv_path", return_value="/tmp/relenv.tar.xz"
        ), patch.object(
            mod, "_file_client", return_value=mock_fsclient
        ), patch.object(
            mod, "_connection_kwargs", return_value={}
        ), patch(
            "salt.utils.hashutils.get_hash", return_value="abc123"
        ), patch(
            "os.remove"
        ), patch(
            "salt.client.ssh.Single"
        ) as mock_single_cls, patch(
            "salt.client.ssh.wrapper.parse_ret",
            return_value={"return": _VALID_STATE_RETURN, "retcode": 0},
        ):
            mock_single = MagicMock()
            mock_single.cmd_block.return_value = ("", "", 0)
            mock_single.shell = MagicMock()
            mock_single_cls.return_value = mock_single

            mod._exec_state_pkg(opts, "/tmp/fake.tgz", False)

            _, kwargs = mock_single_cls.call_args
            assert kwargs.get("fsclient") is mock_fsclient

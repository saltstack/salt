"""
Regression tests for issue #69637.

If ``HighState.__init__`` (or ``State.__init__``) allocates a fileclient and
then a later step in the same constructor raises, the caller never gets the
``HighState``/``State`` instance and therefore never calls ``destroy()``.  The
allocated fileclient's transport is finalized during garbage collection with
``_closing = False``, which trips the ``TransportWarning: Unclosed
transport!`` warning added by PR #65559.

These tests exercise the failure path and assert that the fileclient's
``destroy()`` is invoked before the exception propagates.
"""

import pytest

import salt.state
from tests.support import mock

pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def minimal_opts(tmp_path):
    return {
        "id": "test-minion",
        "__role": "minion",
        "cachedir": str(tmp_path / "cache"),
        "extension_modules": str(tmp_path / "ext_mods"),
        "file_client": "remote",
        "file_roots": {"base": []},
        "pillar_roots": {"base": []},
        "state_top": "salt://top.sls",
        "renderer": "yaml_jinja",
        "renderer_whitelist": [],
        "renderer_blacklist": [],
        "grains": {},
        "pillar": {},
        "pillarenv": None,
        "saltenv": "base",
        "state_events": False,
        "state_verbose": True,
        "pillar_cache": False,
        "master_type": "str",
        "master": "127.0.0.1",
        "master_uri": "tcp://127.0.0.1:44506",
        "transport": "zeromq",
    }


def test_highstate_init_failure_destroys_fileclient(minimal_opts):
    """
    If ``BaseHighState.__init__`` (called from ``HighState.__init__``) raises,
    the fileclient allocated seconds earlier must be destroyed rather than
    leaked to garbage collection.

    Regression test for issue #69637.
    """
    mock_client = mock.MagicMock()
    with mock.patch(
        "salt.fileclient.get_file_client", return_value=mock_client
    ), mock.patch.object(
        salt.state.BaseHighState, "__init__", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError, match="boom"):
            salt.state.HighState(minimal_opts)
    mock_client.destroy.assert_called_once()


def test_highstate_init_success_does_not_destroy_fileclient(minimal_opts):
    """
    In the success case the fileclient must remain owned by the HighState so
    that ``HighState.destroy()`` can close it later.  This test guards the
    happy path so the exception-safety change doesn't accidentally double-
    destroy.
    """
    mock_client = mock.MagicMock()
    with mock.patch(
        "salt.fileclient.get_file_client", return_value=mock_client
    ), mock.patch.object(
        salt.state.BaseHighState, "__init__", return_value=None
    ), mock.patch.object(
        salt.state, "State", return_value=mock.MagicMock()
    ), mock.patch(
        "salt.loader.matchers"
    ):
        hs = salt.state.HighState(minimal_opts)
        # Constructor succeeded — the client is now owned by hs.
        assert hs.client is mock_client
        assert hs.preserve_client is False
        mock_client.destroy.assert_not_called()
        # Explicit destroy still works.
        hs.destroy()
        mock_client.destroy.assert_called_once()


def test_state_init_failure_destroys_fileclient(minimal_opts):
    """
    If ``State.__init__`` raises after allocating a fileclient (e.g. during
    pillar rendering), that fileclient must be destroyed.

    Regression test for issue #69637.
    """
    mock_client = mock.MagicMock()
    with mock.patch(
        "salt.fileclient.get_file_client", return_value=mock_client
    ), mock.patch.object(
        salt.state.State,
        "_gather_pillar",
        side_effect=RuntimeError("pillar boom"),
    ):
        with pytest.raises(RuntimeError, match="pillar boom"):
            salt.state.State(minimal_opts)
    # State prefers destroy() but falls back to close() if not available.
    assert (
        mock_client.destroy.called or mock_client.close.called
    ), "State did not tear down its fileclient after init failure"

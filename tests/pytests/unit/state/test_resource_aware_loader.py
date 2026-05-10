"""
Unit test: ``salt.state.State`` switches its execution-module loader to
:func:`salt.loader.resource_modules` when ``opts["resource_type"]`` is set.

This is the load-time half of the resource-aware state pipeline.  When
``state.apply`` is dispatched into a resource context (the per-resource
execution loader runs the function), ``__opts__`` carries ``resource_type``
through to ``State.__init__``.  ``State.load_modules`` must then build
``self.functions`` from the per-resource loader so that state modules under
``salt/states/`` get a resource-aware ``__salt__`` automatically — without
needing a separate ``__resource_funcs__`` dunder in the state pack.

The companion state module :mod:`salt.states.dummyresource_test` exercises
the dispatch path: it virtuals out unless ``resource_type == "dummy"``,
and its ``present`` function calls ``__salt__["test.ping"]`` which the
per-resource loader resolves to :func:`salt.modules.dummyresource_test.ping`
(itself delegating to :func:`salt.resource.dummy.ping` via
``__resource_funcs__``).
"""

import pytest

import salt.config
import salt.loader.context as loader_ctx
import salt.state


@pytest.fixture
def resource_state_opts(tmp_path):
    """Minion opts wired for an in-process dummy resource type."""
    cachedir = tmp_path / "cache"
    cachedir.mkdir()
    (tmp_path / "srv" / "salt").mkdir(parents=True)
    (tmp_path / "srv" / "pillar").mkdir(parents=True)

    opts = salt.config.minion_config(None)
    opts["root_dir"] = str(tmp_path)
    opts["cachedir"] = str(cachedir)
    opts["file_client"] = "local"
    opts["file_roots"] = {"base": [str(tmp_path / "srv" / "salt")]}
    opts["pillar_roots"] = {"base": [str(tmp_path / "srv" / "pillar")]}
    opts["resource_type"] = "dummy"
    opts["resources"] = {"dummy": ["dummy-01"]}
    opts.setdefault("grains", {})
    opts["pillar"] = {}
    return opts


def test_state_loader_uses_resource_modules_when_resource_type_set(
    resource_state_opts,
):
    """
    With ``resource_type`` in opts, ``State`` builds its ``self.functions``
    via :func:`salt.loader.resource_modules` (per-resource execution loader)
    rather than :func:`salt.loader.minion_mods`.  The state loader's
    ``__salt__`` then dispatches to resource-aware modules.
    """
    st_ = salt.state.State(resource_state_opts)
    # The per-resource loader carries ``resource_type`` in its bound opts.
    assert st_.functions.opts.get("resource_type") == "dummy"
    # The connection module loader must be available too — it's what the
    # per-resource execution modules reach for via ``__resource_funcs__``.
    assert hasattr(st_, "resource_funcs")
    assert "dummy.ping" in st_.resource_funcs
    # Standard ``test.ping`` virtuals out in dummy context; the dummy
    # resource override takes the slot instead.
    assert "test.ping" in st_.functions
    # And the new state module loaded successfully because it sees the
    # resource-typed opts.
    assert "dummy_test.present" in st_.states


def test_state_falls_back_to_minion_mods_without_resource_type(tmp_path):
    """
    Without ``resource_type`` in opts the existing behaviour is preserved:
    ``State`` builds its execution-module loader via
    :func:`salt.loader.minion_mods`, and the new ``dummy_test`` state
    module is invisible.
    """
    cachedir = tmp_path / "cache"
    cachedir.mkdir()
    (tmp_path / "srv" / "salt").mkdir(parents=True)
    (tmp_path / "srv" / "pillar").mkdir(parents=True)

    opts = salt.config.minion_config(None)
    opts["root_dir"] = str(tmp_path)
    opts["cachedir"] = str(cachedir)
    opts["file_client"] = "local"
    opts["file_roots"] = {"base": [str(tmp_path / "srv" / "salt")]}
    opts["pillar_roots"] = {"base": [str(tmp_path / "srv" / "pillar")]}
    opts.setdefault("grains", {})
    opts["pillar"] = {}

    st_ = salt.state.State(opts)
    assert "resource_type" not in st_.functions.opts
    assert "dummy_test.present" not in st_.states
    # No resource_funcs attribute either — only set in the resource branch.
    assert not hasattr(st_, "resource_funcs")


def test_dummy_state_dispatches_through_per_resource_loader(resource_state_opts):
    """
    End-to-end: invoke the new ``dummy_test.present`` state and confirm
    ``__salt__["test.ping"]`` is the per-resource override (which delegates
    to ``salt.resource.dummy.ping``), not the managing minion's own
    ``test.ping``.

    The per-resource override returns ``True`` only when ``__resource__``
    is set in the contextvar; we set it manually to mimic what the minion's
    ``_thread_return`` does before dispatching a job.
    """
    st_ = salt.state.State(resource_state_opts)
    # Initialize the dummy connection module's __context__.
    st_.resource_funcs["dummy.init"](resource_state_opts)
    token = loader_ctx.resource_ctxvar.set({"type": "dummy", "id": "dummy-01"})
    try:
        ret = st_.states["dummy_test.present"]("hello")
    finally:
        loader_ctx.resource_ctxvar.reset(token)

    assert ret == {
        "name": "hello",
        "result": True,
        "comment": "dummy resource ping returned True",
        "changes": {},
    }

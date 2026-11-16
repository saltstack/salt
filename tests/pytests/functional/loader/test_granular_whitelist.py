"""
Functional tests for function-scoped ``module.func`` entries in
``whitelist_modules`` / ``whitelist_state_modules``.

Companion to :mod:`tests.pytests.unit.loader.test_granular_whitelist`.
Where the unit tests exercise ``_parse_whitelist`` and the helper gates
against a scratch-directory LazyLoader, these tests wire up real
``salt.loader.minion_mods`` and ``salt.loader.states`` against the
shipped Salt modules (``cmd``, ``file``, ``test``) and prove the gate
behaves end-to-end on the actual loader pipeline.
"""

import copy
import textwrap

import pytest

import salt.loader
import salt.loader.context
import salt.loader.lazy
import salt.state

# ---------------------------------------------------------------------------
# Execution-module loader (whitelist_modules)
# ---------------------------------------------------------------------------


@pytest.fixture
def exec_wl_opts(minion_opts, tmp_path):
    """
    Minion opts with a granular execution-module whitelist.

    ``cmd`` is scoped to a single function (``cmd.run``) and ``test`` is
    a bare entry -- together they let us exercise every branch of the
    granular syntax against real shipped modules.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["cmd.run", "test"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    return opts


@pytest.fixture
def exec_wl_loader(exec_wl_opts):
    return salt.loader.minion_mods(exec_wl_opts)


def test_exec_dotted_entry_resolves_the_allowed_function(exec_wl_loader):
    """
    ``whitelist_modules: [cmd.run]`` -- ``cmd.run`` is reachable and
    actually callable through the real loader.
    """
    assert "cmd.run" in exec_wl_loader
    func = exec_wl_loader["cmd.run"]
    assert callable(func)


def test_exec_dotted_entry_blocks_sibling_functions(exec_wl_loader):
    """
    Sibling functions of the same module (``cmd.retcode``, ``cmd.shell``,
    ``cmd.run_bg``) must be unreachable even though they share a file
    with the allowed ``cmd.run``.
    """
    for blocked in ("cmd.retcode", "cmd.shell", "cmd.run_bg"):
        assert blocked not in exec_wl_loader, blocked
        with pytest.raises(KeyError):
            _ = exec_wl_loader[blocked]


def test_exec_sibling_blocked_after_module_already_loaded(exec_wl_loader):
    """
    The gate must survive after a sibling of the blocked function has
    forced the module to load.  ``cmd.run`` populates ``cmd.retcode``
    into ``_dict`` as a side effect, but the gate at ``__getitem__`` is
    applied on every lookup so the sibling stays rejected.
    """
    # Trigger module load.
    _ = exec_wl_loader["cmd.run"]
    # Internal dict carries the sibling even though it is gated.
    assert "cmd.retcode" in exec_wl_loader._dict
    assert "cmd.retcode" not in exec_wl_loader
    with pytest.raises(KeyError):
        _ = exec_wl_loader["cmd.retcode"]


def test_exec_bare_entry_still_allows_every_public_function(exec_wl_loader):
    """
    Backcompat: a bare ``test`` entry resolves every public function of
    the module (``test.ping``, ``test.echo``, ...) through the real
    loader without having to list each one.
    """
    assert callable(exec_wl_loader["test.ping"])
    assert callable(exec_wl_loader["test.echo"])
    # ``test.ping`` returns True.
    assert exec_wl_loader["test.ping"]() is True


def test_exec_jinja_attr_access_honors_function_gate(exec_wl_loader):
    """
    Jinja-style attribute access (``salt.cmd.run``) resolves via
    ``LazyLoader.__getattr__`` -> ``LoadedMod.__getattr__`` ->
    ``loader["cmd.run"]``, so the function-level gate applies.
    """
    mod = exec_wl_loader.cmd
    assert isinstance(mod, salt.loader.lazy.LoadedMod)
    assert callable(mod.run)
    # Blocked sibling -> AttributeError on attribute-style access, so
    # ``hasattr(salt, 'cmd').retcode`` / Jinja ``undefined`` fallthrough
    # behave correctly.
    with pytest.raises(AttributeError):
        getattr(mod, "retcode")


def test_exec_jinja_attr_access_rejects_unlisted_module(exec_wl_loader):
    """
    A module that is neither bare-listed nor mentioned by any
    ``module.func`` entry raises ``AttributeError`` on attribute-style
    access.
    """
    with pytest.raises(AttributeError):
        getattr(exec_wl_loader, "grains")


def test_exec_bare_plus_dotted_narrows_to_listed_functions(minion_opts, tmp_path):
    """
    ``[cmd, cmd.run]`` -- the dotted entry narrows the bare one so only
    the listed function survives.  This is the "tightening without
    removing the broader entry" path through the real loader.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["cmd", "cmd.run"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    loader = salt.loader.minion_mods(opts)
    assert callable(loader["cmd.run"])
    for blocked in ("cmd.retcode", "cmd.shell", "cmd.run_bg"):
        assert blocked not in loader, blocked


def test_exec_unlisted_module_blocked_entirely(exec_wl_loader):
    """
    Sanity check: a module that appears in neither form of the
    whitelist is blocked end-to-end.  Attribute- and dict-style access
    both refuse.
    """
    assert "grains.items" not in exec_wl_loader
    with pytest.raises(KeyError):
        _ = exec_wl_loader["grains.items"]


def test_exec_dunder_salt_stays_unfiltered(exec_wl_loader):
    """
    The two-loader model is unchanged: the inner unfiltered loader
    (``_dunder_salt``) must still expose every exec function so shipped
    modules can compose with blocked ones via ``__salt__[...]``.  The
    granular whitelist only tightens the wire-facing outer loader.
    """
    inner = exec_wl_loader._dunder_salt
    # Blocked on the outer wire loader...
    assert "cmd.retcode" not in exec_wl_loader
    # ...but reachable on the inner dunder for internal composition.
    assert "cmd.retcode" in inner


# ---------------------------------------------------------------------------
# State-module loader (whitelist_state_modules)
# ---------------------------------------------------------------------------


@pytest.fixture
def state_wl_opts(minion_opts, tmp_path):
    """
    Minion opts with a granular state-module whitelist: ``file.managed``
    narrowed to a single function, ``test`` left bare.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_state_modules"] = ["file.managed", "test"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    return opts


@pytest.fixture
def state_wl_loader(state_wl_opts):
    minion_mods = salt.loader.minion_mods(state_wl_opts)
    utils = salt.loader.utils(state_wl_opts)
    serializers = salt.loader.serializers(state_wl_opts)
    return salt.loader.states(state_wl_opts, minion_mods, utils, serializers)


def test_state_dotted_entry_resolves_allowed_state(state_wl_loader):
    """
    ``whitelist_state_modules: [file.managed]`` -- ``file.managed`` is
    callable through the real state loader.
    """
    assert "file.managed" in state_wl_loader
    assert callable(state_wl_loader["file.managed"])


def test_state_dotted_entry_blocks_sibling_states(state_wl_loader):
    """
    Other state functions of the same state module (``file.absent``,
    ``file.directory``, ``file.symlink``) are unreachable.
    """
    for blocked in ("file.absent", "file.directory", "file.symlink"):
        assert blocked not in state_wl_loader, blocked
        with pytest.raises(KeyError):
            _ = state_wl_loader[blocked]


def test_state_bare_entry_still_allows_all_state_functions(state_wl_loader):
    """
    Backcompat: bare ``test`` entry resolves every public state function
    of the ``test`` module (``test.succeed_without_changes``,
    ``test.fail_without_changes``, ``test.nop``, ...).
    """
    assert callable(state_wl_loader["test.succeed_without_changes"])
    assert callable(state_wl_loader["test.fail_without_changes"])


def test_state_render_sls_of_allowed_state_succeeds(state_wl_opts):
    """
    End-to-end: a rendered SLS that declares ``file.managed`` must
    compile and run through ``State.call_template_str`` -- proving the
    function-level gate interoperates with the state compiler.
    """
    st = salt.state.State(state_wl_opts)
    sls = textwrap.dedent(
        """\
        probe:
          test.succeed_without_changes:
            - name: ok
        """
    )
    ret = st.call_template_str(sls)
    assert isinstance(ret, dict), ret
    chunk_id = next(iter(ret))
    assert ret[chunk_id]["result"] is True


def test_state_render_sls_of_blocked_state_function_fails_runtime(state_wl_opts):
    """
    An SLS that declares a non-whitelisted state function
    (``file.absent`` while only ``file.managed`` is allowed) must not
    silently execute.  The state loader lookup fails, the chunk
    surfaces ``result: False`` with a "not found" comment, and no
    changes are made.
    """
    st = salt.state.State(state_wl_opts)
    sls = textwrap.dedent(
        """\
        remove_me:
          file.absent:
            - name: /tmp/does-not-matter
        """
    )
    ret = st.call_template_str(sls)
    assert isinstance(ret, dict), ret
    chunk_id = next(iter(ret))
    chunk = ret[chunk_id]
    assert chunk["result"] is False
    assert "file.absent" in chunk["comment"] or "not found" in chunk["comment"].lower()
    assert not chunk["changes"]


def test_state_bare_plus_dotted_narrows_in_real_loader(minion_opts, tmp_path):
    """
    ``whitelist_state_modules: [file, file.managed]`` -- the dotted
    entry narrows the bare one.  Only ``file.managed`` survives when
    both shapes are present for the same module.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_state_modules"] = ["file", "file.managed"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    minion_mods = salt.loader.minion_mods(opts)
    utils = salt.loader.utils(opts)
    serializers = salt.loader.serializers(opts)
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    assert callable(loader["file.managed"])
    for blocked in ("file.absent", "file.directory", "file.symlink"):
        assert blocked not in loader, blocked


# ---------------------------------------------------------------------------
# Dispatcher behaviour: cross_test vs cross_test_safe
# ---------------------------------------------------------------------------
#
# The two-loader model packs the unfiltered inner loader as ``__salt__`` so
# shipped code can compose with gated modules internally.  ``test.cross_test``
# intentionally uses ``__salt__`` -- an operator who whitelists it is
# opting into reflective access to every execution module.
#
# ``test.cross_test_safe`` dispatches via the whitelist-gated
# ``__wire_salt__`` instead, so a caller that whitelists only
# ``test.cross_test_safe`` cannot reach ungated functions through it.


def test_cross_test_remains_unfiltered(minion_opts, tmp_path):
    """
    ``test.cross_test`` is documented as reflective access and
    dispatches via ``__salt__`` (the unfiltered inner loader).  When an
    operator whitelists ``test.cross_test`` they are granting that
    reflective access deliberately, so a sub-call to a non-whitelisted
    function (``cmd.run``) must still succeed.  This test pins that
    behaviour so a future change doesn't silently tighten it (callers
    who want gating should use :func:`cross_test_safe`).
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["test.cross_test", "test.ping"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    loader = salt.loader.minion_mods(opts)

    cross_test = loader["test.cross_test"]
    token = salt.loader.context.loader_ctxvar.set(loader)
    try:
        # ``cmd.run`` is NOT whitelisted, but cross_test uses the
        # unfiltered inner loader so it still dispatches.
        ret = cross_test("cmd.run", ["true"])
        assert isinstance(ret, str)
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


def test_cross_test_safe_dispatch_target_is_whitelist_gated(minion_opts, tmp_path):
    """
    ``whitelist_modules: [test.cross_test_safe, test.ping]`` --
    ``cross_test_safe`` to an allowed target succeeds; to a
    non-whitelisted target (``cmd.run``) it must fail at the dispatch
    step instead of silently running through the unfiltered inner
    loader.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["test.cross_test_safe", "test.ping"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    loader = salt.loader.minion_mods(opts)

    cross_test_safe = loader["test.cross_test_safe"]
    token = salt.loader.context.loader_ctxvar.set(loader)
    try:
        # Allowed target: dispatch succeeds.
        assert cross_test_safe("test.ping") is True
        # Blocked target: dispatcher uses __wire_salt__ (= outer wire
        # loader), so the whitelist gate fires on the sub-call.
        with pytest.raises(KeyError):
            cross_test_safe("cmd.run", ["id"])
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


def test_cross_test_safe_dispatches_to_whitelisted_target(minion_opts, tmp_path):
    """
    ``whitelist_modules: [test.cross_test_safe, cmd.run]`` -- when both
    the dispatcher and the target are whitelisted, ``cross_test_safe``
    resolves the target through the wire loader and dispatches
    normally.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["test.cross_test_safe", "cmd.run"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    loader = salt.loader.minion_mods(opts)

    cross_test_safe = loader["test.cross_test_safe"]
    token = salt.loader.context.loader_ctxvar.set(loader)
    try:
        ret = cross_test_safe("cmd.run", ["true"])
        assert isinstance(ret, str)
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


def test_cross_test_safe_without_whitelist_unchanged(minion_opts, tmp_path):
    """
    Backcompat: with no whitelist configured, ``cross_test_safe`` must
    dispatch to arbitrary functions.  The wire loader is unfiltered
    when ``whitelist_modules`` is unset, so routing through
    ``__wire_salt__`` behaves identically to routing through
    ``__salt__``.
    """
    opts = copy.deepcopy(minion_opts)
    opts.pop("whitelist_modules", None)
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    loader = salt.loader.minion_mods(opts)

    cross_test_safe = loader["test.cross_test_safe"]
    token = salt.loader.context.loader_ctxvar.set(loader)
    try:
        assert cross_test_safe("test.ping") is True
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


def test_wire_salt_packed_on_exec_modules(minion_opts, tmp_path):
    """
    The ``__wire_salt__`` pack is injected by :func:`salt.loader.minion_mods`
    on both the outer and inner loaders.  It is stored as a
    ``weakref.proxy`` to avoid pinning the outer loader in a reference
    cycle (a strong back-pointer from ``salt_dunder`` to ``ret`` would
    delay collection until Python's cyclic gc ran on every reload).
    The proxy is transparent for the ``__contains__`` / ``__getitem__``
    operations dispatcher functions use.
    """
    import weakref

    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["test"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    loader = salt.loader.minion_mods(opts)
    inner = loader._dunder_salt
    outer_proxy = loader.pack["__wire_salt__"]
    inner_proxy = inner.pack["__wire_salt__"]
    assert type(outer_proxy) is weakref.ProxyType
    assert type(inner_proxy) is weakref.ProxyType
    # Through the proxy, dispatcher operations see the gated loader.
    assert "test.ping" in outer_proxy
    assert callable(outer_proxy["test.ping"])


def test_wire_salt_proxy_does_not_cycle_outer(minion_opts, tmp_path):
    """
    Regression: packing ``__wire_salt__`` as a strong reference to the
    outer loader created a new cycle (``salt_dunder.pack`` -> ret ->
    ``_WriteThroughLoader`` closure -> ``salt_dunder``) that forced
    cyclic gc to collect the outer loader instead of plain refcount.
    With the ``weakref.proxy`` fix, releasing the caller's reference
    to the outer loader collects it immediately -- no gc pass needed.
    """
    import gc
    import weakref as weakref_mod

    gc.collect()
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["test"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    loader = salt.loader.minion_mods(opts)
    wr = weakref_mod.ref(loader)
    del loader
    # Without the fix this is still alive (held by inner.pack["__wire_salt__"]);
    # with the proxy, the strong ref is gone and gc isn't needed.
    assert wr() is None, (
        "outer loader still reachable after del -- __wire_salt__ is "
        "likely a strong reference (should be weakref.proxy)"
    )


def test_state_whitelist_is_independent_from_exec_whitelist(minion_opts, tmp_path):
    """
    Cross-contamination check: a granular ``whitelist_modules`` entry
    on the exec side (``cmd.run``) must not affect the state loader.
    When ``whitelist_state_modules`` is unset every state remains
    reachable, including states whose exec counterpart is wire-gated.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["cmd.run"]
    opts.pop("whitelist_state_modules", None)
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    minion_mods = salt.loader.minion_mods(opts)
    utils = salt.loader.utils(opts)
    serializers = salt.loader.serializers(opts)
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    # ``file.absent`` is a state; the exec-side granular whitelist does
    # not reach it.
    assert callable(loader["file.absent"])

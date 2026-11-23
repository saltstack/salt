"""
Tests for the saltenv used when a state run autoloads dynamic modules.

``state.apply saltenv=qa`` has to sync ``_modules``/``_states``/... from the
``qa`` saltenv only. Every saltenv that gets synced lands in the same flat
``extension_modules`` directory, so any extra saltenv that sneaks into the sync
list overwrites the modules the requested saltenv just provided.
"""

import pytest

import salt.state
from salt.utils.datastructures import DefaultOrderedDict, HashableOrderedDict
from tests.support.mock import MagicMock

pytestmark = [
    pytest.mark.core_test,
]


class MockClient:
    def __init__(self, opts):
        self.opts = opts

    def master_opts(self):
        return self.opts

    def envs(self):
        return ["base", "qa"]

    def list_states(self, saltenv):
        return ["common", "foo"]

    def destroy(self):
        pass


class MockHighState(salt.state.BaseHighState):
    """
    Just enough of a HighState to drive ``top_matches``/``load_dynamic``.
    """

    def __init__(self, opts, ext_matches=None):
        self.client = MockClient(opts)
        self._ext_matches = ext_matches or {}
        self.sync_calls = []
        super().__init__(opts)
        self.matchers = {"confirm_top.confirm_top": MagicMock(return_value=True)}
        self.state = MagicMock()
        self.state.opts = self.opts
        self.state.functions = {"saltutil.sync_all": self._sync_all}

    def _sync_all(self, saltenv=None, refresh=True, **kwargs):
        self.sync_calls.append(saltenv)
        return {"grains": []}

    def _master_tops(self):
        return self._ext_matches

    def destroy(self):
        self.client.destroy()


@pytest.fixture
def highstate_opts(minion_opts):
    minion_opts["autoload_dynamic_modules"] = True
    minion_opts["file_roots"] = {"base": [], "qa": []}
    minion_opts["nodegroups"] = {}
    minion_opts["id"] = "minion"
    return minion_opts


def _top(data):
    return DefaultOrderedDict(HashableOrderedDict, data)


def test_load_dynamic_uses_requested_saltenv_with_master_tops(highstate_opts):
    """
    master_tops data for another saltenv must not drag that saltenv into the
    dynamic module sync when the run is pinned to a saltenv.
    """
    highstate_opts["saltenv"] = "qa"
    hs = MockHighState(highstate_opts, ext_matches={"base": ["common"]})

    hs.load_dynamic(hs.top_matches(_top({"qa": {"*": ["foo"]}})))

    assert hs.sync_calls == [["qa"]]


def test_load_dynamic_uses_requested_saltenv_with_cross_saltenv_include(
    highstate_opts,
):
    """
    A ``- base: common`` entry in the top file must not drag ``base`` into the
    dynamic module sync when the run is pinned to a saltenv.
    """
    highstate_opts["saltenv"] = "qa"
    hs = MockHighState(highstate_opts)

    matches = hs.top_matches(_top({"qa": {"*": ["foo", {"base": "common"}]}}))
    # the cross-saltenv include is still honored for state rendering
    assert "base" in matches

    hs.load_dynamic(matches)

    assert hs.sync_calls == [["qa"]]


def test_top_matches_ignores_master_tops_from_other_saltenvs(highstate_opts):
    """
    A saltenv-pinned run only considers master_tops data for that saltenv,
    matching how top file sections for other saltenvs are already skipped.
    """
    highstate_opts["saltenv"] = "qa"
    hs = MockHighState(highstate_opts, ext_matches={"base": ["common"], "qa": ["bar"]})

    matches = hs.top_matches(_top({"qa": {"*": ["foo"]}}))

    assert dict(matches) == {"qa": ["foo", "bar"]}


def test_top_matches_keeps_master_tops_when_no_saltenv_requested(highstate_opts):
    """
    Without an explicit saltenv, master_tops data for every saltenv is still
    merged in.
    """
    highstate_opts["saltenv"] = None
    hs = MockHighState(highstate_opts, ext_matches={"base": ["common"]})

    matches = hs.top_matches(_top({"qa": {"*": ["foo"]}}))

    assert dict(matches) == {"qa": ["foo"], "base": ["common"]}


def test_load_dynamic_syncs_matched_saltenvs_when_no_saltenv_requested(
    highstate_opts,
):
    """
    Without an explicit saltenv the matched saltenvs are synced, as before.
    """
    highstate_opts["saltenv"] = None
    hs = MockHighState(highstate_opts)

    hs.load_dynamic(
        hs.top_matches(_top({"base": {"*": ["common"]}, "qa": {"*": ["foo"]}}))
    )

    assert hs.sync_calls == [["base", "qa"]]


def test_load_dynamic_noop_when_autoload_disabled(highstate_opts):
    highstate_opts["saltenv"] = "qa"
    highstate_opts["autoload_dynamic_modules"] = False
    hs = MockHighState(highstate_opts)

    hs.load_dynamic(hs.top_matches(_top({"qa": {"*": ["foo"]}})))

    assert hs.sync_calls == []

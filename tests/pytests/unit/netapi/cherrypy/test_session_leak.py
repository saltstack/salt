"""
Unit tests for ``salt.netapi.rest_cherrypy.app._NoEmptyRamSession``.
"""

import datetime

import pytest

import salt.netapi.rest_cherrypy.app as cherrypy_app

pytest.importorskip("cherrypy")


@pytest.fixture
def clean_cache():
    """
    Empty ``RamSession.cache``/``locks`` before and after each test and
    restore whatever entries were there.
    """
    import cherrypy.lib.sessions as sessions

    saved_cache = sessions.RamSession.cache
    saved_locks = sessions.RamSession.locks
    sessions.RamSession.cache = {}
    sessions.RamSession.locks = {}
    try:
        yield sessions
    finally:
        sessions.RamSession.cache = saved_cache
        sessions.RamSession.locks = saved_locks


def _make_session(id="sid-1", data=None):
    sess = cherrypy_app._NoEmptyRamSession(id=id)
    sess._data = data or {}
    sess.loaded = True
    return sess


def test_noemptyramsession_is_ramsession_subclass():
    import cherrypy.lib.sessions as sessions

    assert issubclass(cherrypy_app._NoEmptyRamSession, sessions.RamSession)


def test_empty_session_is_not_persisted(clean_cache):
    sess = _make_session(id="empty-sid", data={})

    expiration = datetime.datetime.now() + datetime.timedelta(hours=10)
    sess._save(expiration)

    # Unauthenticated / no-op requests should not leave a cache entry
    # behind: this is the fix for the RamSession.cache pileup that
    # drove the salt-api rest_cherrypy RSS leak under sustained
    # anonymous / bad-token traffic.
    assert "empty-sid" not in clean_cache.RamSession.cache
    assert len(clean_cache.RamSession.cache) == 0


def test_populated_session_is_persisted(clean_cache):
    sess = _make_session(id=None, data={"token": "abc123"})
    real_id = sess.id
    assert real_id  # Session._regenerate() picks a fresh random id

    expiration = datetime.datetime.now() + datetime.timedelta(hours=10)
    sess._save(expiration)

    # A real logged-in session (with the salt auth token stashed in
    # session["token"]) must still be persisted so ``salt_auth_tool``
    # can find it on the next request.
    assert real_id in clean_cache.RamSession.cache
    data, exp = clean_cache.RamSession.cache[real_id]
    assert data == {"token": "abc123"}
    assert exp == expiration


def test_full_save_path_skips_empty_data(clean_cache):
    """
    Exercise the full ``Session.save()`` path (not just ``_save``): a
    session that was loaded but never had any data written to it must
    not end up in the cache when saved via CherryPy's own machinery.
    """
    sess = cherrypy_app._NoEmptyRamSession(id="pipeline-sid")
    # Simulate ``salt_auth_tool``'s ``"token" not in cherrypy.session``
    # touch: load() is called, sets ``loaded=True`` and leaves _data={}.
    sess.load()
    assert sess.loaded is True
    assert sess._data == {}
    sess.timeout = 60 * 10
    sess.save()

    assert "pipeline-sid" not in clean_cache.RamSession.cache


def test_full_save_path_persists_populated_data(clean_cache):
    sess = cherrypy_app._NoEmptyRamSession(id=None)
    real_id = sess.id
    sess.load()
    sess["token"] = "salt-tok-xyz"
    assert sess.loaded is True
    sess.timeout = 60 * 10
    sess.save()

    assert real_id in clean_cache.RamSession.cache
    data, _ = clean_cache.RamSession.cache[real_id]
    assert data == {"token": "salt-tok-xyz"}


def test_lowdataadapter_configures_the_noempty_session_class():
    # Regression guard: without this, CherryPy defaults back to
    # ``RamSession`` and every touched-but-not-written session gets
    # cached again.
    assert (
        cherrypy_app.LowDataAdapter._cp_config["tools.sessions.storage_class"]
        is cherrypy_app._NoEmptyRamSession
    )

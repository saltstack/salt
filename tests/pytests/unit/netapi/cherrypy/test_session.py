"""
Unit tests for the cache-backed CherryPy session store used by rest_cherrypy.
"""

import datetime
from types import SimpleNamespace

import pytest

import salt.cache
import salt.netapi.rest_cherrypy.app as cherrypy_app

cherrypy = pytest.importorskip("cherrypy")


@pytest.fixture
def session_cls(tmp_path):
    """
    Point SaltCacheSession at a throwaway localfs cache and reset the shared
    class state between tests.
    """
    saltopts = {
        "cache": "localfs",
        "cachedir": str(tmp_path),
        "extension_modules": "",
    }
    saved = cherrypy.config.get("saltopts")
    cherrypy.config["saltopts"] = saltopts
    cls = cherrypy_app.SaltCacheSession
    cls.setup(timeout=10, clean_freq=0)
    try:
        yield cls
    finally:
        cls.cache = None
        cls.locks = {}
        if saved is None:
            cherrypy.config.pop("saltopts", None)
        else:
            cherrypy.config["saltopts"] = saved


def _login(session_cls):
    """
    Mimic the worker that handled /login: CherryPy generates the session id
    (which is handed back to the client as the X-Auth-Token), the Salt token is
    stored inside the session, and the session is persisted.
    """
    sess = session_cls(id=None)
    sess.acquire_lock()
    sess["token"] = True
    sess.save()
    return sess


def test_setup_builds_cache(session_cls):
    assert isinstance(session_cls.cache, salt.cache.Cache)
    assert session_cls.cache.driver == "localfs"


def test_session_shared_across_workers(session_cls):
    """
    A session saved by one worker must be resolvable by another worker that
    only shares the cache -- this is the whole point of the backend.
    """
    sid = _login(session_cls).id

    other_worker = session_cls(id=sid)
    assert other_worker._exists()
    assert not other_worker.missing
    other_worker.acquire_lock()
    assert other_worker["token"] is True
    other_worker.release_lock()


def test_unknown_session_is_missing(session_cls):
    sess = session_cls(id="b" * 40)
    assert sess.missing
    # The unrecognised id is rejected and a fresh one generated.
    assert sess.id != "b" * 40


def test_expired_session_loads_empty(session_cls):
    sess = _login(session_cls)
    # Force the stored entry to be already expired.
    sess._save(sess.now() - datetime.timedelta(seconds=5))

    reloaded = session_cls(id=sess.id)
    reloaded.acquire_lock()
    reloaded.load()
    reloaded.release_lock()
    assert reloaded._data == {}


def test_clean_up_sweeps_expired_only(session_cls):
    live = _login(session_cls)
    dead = _login(session_cls)
    dead._save(dead.now() - datetime.timedelta(seconds=5))

    assert session_cls.cache.contains(session_cls.bank, dead.id)
    live.clean_up()

    assert not session_cls.cache.contains(session_cls.bank, dead.id)
    assert session_cls.cache.contains(session_cls.bank, live.id)


def test_delete_removes_session(session_cls):
    sess = _login(session_cls)
    assert sess._exists()
    sess.delete()
    assert not sess._exists()


def test_lookup_session_data_cache_backend(session_cls):
    """
    The EventSource/WebSocket out-of-band lookup must resolve the nested Salt
    token from a cache-backed session.
    """
    sess = _login(session_cls)
    cherrypy.serving.session = sess
    try:
        data = cherrypy_app._lookup_session_data(sess.id)
        assert data.get("token") is True
        # An unknown id resolves to an empty dict, not an error.
        assert cherrypy_app._lookup_session_data("0" * 40) == {}
    finally:
        cherrypy.serving.session = None


def test_lookup_session_data_ram_backend():
    """
    With the default in-RAM backend the lookup reads the class-level
    {id: (data, expiration)} mapping, unchanged from the previous behaviour.
    """
    fake_ram = SimpleNamespace(cache={"abc": ({"token": "salt-tok"}, None)})
    cherrypy.serving.session = fake_ram
    try:
        assert cherrypy_app._lookup_session_data("abc") == {"token": "salt-tok"}
        assert cherrypy_app._lookup_session_data("missing") == {}
    finally:
        cherrypy.serving.session = None


def test_get_conf_enables_cache_session_store():
    api = cherrypy_app.API.__new__(cherrypy_app.API)
    api.apiopts = {"session_store": "cache"}
    conf = api.get_conf()
    assert conf["/"]["tools.sessions.storage_class"] is cherrypy_app.SaltCacheSession


def test_get_conf_defaults_to_ram():
    api = cherrypy_app.API.__new__(cherrypy_app.API)
    api.apiopts = {}
    conf = api.get_conf()
    assert "tools.sessions.storage_class" not in conf["/"]

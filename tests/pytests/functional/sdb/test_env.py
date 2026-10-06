import salt.sdb.env as env


def test_set_and_get(monkeypatch):
    """
    A value set through sdb.env can be read back through it.
    """
    monkeypatch.delenv("SALT_SDB_ENV_TEST", raising=False)
    assert env.set_("SALT_SDB_ENV_TEST", "hello") == "hello"
    assert env.get("SALT_SDB_ENV_TEST") == "hello"


def test_get_missing_returns_none(monkeypatch):
    """
    Looking up an unset environment variable returns None.
    """
    monkeypatch.delenv("SALT_SDB_ENV_MISSING", raising=False)
    assert env.get("SALT_SDB_ENV_MISSING") is None


def test_set_does_not_overwrite_existing(monkeypatch):
    """
    sdb.env.set_ uses ``os.environ.setdefault``, so it leaves an already-set
    variable untouched and returns the existing value.
    """
    monkeypatch.setenv("SALT_SDB_ENV_EXISTING", "original")
    assert env.set_("SALT_SDB_ENV_EXISTING", "new") == "original"
    assert env.get("SALT_SDB_ENV_EXISTING") == "original"

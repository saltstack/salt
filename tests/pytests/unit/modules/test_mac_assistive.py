import sqlite3

import pytest

import salt.modules.mac_assistive as assistive
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch

# DO NOT CHANGE THE SCHEMA BELLOW TO SPLIT LINES, ETC.
# A sha1sum of it will be used to decide which schema to use
BIGSUR_DB_SCHEMA = """\
CREATE TABLE admin (key TEXT PRIMARY KEY NOT NULL, value INTEGER NOT NULL);
CREATE TABLE policies ( id              INTEGER NOT NULL PRIMARY KEY,   bundle_id       TEXT    NOT NULL,       uuid            TEXT    NOT NULL,       display         TEXT    NOT NULL,       UNIQUE (bundle_id, uuid));
CREATE TABLE active_policy (    client          TEXT    NOT NULL,       client_type     INTEGER NOT NULL,       policy_id       INTEGER NOT NULL,       PRIMARY KEY (client, client_type),      FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE ON UPDATE CASCADE);
CREATE INDEX active_policy_id ON active_policy(policy_id);
CREATE TABLE access_overrides ( service         TEXT    NOT NULL PRIMARY KEY);
CREATE TABLE expired (    service        TEXT        NOT NULL,     client         TEXT        NOT NULL,     client_type    INTEGER     NOT NULL,     csreq          BLOB,     last_modified  INTEGER     NOT NULL ,     expired_at     INTEGER     NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),     PRIMARY KEY (service, client, client_type));
CREATE TABLE IF NOT EXISTS "access" (    service        TEXT        NOT NULL,     client         TEXT        NOT NULL,     client_type    INTEGER     NOT NULL,     auth_value     INTEGER     NOT NULL,     auth_reason    INTEGER     NOT NULL,     auth_version   INTEGER     NOT NULL,     csreq          BLOB,     policy_id      INTEGER,     indirect_object_identifier_type    INTEGER,     indirect_object_identifier         TEXT NOT NULL DEFAULT 'UNUSED',     indirect_object_code_identity      BLOB,     flags          INTEGER,     last_modified  INTEGER     NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),     PRIMARY KEY (service, client, client_type, indirect_object_identifier),    FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE ON UPDATE CASCADE);
"""
CATALINA_DB_SCHEMA = """\
CREATE TABLE admin (key TEXT PRIMARY KEY NOT NULL, value INTEGER NOT NULL);
CREATE TABLE policies ( id              INTEGER NOT NULL PRIMARY KEY,   bundle_id       TEXT    NOT NULL,       uuid            TEXT    NOT NULL,       display         TEXT    NOT NULL,       UNIQUE (bundle_id, uuid));
CREATE TABLE active_policy (    client          TEXT    NOT NULL,       client_type     INTEGER NOT NULL,       policy_id       INTEGER NOT NULL,       PRIMARY KEY (client, client_type),      FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE ON UPDATE CASCADE);
CREATE INDEX active_policy_id ON active_policy(policy_id);
CREATE TABLE access_overrides ( service         TEXT    NOT NULL PRIMARY KEY);
CREATE TABLE expired (    service        TEXT        NOT NULL,     client         TEXT        NOT NULL,     client_type    INTEGER     NOT NULL,     csreq          BLOB,     last_modified  INTEGER     NOT NULL ,     expired_at     INTEGER     NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),     PRIMARY KEY (service, client, client_type));
CREATE TABLE IF NOT EXISTS "access" (    service        TEXT        NOT NULL,     client         TEXT        NOT NULL,     client_type    INTEGER     NOT NULL,     auth_value     INTEGER     NOT NULL,     auth_reason    INTEGER     NOT NULL,     auth_version   INTEGER     NOT NULL,     csreq          BLOB,     policy_id      INTEGER,     indirect_object_identifier_type    INTEGER,     indirect_object_identifier         TEXT NOT NULL DEFAULT 'UNUSED',     indirect_object_code_identity      BLOB,     flags          INTEGER,     last_modified  INTEGER     NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),     PRIMARY KEY (service, client, client_type, indirect_object_identifier),    FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE ON UPDATE CASCADE);
"""


@pytest.fixture(params=("Catalina", "BigSur"))
def macos_version(request):
    return request.param


@pytest.fixture(autouse=True)
def tcc_db_path(tmp_path, macos_version):
    db = tmp_path / "tcc.db"
    if macos_version == "BigSur":
        schema = BIGSUR_DB_SCHEMA
    elif macos_version == "Catalina":
        schema = CATALINA_DB_SCHEMA
    else:
        # A new macOS version?
        # Spin a VM and run the following:
        #    sudo sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db"
        #
        # Then, when the DB is open in sqlite,  issue the following
        #   .schema
        #
        # Copy/Paste the output of that to this test.
        pytest.fail("Don't know how to handle {}".format(macos_version))
    conn = sqlite3.connect(str(db))
    with conn:
        for stmt in schema.splitlines():
            conn.execute(stmt)
    return str(db)


@pytest.fixture
def configure_loader_modules(tcc_db_path):
    return {assistive: {"TCC_DB_PATH": tcc_db_path}}


def test_install_assistive_bundle():
    """
    Test installing a bundle ID as being allowed to run with assistive access
    """
    assert assistive.install("foo")


def test_install_assistive_error():
    """
    Test installing a bundle ID as being allowed to run with assistive access
    """
    with patch.object(assistive.TccDB, "install", side_effect=sqlite3.Error("Foo")):
        pytest.raises(CommandExecutionError, assistive.install, "foo")


def test_installed_bundle():
    """
    Test checking to see if a bundle id is installed as being able to use assistive access
    """
    assistive.install("foo")
    assert assistive.installed("foo")


def test_installed_bundle_not():
    """
    Test checking to see if a bundle id is installed as being able to use assistive access
    """
    assert not assistive.installed("foo")


def test_enable_assistive():
    """
    Test enabling a bundle ID as being allowed to run with assistive access
    """
    assistive.install("foo", enable=False)
    assert assistive.enable_("foo", True)


def test_enable_error():
    """
    Test enabled a bundle ID that throws a command error
    """
    with patch.object(assistive.TccDB, "enable", side_effect=sqlite3.Error("Foo")):
        pytest.raises(CommandExecutionError, assistive.enable_, "foo")


def test_enable_false():
    """
    Test return of enable function when app isn't found.
    """
    assert not assistive.enable_("foo")


def test_enabled_assistive():
    """
    Test enabling a bundle ID as being allowed to run with assistive access
    """
    assistive.install("foo")
    assert assistive.enabled("foo")


def test_enabled_assistive_false():
    """
    Test if a bundle ID is disabled for assistive access
    """
    assistive.install("foo", enable=False)
    assert not assistive.enabled("foo")


def test_remove_assistive():
    """
    Test removing an assitive bundle.
    """
    assistive.install("foo")
    assert assistive.remove("foo")


def test_remove_assistive_error():
    """
    Test removing an assitive bundle.
    """
    with patch.object(assistive.TccDB, "remove", side_effect=sqlite3.Error("Foo")):
        pytest.raises(CommandExecutionError, assistive.remove, "foo")

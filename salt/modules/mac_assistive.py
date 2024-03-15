"""
This module allows you to manage assistive access on macOS minions with 10.9+

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' assistive.install /usr/bin/osascript
"""

import hashlib
import logging
import sqlite3
import time

import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from salt.utils.versions import Version

log = logging.getLogger(__name__)

__virtualname__ = "assistive"
__func_alias__ = {"enable_": "enable"}

TCC_DB_PATH = "/Library/Application Support/com.apple.TCC/TCC.db"


def __virtual__():
    """
    Only work on Mac OS
    """
    if not salt.utils.platform.is_darwin():
        return False, "Must be run on macOS"
    if Version(__grains__["osrelease"]) < Version("10.9"):
        return False, "Must be run on macOS 10.9 or newer"
    return __virtualname__


def install(app_id, enable=True, tries=3, wait=10):
    """
    Install a bundle ID or command as being allowed to use
    assistive access.

    app_id
        The bundle ID or command to install for assistive access.

    enabled
        Sets enabled or disabled status. Default is ``True``.

    tries
        How many times to try and write to a read-only tcc. Default is ``True``.

    wait
        Number of seconds to wait between tries. Default is ``10``.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.install /usr/bin/osascript
        salt '*' assistive.install com.smileonmymac.textexpander
    """
    num_tries = 1
    while True:
        with TccDB() as db:
            try:
                return db.install(app_id, enable=enable)
            except sqlite3.Error as exc:
                if "attempt to write a readonly database" not in str(exc):
                    raise CommandExecutionError(
                        f"Error installing app({app_id}): {exc}"
                    )
                elif num_tries < tries:
                    num_tries += 1
                else:
                    raise CommandExecutionError(
                        f"Error installing app({app_id}): {exc}"
                    )
        time.sleep(wait)


def installed(app_id):
    """
    Check if a bundle ID or command is listed in assistive access.
    This will not check to see if it's enabled.

    app_id
        The bundle ID or command to check installed status.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.installed /usr/bin/osascript
        salt '*' assistive.installed com.smileonmymac.textexpander
    """
    with TccDB() as db:
        try:
            return db.installed(app_id)
        except sqlite3.Error as exc:
            raise CommandExecutionError(
                f"Error checking if app({app_id}) is installed: {exc}"
            )


def enable_(app_id, enabled=True):
    """
    Enable or disable an existing assistive access application.

    app_id
        The bundle ID or command to set assistive access status.

    enabled
        Sets enabled or disabled status. Default is ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.enable /usr/bin/osascript
        salt '*' assistive.enable com.smileonmymac.textexpander enabled=False
    """
    with TccDB() as db:
        try:
            if enabled:
                return db.enable(app_id)
            else:
                return db.disable(app_id)
        except sqlite3.Error as exc:
            raise CommandExecutionError(
                f"Error setting enable to {enabled} on app({app_id}): {exc}"
            )


def enabled(app_id):
    """
    Check if a bundle ID or command is listed in assistive access and
    enabled.

    app_id
        The bundle ID or command to retrieve assistive access status.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.enabled /usr/bin/osascript
        salt '*' assistive.enabled com.smileonmymac.textexpander
    """
    with TccDB() as db:
        try:
            return db.enabled(app_id)
        except sqlite3.Error as exc:
            raise CommandExecutionError(
                f"Error checking if app({app_id}) is enabled: {exc}"
            )


def remove(app_id):
    """
    Remove a bundle ID or command as being allowed to use assistive access.

    app_id
        The bundle ID or command to remove from assistive access list.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.remove /usr/bin/osascript
        salt '*' assistive.remove com.smileonmymac.textexpander
    """
    with TccDB() as db:
        try:
            return db.remove(app_id)
        except sqlite3.Error as exc:
            raise CommandExecutionError(f"Error removing app({app_id}): {exc}")


class TccDB:
    def __init__(self, path=None):
        if path is None:
            path = TCC_DB_PATH
        self.path = path
        self.connection = None
        self.ge_mojave_and_catalina = False
        self.ge_bigsur_and_later = False

    def _check_table_digest(self):
        # This logic comes from https://github.com/jacobsalmela/tccutil which is
        # Licensed under GPL-2.0
        cursor = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='access' and type='table'"
        )
        for row in cursor.fetchall():
            digest = hashlib.sha1(row["sql"].encode()).hexdigest()[:10]
            if digest in ("ecc443615f", "80a4bb6912"):
                # Mojave and Catalina
                self.ge_mojave_and_catalina = True
            elif digest in ("3d1c2a0e97", "cef70648de"):
                # BigSur and later
                self.ge_bigsur_and_later = True
            else:
                raise CommandExecutionError(
                    f"TCC Database structure unknown for digest '{digest}'"
                )

    def _get_client_type(self, app_id):
        if app_id[0] == "/":
            # This is a command line utility
            return 1
        # This is a bundle ID
        return 0

    def installed(self, app_id):
        cursor = self.connection.execute(
            "SELECT * from access WHERE client=? and service='kTCCServiceAccessibility'",
            (app_id,),
        )
        for row in cursor.fetchall():
            if row:
                return True
        return False

    def install(self, app_id, enable=True):
        client_type = self._get_client_type(app_id)
        auth_value = 1 if enable else 0
        if self.ge_bigsur_and_later:
            # CREATE TABLE IF NOT EXISTS "access" (
            #   service        TEXT        NOT NULL,
            #   client         TEXT        NOT NULL,
            #   client_type    INTEGER     NOT NULL,
            #   auth_value     INTEGER     NOT NULL,
            #   auth_reason    INTEGER     NOT NULL,
            #   auth_version   INTEGER     NOT NULL,
            #   csreq          BLOB,     policy_id      INTEGER,
            #   indirect_object_identifier_type    INTEGER,
            #   indirect_object_identifier         TEXT NOT NULL DEFAULT 'UNUSED',
            #   indirect_object_code_identity      BLOB,
            #   flags          INTEGER,
            #   last_modified  INTEGER     NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),
            #   PRIMARY KEY (
            #       service,
            #       client,
            #       client_type,
            #       indirect_object_identifier
            #   ),
            #   FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE ON UPDATE CASCADE);
            self.connection.execute(
                """
                    INSERT or REPLACE INTO access VALUES (
                        'kTCCServiceAccessibility',
                        ?,
                        ?,
                        ?,
                        4,
                        1,
                        NULL,
                        NULL,
                        0,
                        'UNUSED',
                        NULL,
                        0,
                        0
                    )
                    """,
                (app_id, client_type, auth_value),
            )
            self.connection.commit()
        elif self.ge_mojave_and_catalina:
            # CREATE TABLE IF NOT EXISTS "access" (
            #   service        TEXT        NOT NULL,
            #   client         TEXT        NOT NULL,
            #   client_type    INTEGER     NOT NULL,
            #   allowed        INTEGER     NOT NULL,
            #   prompt_count   INTEGER     NOT NULL,
            #   csreq          BLOB,
            #   policy_id      INTEGER,
            #   indirect_object_identifier_type    INTEGER,
            #   indirect_object_identifier         TEXT DEFAULT 'UNUSED',
            #   indirect_object_code_identity      BLOB,
            #   flags          INTEGER,
            #   last_modified  INTEGER     NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),
            #   PRIMARY KEY (
            #       service,
            #       client,
            #       client_type,
            #       indirect_object_identifier
            #   ),
            #   FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE ON UPDATE CASCADE);
            self.connection.execute(
                """
                    INSERT or REPLACE INTO access VALUES(
                        'kTCCServiceAccessibility',
                        ?,
                        ?,
                        ?,
                        1,
                        NULL,
                        NULL,
                        NULL,
                        'UNUSED',
                        NULL,
                        0,
                        0
                    )
                    """,
                (app_id, client_type, auth_value),
            )
            self.connection.commit()
        return True

    def enabled(self, app_id):
        if self.ge_bigsur_and_later:
            column = "auth_value"
        elif self.ge_mojave_and_catalina:
            column = "allowed"
        cursor = self.connection.execute(
            "SELECT * from access WHERE client=? and service='kTCCServiceAccessibility'",
            (app_id,),
        )
        for row in cursor.fetchall():
            if row[column]:
                return True
        return False

    def enable(self, app_id):
        if not self.installed(app_id):
            return False
        if self.ge_bigsur_and_later:
            column = "auth_value"
        elif self.ge_mojave_and_catalina:
            column = "allowed"
        self.connection.execute(
            "UPDATE access SET {} = ? WHERE client=? AND service IS 'kTCCServiceAccessibility'".format(
                column
            ),
            (1, app_id),
        )
        self.connection.commit()
        return True

    def disable(self, app_id):
        if not self.installed(app_id):
            return False
        if self.ge_bigsur_and_later:
            column = "auth_value"
        elif self.ge_mojave_and_catalina:
            column = "allowed"
        self.connection.execute(
            "UPDATE access SET {} = ? WHERE client=? AND service IS 'kTCCServiceAccessibility'".format(
                column
            ),
            (0, app_id),
        )
        self.connection.commit()
        return True

    def remove(self, app_id):
        if not self.installed(app_id):
            return False
        self.connection.execute(
            "DELETE from access where client IS ? AND service IS 'kTCCServiceAccessibility'",
            (app_id,),
        )
        self.connection.commit()
        return True

    def __enter__(self):
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._check_table_digest()
        return self

    def __exit__(self, *_):
        self.connection.close()

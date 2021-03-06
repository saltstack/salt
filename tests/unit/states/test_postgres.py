import salt.modules.postgres as postgresmod
import salt.states.postgres_extension as postgres_extension
import salt.states.postgres_schema as postgres_schema
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase


class PostgresExtensionTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        patcher = patch("salt.utils.path.which", Mock(return_value="/usr/bin/pgsql"))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            postgres_extension: {
                "__grains__": {"os_family": "Linux"},
                "__salt__": {
                    "config.option": Mock(),
                    "cmd.run_all": Mock(),
                    "file.chown": Mock(),
                    "file.remove": Mock(),
                },
                "__opts__": {"test": False},
            },
        }

    def test_present_failed(self):
        """
        scenario of creating upgrading extensions with possible schema and
        version specifications
        """
        with patch.dict(
            postgres_extension.__salt__,
            {
                "postgres.create_metadata": Mock(
                    side_effect=[
                        [postgresmod._EXTENSION_NOT_INSTALLED],
                        [
                            postgresmod._EXTENSION_TO_MOVE,
                            postgresmod._EXTENSION_INSTALLED,
                        ],
                    ]
                ),
                "postgres.create_extension": Mock(side_effect=[False, False]),
            },
        ):
            ret = postgres_extension.present("foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Failed to install extension foo",
                    "changes": {},
                    "name": "foo",
                    "result": False,
                },
            )
            ret = postgres_extension.present("foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Failed to upgrade extension foo",
                    "changes": {},
                    "name": "foo",
                    "result": False,
                },
            )

    def test_present(self):
        """
        scenario of creating upgrading extensions with possible schema and
        version specifications
        """
        with patch.dict(
            postgres_extension.__salt__,
            {
                "postgres.create_metadata": Mock(
                    side_effect=[
                        [postgresmod._EXTENSION_NOT_INSTALLED],
                        [postgresmod._EXTENSION_INSTALLED],
                        [
                            postgresmod._EXTENSION_TO_MOVE,
                            postgresmod._EXTENSION_INSTALLED,
                        ],
                    ]
                ),
                "postgres.create_extension": Mock(side_effect=[True, True, True]),
            },
        ):
            ret = postgres_extension.present("foo")
            self.assertEqual(
                ret,
                {
                    "comment": "The extension foo has been installed",
                    "changes": {"foo": "Installed"},
                    "name": "foo",
                    "result": True,
                },
            )
            ret = postgres_extension.present("foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Extension foo is already present",
                    "changes": {},
                    "name": "foo",
                    "result": True,
                },
            )
            ret = postgres_extension.present("foo")
            self.assertEqual(
                ret,
                {
                    "comment": "The extension foo has been upgraded",
                    "changes": {"foo": "Upgraded"},
                    "name": "foo",
                    "result": True,
                },
            )

    def test_presenttest(self):
        """
        scenario of creating upgrading extensions with possible schema and
        version specifications
        """
        with patch.dict(
            postgres_extension.__salt__,
            {
                "postgres.create_metadata": Mock(
                    side_effect=[
                        [postgresmod._EXTENSION_NOT_INSTALLED],
                        [postgresmod._EXTENSION_INSTALLED],
                        [
                            postgresmod._EXTENSION_TO_MOVE,
                            postgresmod._EXTENSION_INSTALLED,
                        ],
                    ]
                ),
                "postgres.create_extension": Mock(side_effect=[True, True, True]),
            },
        ):
            with patch.dict(postgres_extension.__opts__, {"test": True}):
                ret = postgres_extension.present("foo")
                self.assertEqual(
                    ret,
                    {
                        "comment": "Extension foo is set to be installed",
                        "changes": {},
                        "name": "foo",
                        "result": None,
                    },
                )
                ret = postgres_extension.present("foo")
                self.assertEqual(
                    ret,
                    {
                        "comment": "Extension foo is already present",
                        "changes": {},
                        "name": "foo",
                        "result": True,
                    },
                )
                ret = postgres_extension.present("foo")
                self.assertEqual(
                    ret,
                    {
                        "comment": "Extension foo is set to be upgraded",
                        "changes": {},
                        "name": "foo",
                        "result": None,
                    },
                )

    def test_absent(self):
        """
        scenario of creating upgrading extensions with possible schema and
        version specifications
        """
        with patch.dict(
            postgres_extension.__salt__,
            {
                "postgres.is_installed_extension": Mock(side_effect=[True, False]),
                "postgres.drop_extension": Mock(side_effect=[True, True]),
            },
        ):
            ret = postgres_extension.absent("foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Extension foo has been removed",
                    "changes": {"foo": "Absent"},
                    "name": "foo",
                    "result": True,
                },
            )
            ret = postgres_extension.absent("foo")
            self.assertEqual(
                ret,
                {
                    "comment": (
                        "Extension foo is not present, " "so it cannot be removed"
                    ),
                    "changes": {},
                    "name": "foo",
                    "result": True,
                },
            )

    def test_absent_failed(self):
        """
        scenario of creating upgrading extensions with possible schema and
        version specifications
        """
        with patch.dict(postgres_extension.__opts__, {"test": False}):
            with patch.dict(
                postgres_extension.__salt__,
                {
                    "postgres.is_installed_extension": Mock(side_effect=[True, True]),
                    "postgres.drop_extension": Mock(side_effect=[False, False]),
                },
            ):
                ret = postgres_extension.absent("foo")
                self.assertEqual(
                    ret,
                    {
                        "comment": "Extension foo failed to be removed",
                        "changes": {},
                        "name": "foo",
                        "result": False,
                    },
                )

    def test_absent_failedtest(self):
        with patch.dict(
            postgres_extension.__salt__,
            {
                "postgres.is_installed_extension": Mock(side_effect=[True, True]),
                "postgres.drop_extension": Mock(side_effect=[False, False]),
            },
        ):
            with patch.dict(postgres_extension.__opts__, {"test": True}):
                ret = postgres_extension.absent("foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Extension foo is set to be removed",
                    "changes": {},
                    "name": "foo",
                    "result": None,
                },
            )


class PostgresSchemaTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        patcher = patch("salt.utils.path.which", Mock(return_value="/usr/bin/pgsql"))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            postgres_schema: {
                "__grains__": {"os_family": "Linux"},
                "__salt__": {
                    "config.option": Mock(),
                    "cmd.run_all": Mock(),
                    "file.chown": Mock(),
                    "file.remove": Mock(),
                },
                "__opts__": {"test": False},
            },
        }

    def test_present_creation(self):
        with patch.dict(
            postgres_schema.__salt__,
            {
                "postgres.schema_get": Mock(return_value=None),
                "postgres.schema_create": MagicMock(),
            },
        ):
            ret = postgres_schema.present("dbname", "foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Schema foo has been created in database dbname",
                    "changes": {"foo": "Present"},
                    "dbname": "dbname",
                    "name": "foo",
                    "result": True,
                },
            )
            self.assertEqual(
                postgres_schema.__salt__["postgres.schema_create"].call_count, 1
            )

    def test_present_nocreation(self):
        with patch.dict(
            postgres_schema.__salt__,
            {
                "postgres.schema_get": Mock(
                    return_value={"foo": {"acl": "", "owner": "postgres"}}
                ),
                "postgres.schema_create": MagicMock(),
            },
        ):
            ret = postgres_schema.present("dbname", "foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Schema foo already exists in database dbname",
                    "changes": {},
                    "dbname": "dbname",
                    "name": "foo",
                    "result": True,
                },
            )
            self.assertEqual(
                postgres_schema.__salt__["postgres.schema_create"].call_count, 0
            )

    def test_absent_remove(self):
        with patch.dict(
            postgres_schema.__salt__,
            {
                "postgres.schema_exists": Mock(return_value=True),
                "postgres.schema_remove": MagicMock(),
            },
        ):
            ret = postgres_schema.absent("dbname", "foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Schema foo has been removed from database dbname",
                    "changes": {"foo": "Absent"},
                    "dbname": "dbname",
                    "name": "foo",
                    "result": True,
                },
            )
            self.assertEqual(
                postgres_schema.__salt__["postgres.schema_remove"].call_count, 1
            )

    def test_absent_noremove(self):
        with patch.dict(
            postgres_schema.__salt__,
            {
                "postgres.schema_exists": Mock(return_value=False),
                "postgres.schema_remove": MagicMock(),
            },
        ):
            ret = postgres_schema.absent("dbname", "foo")
            self.assertEqual(
                ret,
                {
                    "comment": "Schema foo is not present in database dbname,"
                    " so it cannot be removed",
                    "changes": {},
                    "dbname": "dbname",
                    "name": "foo",
                    "result": True,
                },
            )
            self.assertEqual(
                postgres_schema.__salt__["postgres.schema_remove"].call_count, 0
            )

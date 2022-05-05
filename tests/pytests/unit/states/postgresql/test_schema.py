import pytest
import salt.states.postgres_schema as postgres_schema
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def configure_loader_modules():
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


def test_present_creation():
    with patch.dict(
        postgres_schema.__salt__,
        {
            "postgres.schema_get": Mock(return_value=None),
            "postgres.schema_create": MagicMock(),
        },
    ):
        ret = postgres_schema.present("dbname", "foo")
        assert ret == {
            "comment": "Schema foo has been created in database dbname",
            "changes": {"foo": "Present"},
            "dbname": "dbname",
            "name": "foo",
            "result": True,
        }
        assert postgres_schema.__salt__["postgres.schema_create"].call_count == 1


def test_present_nocreation():
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
        assert ret == {
            "comment": "Schema foo already exists in database dbname",
            "changes": {},
            "dbname": "dbname",
            "name": "foo",
            "result": True,
        }
        assert postgres_schema.__salt__["postgres.schema_create"].call_count == 0


def test_absent_remove():
    with patch.dict(
        postgres_schema.__salt__,
        {
            "postgres.schema_exists": Mock(return_value=True),
            "postgres.schema_remove": MagicMock(),
        },
    ):
        ret = postgres_schema.absent("dbname", "foo")
        assert ret == {
            "comment": "Schema foo has been removed from database dbname",
            "changes": {"foo": "Absent"},
            "dbname": "dbname",
            "name": "foo",
            "result": True,
        }
        assert postgres_schema.__salt__["postgres.schema_remove"].call_count == 1


def test_absent_noremove():
    with patch.dict(
        postgres_schema.__salt__,
        {
            "postgres.schema_exists": Mock(return_value=False),
            "postgres.schema_remove": MagicMock(),
        },
    ):
        ret = postgres_schema.absent("dbname", "foo")
        assert ret == {
            "comment": (
                "Schema foo is not present in database dbname, so it cannot be removed"
            ),
            "changes": {},
            "dbname": "dbname",
            "name": "foo",
            "result": True,
        }
        assert postgres_schema.__salt__["postgres.schema_remove"].call_count == 0

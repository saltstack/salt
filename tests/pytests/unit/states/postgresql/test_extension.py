import pytest
import salt.modules.postgres as postgresmod
import salt.states.postgres_extension as postgres_extension
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        postgres_extension: {
            "__grains__": {"os_family": "linux"},
            "__salt__": {
                "config.option": Mock(),
                "cmd.run_all": Mock(),
                "file.chown": Mock(),
                "file.remove": Mock(),
            },
            "__opts__": {"test": False},
        },
    }


def test_present_failed():
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
                    [postgresmod._EXTENSION_TO_MOVE, postgresmod._EXTENSION_INSTALLED],
                ]
            ),
            "postgres.create_extension": Mock(side_effect=[False, False]),
        },
    ):
        ret = postgres_extension.present("foo")
        assert ret == {
            "comment": "Failed to install extension foo",
            "changes": {},
            "name": "foo",
            "result": False,
        }
        ret = postgres_extension.present("foo")
        assert ret == {
            "comment": "Failed to upgrade extension foo",
            "changes": {},
            "name": "foo",
            "result": False,
        }


def test_present():
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
                    [postgresmod._EXTENSION_TO_MOVE, postgresmod._EXTENSION_INSTALLED],
                ]
            ),
            "postgres.create_extension": Mock(side_effect=[True, True, True]),
        },
    ):
        ret = postgres_extension.present("foo")
        assert ret == {
            "comment": "The extension foo has been installed",
            "changes": {"foo": "Installed"},
            "name": "foo",
            "result": True,
        }
        ret = postgres_extension.present("foo")
        assert ret == {
            "comment": "Extension foo is already present",
            "changes": {},
            "name": "foo",
            "result": True,
        }
        ret = postgres_extension.present("foo")
        assert ret == {
            "comment": "The extension foo has been upgraded",
            "changes": {"foo": "Upgraded"},
            "name": "foo",
            "result": True,
        }


def test_presenttest():
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
                    [postgresmod._EXTENSION_TO_MOVE, postgresmod._EXTENSION_INSTALLED],
                ]
            ),
            "postgres.create_extension": Mock(side_effect=[True, True, True]),
        },
    ):
        with patch.dict(postgres_extension.__opts__, {"test": True}):
            ret = postgres_extension.present("foo")
            assert ret == {
                "comment": "Extension foo is set to be installed",
                "changes": {},
                "name": "foo",
                "result": None,
            }
            ret = postgres_extension.present("foo")
            assert ret == {
                "comment": "Extension foo is already present",
                "changes": {},
                "name": "foo",
                "result": True,
            }
            ret = postgres_extension.present("foo")
            assert ret == {
                "comment": "Extension foo is set to be upgraded",
                "changes": {},
                "name": "foo",
                "result": None,
            }


def test_absent():
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
        assert ret == {
            "comment": "Extension foo has been removed",
            "changes": {"foo": "Absent"},
            "name": "foo",
            "result": True,
        }
        ret = postgres_extension.absent("foo")
        assert ret == {
            "comment": "Extension foo is not present, so it cannot be removed",
            "changes": {},
            "name": "foo",
            "result": True,
        }


def test_absent_failed():
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
            assert ret == {
                "comment": "Extension foo failed to be removed",
                "changes": {},
                "name": "foo",
                "result": False,
            }


def test_absent_failedtest():
    with patch.dict(
        postgres_extension.__salt__,
        {
            "postgres.is_installed_extension": Mock(side_effect=[True, True]),
            "postgres.drop_extension": Mock(side_effect=[False, False]),
        },
    ):
        with patch.dict(postgres_extension.__opts__, {"test": True}):
            ret = postgres_extension.absent("foo")
        assert ret == {
            "comment": "Extension foo is set to be removed",
            "changes": {},
            "name": "foo",
            "result": None,
        }

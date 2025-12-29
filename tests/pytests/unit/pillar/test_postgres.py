import pytest

import salt.pillar.postgres as postgres
from tests.support.mock import MagicMock, patch

try:
    import psycopg2  # pylint: disable=unused-import

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
pytestmark = [
    pytest.mark.skipif(not HAS_POSTGRES, reason="Package psycopg2 is not installed."),
]


def test_should_pass_ssl_args():
    postgres_opts = {
        "postgres": {
            "host": "postgres",
            "sslmode": "verify-ca",
            "sslcert": "/path/to/sslcert",
            "sslkey": "/path/to/sslkey",
            "sslrootcert": "/path/to/sslrootcert",
            "sslcrl": "/path/to/sslcrl",
            "kwargs": {"application_name": "salt"},
        }
    }
    with (
        patch("salt.pillar.postgres.__opts__", postgres_opts, create=True),
        patch("psycopg2.connect", MagicMock()) as connect_mock,
    ):
        postgres.ext_pillar("test", {})
    connect_mock.assert_called_with(
        host="postgres",
        user="salt",
        password="salt",
        dbname="salt",
        port=5432,
        sslmode="verify-ca",
        sslcert="/path/to/sslcert",
        sslkey="/path/to/sslkey",
        sslrootcert="/path/to/sslrootcert",
        sslcrl="/path/to/sslcrl",
        application_name="salt",
    )


def test_should_pass_default_args():
    postgres_opts = {}
    with (
        patch("salt.pillar.postgres.__opts__", postgres_opts, create=True),
        patch("psycopg2.connect", MagicMock()) as connect_mock,
    ):
        postgres.ext_pillar("test", {})
    connect_mock.assert_called_with(
        host="localhost",
        user="salt",
        password="salt",
        dbname="salt",
        port=5432,
        sslmode="prefer",
        sslcert=None,
        sslkey=None,
        sslrootcert=None,
        sslcrl=None,
    )

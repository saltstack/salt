"""
    tests.unit.returners.cassandra_cql_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import ssl

import salt.modules.cassandra_cql as cassandra_cql
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import cassandra  # pylint: disable=unused-import,wrong-import-position

    HAS_CASSANDRA = True
except ImportError:
    HAS_CASSANDRA = False


@skipIf(
    not HAS_CASSANDRA,
    "Please install the cassandra datastax driver to run cassandra_cql module unit"
    " tests.",
)
class CassandraCQLReturnerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cassandra CQL module
    """

    def setup_loader_modules(self):
        return {cassandra_cql: {}}

    def test_returns_opts_if_specified(self):
        """
        If ssl options are present then check that they are parsed and returned
        """
        options = MagicMock(
            return_value={
                "cluster": ["192.168.50.10", "192.168.50.11", "192.168.50.12"],
                "port": 9000,
                "ssl_options": {
                    "ca_certs": "/etc/ssl/certs/ca-bundle.trust.crt",
                    "ssl_version": "PROTOCOL_TLSv1",
                },
                "username": "cas_admin",
            }
        )

        with patch.dict(cassandra_cql.__salt__, {"config.option": options}):

            self.assertEqual(
                cassandra_cql._get_ssl_opts(),
                {  # pylint: disable=protected-access
                    "ca_certs": "/etc/ssl/certs/ca-bundle.trust.crt",
                    "ssl_version": ssl.PROTOCOL_TLSv1,
                },
            )  # pylint: disable=no-member

    def test_invalid_protocol_version(self):
        """
        Check that the protocol version is imported only if it isvalid
        """
        options = MagicMock(
            return_value={
                "cluster": ["192.168.50.10", "192.168.50.11", "192.168.50.12"],
                "port": 9000,
                "ssl_options": {
                    "ca_certs": "/etc/ssl/certs/ca-bundle.trust.crt",
                    "ssl_version": "Invalid",
                },
                "username": "cas_admin",
            }
        )

        with patch.dict(cassandra_cql.__salt__, {"config.option": options}):
            with self.assertRaises(CommandExecutionError):
                cassandra_cql._get_ssl_opts()  # pylint: disable=protected-access

    def test_unspecified_opts(self):
        """
        Check that it returns None when ssl opts aren't specified
        """
        with patch.dict(
            cassandra_cql.__salt__, {"config.option": MagicMock(return_value={})}
        ):
            self.assertEqual(
                cassandra_cql._get_ssl_opts(), None  # pylint: disable=protected-access
            )

    def test_valid_asynchronous_args(self):
        mock_execute = MagicMock(return_value={})
        mock_execute_async = MagicMock(return_value={})
        mock_context = {
            "cassandra_cql_returner_cluster": MagicMock(return_value={}),
            "cassandra_cql_returner_session": MagicMock(
                execute=mock_execute,
                execute_async=mock_execute_async,
                prepare=lambda _: MagicMock(
                    bind=lambda _: None
                ),  # mock prepared_statement
                row_factory=None,
            ),
            "cassandra_cql_prepared": {},
        }

        with patch.dict(cassandra_cql.__context__, mock_context):
            cassandra_cql.cql_query_with_prepare(
                "SELECT now() from system.local;", "select_now", [], asynchronous=True
            )
            mock_execute_async.assert_called_once()

    def test_valid_async_args(self):
        mock_execute = MagicMock(return_value={})
        mock_execute_async = MagicMock(return_value={})
        mock_context = {
            "cassandra_cql_returner_cluster": MagicMock(return_value={}),
            "cassandra_cql_returner_session": MagicMock(
                execute=mock_execute,
                execute_async=mock_execute_async,
                prepare=lambda _: MagicMock(bind=lambda _: None),
                # mock prepared_statement
                row_factory=None,
            ),
            "cassandra_cql_prepared": {},
        }

        kwargs = {"async": True}  # to avoid syntax error in python 3.7
        with patch.dict(cassandra_cql.__context__, mock_context):
            cassandra_cql.cql_query_with_prepare(
                "SELECT now() from system.local;", "select_now", [], **kwargs
            )
            mock_execute_async.assert_called_once()

# -*- coding: utf-8 -*-
'''
    tests.unit.returners.cassandra_cql_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import ssl

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock

# Import salt libs
import salt.modules.cassandra_cql as cassandra_cql
from salt.exceptions import CommandExecutionError

try:
    import cassandra  # pylint: disable=unused-import,wrong-import-position
    HAS_CASSANDRA = True
except ImportError:
    HAS_CASSANDRA = False


@skipIf(
    not HAS_CASSANDRA,
    'Please install the cassandra datastax driver to run cassandra_cql module unit tests.'
)
class CassandraCQLReturnerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cassandra CQL module
    '''
    def setup_loader_modules(self):
        return {cassandra_cql: {}}

    def test_returns_opts_if_specified(self):
        '''
        If ssl options are present then check that they are parsed and returned
        '''
        options = MagicMock(return_value={
            'cluster': [
                '192.168.50.10', '192.168.50.11', '192.168.50.12'],
            'port': 9000,
            'ssl_options': {
                'ca_certs': '/etc/ssl/certs/ca-bundle.trust.crt',
                'ssl_version': 'PROTOCOL_TLSv1'},
            'username': 'cas_admin'}
        )

        with patch.dict(cassandra_cql.__salt__, {'config.option': options}):

            self.assertEqual(cassandra_cql._get_ssl_opts(), {  # pylint: disable=protected-access
                'ca_certs': '/etc/ssl/certs/ca-bundle.trust.crt', 'ssl_version': ssl.PROTOCOL_TLSv1})  # pylint: disable=no-member

    def test_invalid_protocol_version(self):
        '''
        Check that the protocol version is imported only if it isvalid
        '''
        options = MagicMock(return_value={
            'cluster': [
                '192.168.50.10', '192.168.50.11', '192.168.50.12'],
            'port': 9000,
            'ssl_options': {
                'ca_certs': '/etc/ssl/certs/ca-bundle.trust.crt',
                'ssl_version': 'Invalid'},
            'username': 'cas_admin'}
        )

        with patch.dict(cassandra_cql.__salt__, {'config.option': options}):
            with self.assertRaises(CommandExecutionError):
                cassandra_cql._get_ssl_opts()  # pylint: disable=protected-access

    def test_unspecified_opts(self):
        '''
        Check that it returns None when ssl opts aren't specified
        '''
        with patch.dict(cassandra_cql.__salt__, {'config.option': MagicMock(return_value={})}):
            self.assertEqual(cassandra_cql._get_ssl_opts(),  # pylint: disable=protected-access
                             None)

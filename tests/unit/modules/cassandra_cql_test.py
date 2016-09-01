# -*- coding: utf-8 -*-
'''
    tests.unit.returners.cassandra_cql_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import ssl

# Import Salt Testing libs
from salttesting.unit import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import salt libs
from salt.modules import cassandra_cql
from salt.exceptions import CommandExecutionError

cassandra_cql.__salt__ = {}
cassandra_cql.__opts__ = {}

try:
    import cassandra  # pylint: disable=unused-import,wrong-import-position
    HAS_CASSANDRA = True
except ImportError:
    HAS_CASSANDRA = False


@skipIf(
    not HAS_CASSANDRA,
    'Please install the cassandra datastax driver to run cassandra_cql module unit tests.'
)
class CassandraCQLReturnerTestCase(TestCase):
    '''
    Test cassandra CQL module
    '''
    def test_returns_opts_if_specified(self):
        '''
        If ssl options are present then check that they are parsed and returned
        '''
        cassandra_cql.cs_ = {
            'cluster': [
                '192.168.50.10', '192.168.50.11', '192.168.50.12'],
            'port': 9000,
            'ssl_options': {
                'ca_certs': '/etc/ssl/certs/ca-bundle.trust.crt',
                'ssl_version': 'PROTOCOL_TLSv1'},
            'username': 'cas_admin'}

        cassandra_cql.__salt__['config.option'] = lambda x: cassandra_cql.cs_

        self.assertEqual(cassandra_cql._get_ssl_opts(), {  # pylint: disable=protected-access
            'ca_certs': '/etc/ssl/certs/ca-bundle.trust.crt', 'ssl_version': ssl.PROTOCOL_TLSv1})  # pylint: disable=no-member

    def test_invalid_protocol_version(self):
        '''
        Check that the protocol version is imported only if it isvalid
        '''
        cassandra_cql.cs_ = {
            'cluster': [
                '192.168.50.10', '192.168.50.11', '192.168.50.12'],
            'port': 9000,
            'ssl_options': {
                'ca_certs': '/etc/ssl/certs/ca-bundle.trust.crt',
                'ssl_version': 'Invalid'},
            'username': 'cas_admin'}

        cassandra_cql.__salt__['config.option'] = lambda x: cassandra_cql.cs_

        with self.assertRaises(CommandExecutionError):
            cassandra_cql._get_ssl_opts()  # pylint: disable=protected-access

    def test_unspecified_opts(self):
        '''
        Check that it returns None when ssl opts aren't specified
        '''
        cassandra_cql.__salt__['config.option'] = lambda x: {}

        self.assertEqual(cassandra_cql._get_ssl_opts(),  # pylint: disable=protected-access
                         None)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CassandraCQLReturnerTestCase, needs_daemon=False)

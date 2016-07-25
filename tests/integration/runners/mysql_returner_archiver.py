# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import logging
import os
import yaml
from pprint import pprint

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath
)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
from salt.modules import mysql as mysqlmod

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)

NO_MYSQL = False
try:
    import MySQLdb  # pylint: disable=import-error,unused-import
except Exception:
    NO_MYSQL = True

if not salt.utils.which('mysqladmin'):
    NO_MYSQL = True


@skipIf(
    NO_MYSQL,
    'Please install MySQL bindings and a MySQL Server before running'
    'MySQL returner archiver integration tests.'
)

@destructiveTest
class MysqlReturnerArchiverTest(integration.ShellCase,
                                integration.SaltReturnAssertsMixIn):
    '''
    Module testing the MySQL returner archiver
    '''

    user = 'root'
    password = 'poney'

    def setUp(self):
        '''
        Test presence of MySQL server, enforce a root password
        '''
        super(MysqlReturnerArchiverTest, self).setUp()

        # Load test data
        command = 'mysqladmin -f drop salt'
        ret = self.run_call('--local cmd.run "{0}"'.format(command), with_retcode=True)
        command = 'mysql mysql < {0}'.format(os.path.join(integration.INTEGRATION_TEST_DIR, 'files/mysql_returner_archiver_data.sql'))
        ret3 = self.run_call('--local cmd.run "{0}" python_shell=True'.format(command), with_retcode=True)

        print 'ret3 {0}'.format(ret3)
        self.assertEqual(ret3[-1], 0)

        tables_present = self.run_call('--local mysql.db_tables salt')
        pprint(tables_present)
        table_dictionary = yaml.safe_load('\n'.join(tables_present))
        pprint(table_dictionary)
        self.assertIn('jids', table_dictionary['local'])
        self.assertIn('salt_returns', table_dictionary['local'])
        self.assertIn('salt_events', table_dictionary['local'])


    def testArchiveRecords(self):

        self.run_run('mysql_returner_archiver.archive')
        tables_present = self.run_call('--local mysql.db_tables salt')
        table_dictionary = yaml.safe_load('\n'.join(tables_present))

        self.assertIn('jids_archive', table_dictionary['local'])
        self.assertIn('salt_returns_archive', table_dictionary['local'])
        self.assertIn('salt_events_archive', table_dictionary['local'])




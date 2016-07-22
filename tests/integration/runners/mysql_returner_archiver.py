# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import logging
import os

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
class MysqlReturnerArchiverTest(integration.ModuleCase,
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
        NO_MYSQL_SERVER = True

        # Load test data
        command = 'mysql mysql < {0}'.format(os.path.join(integration.INTEGRATION_TEST_DIR, 'files/mysql_returner_archiver_data.sql'))
        ret3 = self.run_state('cmd.run', name=command)
        self.assertTrue('Traceback' not in ret3)



    def testTablePresent(self):

        tables_present = self.run_function('mysql.db_tables', ['salt'])
        self.assertIn('jids', tables_present)
        self.assertIn('salt_returns', tables_present)
        self.assertIn('salt_events', tables_present)

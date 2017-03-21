# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch

# Import salt libs
import salt.ext.six as six
import salt.modules.deb_postgres as deb_postgres

deb_postgres.__grains__ = None  # in order to stub it w/patch below
deb_postgres.__salt__ = None  # in order to stub it w/patch below


LSCLUSTER = '''\
8.4 main 5432 online postgres /srv/8.4/main \
        /var/log/postgresql/postgresql-8.4-main.log
9.1 main 5433 online postgres /srv/9.1/main \
        /var/log/postgresql/postgresql-9.1-main.log
'''
if NO_MOCK is False:
    SALT_STUB = {
        'config.option': Mock(),
        'cmd.run_all': Mock(return_value={'stdout': LSCLUSTER}),
        'file.chown': Mock(),
        'file.remove': Mock(),
    }
else:
    SALT_STUB = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(deb_postgres,
                __salt__=SALT_STUB)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pg_createcluster'))
class PostgresClusterTestCase(TestCase):

    def test_cluster_create(self):
        deb_postgres.cluster_create(
            '9.3',
            'main',
            port='5432',
            locale='fr_FR',
            encoding='UTF-8',
            datadir='/opt/postgresql'
        )
        cmd = SALT_STUB['cmd.run_all']

        cmdstr = '/usr/bin/pg_createcluster ' \
            '--port 5432 --locale fr_FR --encoding UTF-8 ' \
            '--datadir /opt/postgresql ' \
            '9.3 main'
        self.assertEqual(cmdstr, cmd.call_args[0][0])

    # XXX version should be a string but from cmdline you get a float
    # def test_cluster_create_with_float(self):
    #     self.assertRaises(AssertionError, deb_postgres.cluster_create,
    #                       (9.3,'main',),
    #                       dict(port='5432',
    #                            locale='fr_FR',
    #                            encoding='UTF-8',
    #                            datadir='/opt/postgresql'))


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(deb_postgres,
                __salt__=SALT_STUB)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pg_lsclusters'))
class PostgresLsClusterTestCase(TestCase):

    def test_parse_pg_lsclusters(self):
        stdout = LSCLUSTER
        self.maxDiff = None
        self.assertDictEqual(
            {('8.4/main'): {
                'port': 5432,
                'status': 'online',
                'user': 'postgres',
                'datadir': '/srv/8.4/main',
                'log': '/var/log/postgresql/postgresql-8.4-main.log'},
             ('9.1/main'): {
                 'port': 5433,
                 'status': 'online',
                 'user': 'postgres',
                 'datadir': '/srv/9.1/main',
                 'log': '/var/log/postgresql/postgresql-9.1-main.log'}},
            deb_postgres._parse_pg_lscluster(stdout))

    def test_cluster_list(self):
        return_list = deb_postgres.cluster_list()
        cmd = SALT_STUB['cmd.run_all']
        self.assertEqual('/usr/bin/pg_lsclusters --no-header',
                         cmd.call_args[0][0])
        if six.PY2:
            # Python 3 returns iterable views (dict_keys in this case) on
            # dict.keys() calls instead of lists. We should only perform
            # this check in Python 2.
            self.assertIsInstance(return_list, list)
        return_dict = deb_postgres.cluster_list(verbose=True)
        self.assertIsInstance(return_dict, dict)

    def test_cluster_exists(self):
        self.assertTrue(deb_postgres.cluster_exists('8.4') is True)
        self.assertTrue(deb_postgres.cluster_exists('8.4', 'main') is True)
        self.assertFalse(deb_postgres.cluster_exists('3.4', 'main'))


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(deb_postgres,
                __salt__=SALT_STUB)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pg_dropcluster'))
class PostgresDeleteClusterTestCase(TestCase):

    def test_cluster_delete(self):
        deb_postgres.cluster_remove('9.3', 'main')
        cmd = SALT_STUB['cmd.run_all']
        self.assertEqual('/usr/bin/pg_dropcluster 9.3 main',
                         cmd.call_args[0][0])
        deb_postgres.cluster_remove('9.3', 'main', stop=True)
        cmd = SALT_STUB['cmd.run_all']
        self.assertEqual('/usr/bin/pg_dropcluster --stop 9.3 main',
                         cmd.call_args[0][0])

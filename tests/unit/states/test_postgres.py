# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, Mock, MagicMock, patch

# Import salt libs
import salt.modules.postgres as postgresmod
import salt.states.postgres_database as postgres_database
import salt.states.postgres_user as postgres_user
import salt.states.postgres_group as postgres_group
import salt.states.postgres_extension as postgres_extension
import salt.states.postgres_schema as postgres_schema
MODS = (
    postgres_database,
    postgres_user,
    postgres_group,
    postgres_extension,
    postgres_schema,
)


OPTS = {'test': False}

for postgres in MODS:
    postgres.__grains__ = {}  # in order to stub it w/patch below
    postgres.__salt__ = {}  # in order to stub it w/patch below
    postgres.__opts__ = {}  # in order to stub it w/patch below

if NO_MOCK is False:
    SALT_STUB = {
        'config.option': Mock(),
        'cmd.run_all': Mock(),
        'file.chown': Mock(),
        'file.remove': Mock(),
    }
else:
    SALT_STUB = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(postgres_user,
                __grains__={'os_family': 'Linux'},
                __salt__=SALT_STUB,
                __opts__={'test': False})
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresUserTestCase(TestCase):

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value=None),
        'postgres.user_create': MagicMock(),
    })
    def test_present__creation(self):
        # test=True
        with patch.dict(postgres_user.__opts__, {'test': True}):
            ret = postgres_user.present('foo')
            self.assertEqual(
                ret,
                {'comment': 'User foo is set to be created',
                 'changes': {}, 'name': 'foo', 'result': None}
            )
            self.assertEqual(SALT_STUB['postgres.user_create'].call_count, 0)

        # test=False
        ret = postgres_user.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'The user foo has been created',
             'changes': {'foo': 'Present'}, 'name': 'foo', 'result': True}
        )
        SALT_STUB['postgres.user_create'].assert_called_once_with(username='foo',
                                                                  superuser=None,
                                                                  encrypted=True,
                                                                  runas=None,
                                                                  inherit=None,
                                                                  rolepassword=None,
                                                                  port=None,
                                                                  replication=None,
                                                                  host=None,
                                                                  createroles=None,
                                                                  user=None,
                                                                  groups=None,
                                                                  maintenance_db=None,
                                                                  login=None,
                                                                  password=None,
                                                                  createdb=None)

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value={
            'can create databases': False,
            'can create roles': False,
            'can login': False,
            'can update system catalogs': False,
            'connections': None,
            'defaults variables': {},
            'expiry time': None,
            'inherits privileges': True,
            'replication': False,
            'superuser': False,
        }),
        'postgres.user_update': MagicMock(),
    })
    def test_present__update(self):
        # test=True
        with patch.dict(postgres_user.__opts__, {'test': True}):
            ret = postgres_user.present('foo', login=True, replication=False)
            self.assertEqual(
                ret,
                {'comment': 'User foo is set to be updated',
                 'changes': {'foo': {'login': True}}, 'name': 'foo', 'result': None}
            )
            self.assertEqual(SALT_STUB['postgres.user_update'].call_count, 0)

        # test=False
        ret = postgres_user.present('foo', login=True, replication=False)
        self.assertEqual(
            ret,
            {'comment': 'The user foo has been updated',
             'changes': {'foo': {'login': True}}, 'name': 'foo', 'result': True}
        )
        SALT_STUB['postgres.user_update'].assert_called_once_with(username='foo',
                                                                  superuser=None,
                                                                  encrypted=True,
                                                                  runas=None,
                                                                  inherit=None,
                                                                  rolepassword=None,
                                                                  port=None,
                                                                  replication=False,
                                                                  host=None,
                                                                  createroles=None,
                                                                  user=None,
                                                                  groups=None,
                                                                  maintenance_db=None,
                                                                  login=True,
                                                                  password=None,
                                                                  createdb=None)

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value={
            'can create databases': False,
            'can create roles': False,
            'can login': False,
            'can update system catalogs': False,
            'connections': None,
            'defaults variables': {},
            'expiry time': None,
            'inherits privileges': True,
            'replication': False,
            'superuser': False,
        }),
        'postgres.user_update': MagicMock(),
    })
    def test_present__no_update(self):
        # test=True
        with patch.dict(OPTS, {'test': True}):
            ret = postgres_user.present('foo', login=False, replication=False)
            self.assertEqual(
                ret,
                {'comment': 'User foo is already present',
                 'changes': {}, 'name': 'foo', 'result': True}
            )
            self.assertEqual(SALT_STUB['postgres.user_update'].call_count, 0)

        # test=False
        ret = postgres_user.present('foo', login=False, replication=False)
        self.assertEqual(
            ret,
            {'comment': 'User foo is already present',
             'changes': {}, 'name': 'foo', 'result': True}
        )
        self.assertEqual(SALT_STUB['postgres.user_update'].call_count, 0)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(postgres_group,
                __grains__={'os_family': 'Linux'},
                __salt__=SALT_STUB,
                __opts__={'test': False})
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresGroupTestCase(TestCase):

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value=None),
        'postgres.group_create': MagicMock(),
    })
    def test_present__creation(self):
        # test=True
        with patch.dict(postgres_group.__opts__, {'test': True}):
            ret = postgres_group.present('foo')
            self.assertEqual(
                ret,
                {'comment': 'Group foo is set to be created',
                 'changes': {}, 'name': 'foo', 'result': None}
            )
            self.assertEqual(SALT_STUB['postgres.group_create'].call_count, 0)

        # test=False
        ret = postgres_group.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'The group foo has been created',
             'changes': {}, 'name': 'foo', 'result': True}
        )
        SALT_STUB['postgres.group_create'].assert_called_once_with(superuser=None,
                                                                   replication=None,
                                                                   encrypted=True,
                                                                   runas=None,
                                                                   inherit=None,
                                                                   rolepassword=None,
                                                                   port=None,
                                                                   groupname='foo',
                                                                   host=None,
                                                                   createroles=None,
                                                                   user=None,
                                                                   groups=None,
                                                                   maintenance_db=None,
                                                                   login=None,
                                                                   password=None,
                                                                   createdb=None)

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value={
            'can create databases': False,
            'can create roles': False,
            'can login': False,
            'can update system catalogs': False,
            'connections': None,
            'defaults variables': {},
            'expiry time': None,
            'inherits privileges': True,
            'replication': False,
            'superuser': False,
        }),
        'postgres.group_update': MagicMock(),
    })
    def test_present__update(self):
        # test=True
        with patch.dict(postgres_group.__opts__, {'test': True}):
            ret = postgres_group.present('foo', login=True, replication=False)
            self.assertEqual(
                ret,
                {'comment': 'Group foo is set to be updated',
                 'changes': {'foo': {'login': True}}, 'name': 'foo', 'result': None}
            )
            self.assertEqual(SALT_STUB['postgres.group_update'].call_count, 0)

        # test=False
        ret = postgres_group.present('foo', login=True, replication=False)
        self.assertEqual(
            ret,
            {'comment': 'The group foo has been updated',
             'changes': {'foo': {'login': True}}, 'name': 'foo', 'result': True}
        )
        SALT_STUB['postgres.group_update'].assert_called_once_with(superuser=None,
                                                                   replication=False,
                                                                   encrypted=True,
                                                                   runas=None,
                                                                   inherit=None,
                                                                   rolepassword=None,
                                                                   port=None,
                                                                   groupname='foo',
                                                                   host=None,
                                                                   createroles=None,
                                                                   user=None,
                                                                   groups=None,
                                                                   maintenance_db=None,
                                                                   login=True,
                                                                   password=None,
                                                                   createdb=None)

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value={
            'can create databases': False,
            'can create roles': False,
            'can login': False,
            'can update system catalogs': False,
            'connections': None,
            'defaults variables': {},
            'expiry time': None,
            'inherits privileges': True,
            'replication': False,
            'superuser': False,
        }),
        'postgres.group_update': MagicMock(),
    })
    def test_present__no_update(self):
        # test=True
        with patch.dict(OPTS, {'test': True}):
            ret = postgres_group.present('foo', login=False, replication=False)
            self.assertEqual(
                ret,
                {'comment': 'Group foo is already present',
                 'changes': {}, 'name': 'foo', 'result': True}
            )
            self.assertEqual(SALT_STUB['postgres.group_update'].call_count, 0)

        # test=False
        ret = postgres_group.present('foo', login=False, replication=False)
        self.assertEqual(
            ret,
            {'comment': 'Group foo is already present',
             'changes': {}, 'name': 'foo', 'result': True}
        )
        self.assertEqual(SALT_STUB['postgres.group_update'].call_count, 0)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(postgres_extension,
                __grains__={'os_family': 'Linux'},
                __salt__=SALT_STUB,
                __opts__={'test': False})
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresExtensionTestCase(TestCase):

    @patch.dict(SALT_STUB, {
        'postgres.create_metadata': Mock(side_effect=[
            [postgresmod._EXTENSION_NOT_INSTALLED],
            [postgresmod._EXTENSION_TO_MOVE, postgresmod._EXTENSION_INSTALLED],

        ]),
        'postgres.create_extension': Mock(side_effect=[
            False, False,
        ]),
    })
    def test_present_failed(self):
        '''
        scenario of creating upgrading extensions with possible schema and
        version specifications
        '''
        ret = postgres_extension.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'Failed to install extension foo',
             'changes': {}, 'name': 'foo', 'result': False},
        )
        ret = postgres_extension.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'Failed to upgrade extension foo',
             'changes': {}, 'name': 'foo', 'result': False}
        )

    @patch.dict(SALT_STUB, {
        'postgres.create_metadata': Mock(side_effect=[
            [postgresmod._EXTENSION_NOT_INSTALLED],
            [postgresmod._EXTENSION_INSTALLED],
            [postgresmod._EXTENSION_TO_MOVE, postgresmod._EXTENSION_INSTALLED],

        ]),
        'postgres.create_extension': Mock(side_effect=[
            True, True, True,
        ]),
    })
    def test_present(self):
        '''
        scenario of creating upgrading extensions with possible schema and
        version specifications
        '''
        ret = postgres_extension.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'The extension foo has been installed',
             'changes': {'foo': 'Installed'}, 'name': 'foo', 'result': True}
        )
        ret = postgres_extension.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'Extension foo is already present',
             'changes': {}, 'name': 'foo', 'result': True}
        )
        ret = postgres_extension.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'The extension foo has been upgraded',
             'changes': {'foo': 'Upgraded'}, 'name': 'foo', 'result': True}
        )

    @patch.dict(OPTS, {'test': True})
    @patch.dict(SALT_STUB, {
        'postgres.create_metadata': Mock(side_effect=[
            [postgresmod._EXTENSION_NOT_INSTALLED],
            [postgresmod._EXTENSION_INSTALLED],
            [postgresmod._EXTENSION_TO_MOVE, postgresmod._EXTENSION_INSTALLED],

        ]),
        'postgres.create_extension': Mock(side_effect=[
            True, True, True,
        ]),
    })
    def test_presenttest(self):
        '''
        scenario of creating upgrading extensions with possible schema and
        version specifications
        '''
        with patch.dict(postgres_extension.__opts__, {'test': True}):
            ret = postgres_extension.present('foo')
            self.assertEqual(
                ret,
                {'comment': 'Extension foo is set to be installed',
                 'changes': {}, 'name': 'foo', 'result': None}

            )
            ret = postgres_extension.present('foo')
            self.assertEqual(
                ret,
                {'comment': "Extension foo is set to be created",
                 'changes': {}, 'name': 'foo', 'result': None}

            )
            ret = postgres_extension.present('foo')
            self.assertEqual(
                ret,
                {'comment': "Extension foo is set to be upgraded",
                 'changes': {}, 'name': 'foo', 'result': None}
            )

    @patch.dict(SALT_STUB, {
        'postgres.is_installed_extension': Mock(side_effect=[
            True, False,
        ]),
        'postgres.drop_extension': Mock(side_effect=[
            True, True,
        ]),
    })
    def test_absent(self):
        '''
        scenario of creating upgrading extensions with possible schema and
        version specifications
        '''
        ret = postgres_extension.absent('foo')
        self.assertEqual(
            ret,
            {'comment': 'Extension foo has been removed',
             'changes': {'foo': 'Absent'}, 'name': 'foo', 'result': True}
        )
        ret = postgres_extension.absent('foo')
        self.assertEqual(
            ret,
            {'comment': (
                'Extension foo is not present, '
                'so it cannot be removed'),
             'changes': {}, 'name': 'foo', 'result': True}

        )

    @patch.dict(OPTS, {'test': False})
    @patch.dict(SALT_STUB, {
        'postgres.is_installed_extension': Mock(side_effect=[
            True, True,
        ]),
        'postgres.drop_extension': Mock(side_effect=[
            False, False,
        ]),
    })
    def test_absent_failed(self):
        '''
        scenario of creating upgrading extensions with possible schema and
        version specifications
        '''
        ret = postgres_extension.absent('foo')
        self.assertEqual(
            ret,
            {'comment': 'Extension foo failed to be removed',
             'changes': {}, 'name': 'foo', 'result': False}
        )

    @patch.dict(OPTS, {'test': True})
    @patch.dict(SALT_STUB, {
        'postgres.is_installed_extension': Mock(side_effect=[
            True, True,
        ]),
        'postgres.drop_extension': Mock(side_effect=[
            False, False,
        ]),
    })
    def test_absent_failedtest(self):
        with patch.dict(postgres_extension.__opts__, {'test': True}):
            ret = postgres_extension.absent('foo')
        self.assertEqual(
            ret,
            {'comment': 'Extension foo is set to be removed',
             'changes': {}, 'name': 'foo', 'result': None}
        )


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(postgres_schema,
                __grains__={'os_family': 'Linux'},
                __salt__=SALT_STUB,
                __opts__={'test': False})
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresSchemaTestCase(TestCase):

    @patch.dict(SALT_STUB, {
        'postgres.schema_get': Mock(return_value=None),
        'postgres.schema_create': MagicMock(),
    })
    def test_present_creation(self):
        ret = postgres_schema.present('dbname', 'foo')
        self.assertEqual(
            ret,
            {'comment': 'Schema foo has been created in database dbname',
             'changes': {'foo': 'Present'},
             'dbname': 'dbname',
             'name': 'foo',
             'result': True}
            )
        self.assertEqual(SALT_STUB['postgres.schema_create'].call_count, 1)

    @patch.dict(SALT_STUB, {
        'postgres.schema_get': Mock(return_value={'foo':
                                                  {'acl': '',
                                                   'owner': 'postgres'}
                                                  }),
        'postgres.schema_create': MagicMock(),
    })
    def test_present_nocreation(self):
        ret = postgres_schema.present('dbname', 'foo')
        self.assertEqual(
            ret,
            {'comment': 'Schema foo already exists in database dbname',
             'changes': {},
             'dbname': 'dbname',
             'name': 'foo',
             'result': True}
            )
        self.assertEqual(SALT_STUB['postgres.schema_create'].call_count, 0)

    @patch.dict(SALT_STUB, {
        'postgres.schema_exists': Mock(return_value=True),
        'postgres.schema_remove': MagicMock(),
    })
    def test_absent_remove(self):
        ret = postgres_schema.absent('dbname', 'foo')
        self.assertEqual(
            ret,
            {'comment': 'Schema foo has been removed from database dbname',
             'changes': {'foo': 'Absent'},
             'dbname': 'dbname',
             'name': 'foo',
             'result': True}
            )
        self.assertEqual(SALT_STUB['postgres.schema_remove'].call_count, 1)

    @patch.dict(SALT_STUB, {
        'postgres.schema_exists': Mock(return_value=False),
        'postgres.schema_remove': MagicMock(),
    })
    def test_absent_noremove(self):
        ret = postgres_schema.absent('dbname', 'foo')
        self.assertEqual(
            ret,
            {'comment': 'Schema foo is not present in database dbname,'
                        ' so it cannot be removed',
             'changes': {},
             'dbname': 'dbname',
             'name': 'foo',
             'result': True}
            )
        self.assertEqual(SALT_STUB['postgres.schema_remove'].call_count, 0)

# -*- coding: utf-8 -*-

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, Mock, MagicMock, patch

ensure_in_syspath('../../')

# Import salt libs

from salt.modules import postgres as postgresmod

from salt.states import (
    postgres_database,
    postgres_user,
    postgres_group,
    postgres_extension,
)
MODS = (
    postgres_database,
    postgres_user,
    postgres_group,
    postgres_extension,
)


OPTS = {'test': False}

for postgres in MODS:
    postgres.__grains__ = None  # in order to stub it w/patch below
    postgres.__salt__ = None  # in order to stub it w/patch below
    postgres.__opts__ = OPTS  # in order to stub it w/patch below

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
                __salt__=SALT_STUB)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresUserTestCase(TestCase):

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value=None),
        'postgres.user_create': MagicMock(),
    })
    def test_present__creation(self):
        # test=True
        with patch.dict(OPTS, {'test': True}):
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
        with patch.dict(OPTS, {'test': True}):
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
                __salt__=SALT_STUB)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresGroupTestCase(TestCase):

    @patch.dict(SALT_STUB, {
        'postgres.role_get': Mock(return_value=None),
        'postgres.group_create': MagicMock(),
    })
    def test_present__creation(self):
        # test=True
        with patch.dict(OPTS, {'test': True}):
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
        with patch.dict(OPTS, {'test': True}):
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
                __salt__=SALT_STUB)
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
             'changes': {}, 'name': 'foo', 'result': True}
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
             'changes': {}, 'name': 'foo', 'result': True}
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
        ret = postgres_extension.absent('foo')
        self.assertEqual(
            ret,
            {'comment': 'Extension foo is set to be removed',
             'changes': {}, 'name': 'foo', 'result': None}
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PostgresExtensionTestCase, needs_daemon=False)

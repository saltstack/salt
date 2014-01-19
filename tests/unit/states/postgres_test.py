# -*- coding: utf-8 -*-

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch
import re

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
@patch.multiple(postgres,
                __grains__={'os_family': 'Linux'},
                __salt__=SALT_STUB)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresTestCase(TestCase):

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
            {'comment': 'Extention foo is already present',
             'changes': {}, 'name': 'foo', 'result': True}
        )
        ret = postgres_extension.present('foo')
        self.assertEqual(
            ret,
            {'comment': 'The extension foo has been upgradeed',
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
    run_tests(PostgresTestCase, needs_daemon=False)

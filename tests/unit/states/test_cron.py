# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

from salt.ext.six.moves import StringIO
from salt.modules import cron as cronmod
from salt.states import cron as cron

STUB_USER = 'root'
STUB_PATH = '/tmp'

STUB_CRON_TIMESTAMP = {
    'minute': '1',
    'hour': '2',
    'daymonth': '3',
    'month': '4',
    'dayweek': '5'}

STUB_SIMPLE_RAW_CRON = '5 0 * * * /tmp/no_script.sh'
STUB_SIMPLE_CRON_DICT = {
    'pre': ['5 0 * * * /tmp/no_script.sh'],
    'crons': [],
    'env': [],
    'special': []}

CRONTAB = StringIO()


def get_crontab(*args, **kw):
    return CRONTAB.getvalue()


def set_crontab(val):
    CRONTAB.seek(0)
    CRONTAB.truncate(0)
    CRONTAB.write(val)


def write_crontab(*args, **kw):
    set_crontab('\n'.join(
        [a.strip() for a in args[1]]))
    return {
        'retcode': False,
    }


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CronTestCase(TestCase, LoaderModuleMockMixin):

    loader_module = cron, cronmod

    def loader_module_globals(self):
        return {
            '__low__': {'__id__': 'noo'},
            '__grains__': {
                'os': 'Debian',
                'os_family': 'Debian',
            },
            '__opts__': {'test': False},
            '__salt__': {
                'cmd.run_all': MagicMock(return_value={
                    'pid': 5,
                    'retcode': 0,
                    'stderr': '',
                    'stdout': ''}),
                'cron.list_tab': cronmod.list_tab,
                'cron.rm_job': cronmod.rm_job,
                'cron.set_job': cronmod.set_job,
            }
        }

    def setUp(self):
        super(CronTestCase, self).setUp()
        set_crontab('')

    def tearDown(self):
        super(CronTestCase, self).tearDown()
        set_crontab('')

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_present(self):
        cron.present(
            name='foo',
            hour='1',
            identifier='1',
            user='root')
        self.assertMultiLineEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 1 * * * foo')
        cron.present(
            name='foo',
            hour='2',
            identifier='1',
            user='root')
        self.assertMultiLineEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 2 * * * foo')
        cron.present(
            name='cmd1',
            minute='0',
            comment='Commented cron job',
            commented=True,
            identifier='commented_1',
            user='root')
        self.assertMultiLineEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 2 * * * foo\n'
            '# Commented cron job SALT_CRON_IDENTIFIER:commented_1\n'
            '#DISABLED#0 * * * * cmd1')
        cron.present(
            name='foo',
            hour='2',
            identifier='2',
            user='root')
        self.assertMultiLineEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 2 * * * foo\n'
            '# Commented cron job SALT_CRON_IDENTIFIER:commented_1\n'
            '#DISABLED#0 * * * * cmd1\n'
            '# SALT_CRON_IDENTIFIER:2\n'
            '* 2 * * * foo')
        cron.present(
            name='cmd2',
            commented=True,
            identifier='commented_2',
            user='root')
        self.assertMultiLineEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 2 * * * foo\n'
            '# Commented cron job SALT_CRON_IDENTIFIER:commented_1\n'
            '#DISABLED#0 * * * * cmd1\n'
            '# SALT_CRON_IDENTIFIER:2\n'
            '* 2 * * * foo\n'
            '# SALT_CRON_IDENTIFIER:commented_2\n'
            '#DISABLED#* * * * * cmd2')
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 2 * * * foo\n'
            '# SALT_CRON_IDENTIFIER:2\n'
            '* 2 * * * foo\n'
            '* 2 * * * foo\n'
        )
        cron.present(
            name='foo',
            hour='2',
            user='root',
            identifier=None)
        self.assertEqual(
            get_crontab(),
            ('# Lines below here are managed by Salt, do not edit\n'
             '# SALT_CRON_IDENTIFIER:1\n'
             '* 2 * * * foo\n'
             '# SALT_CRON_IDENTIFIER:2\n'
             '* 2 * * * foo\n'
             '* 2 * * * foo'))

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_remove(self):
        with patch.dict(cron.__opts__, {'test': True}):
            set_crontab(
                '# Lines below here are managed by Salt, do not edit\n'
                '# SALT_CRON_IDENTIFIER:1\n'
                '* 1 * * * foo')
            result = cron.absent(name='bar', identifier='1')
            self.assertEqual(
                result,
                {'changes': {},
                 'comment': 'Cron bar is set to be removed',
                 'name': 'bar',
                 'result': None}
            )
            self.assertEqual(
                get_crontab(),
                '# Lines below here are managed by Salt, do not edit\n'
                '# SALT_CRON_IDENTIFIER:1\n'
                '* 1 * * * foo')
        with patch.dict(cron.__opts__, {'test': False}):
            set_crontab(
                '# Lines below here are managed by Salt, do not edit\n'
                '# SALT_CRON_IDENTIFIER:1\n'
                '* 1 * * * foo')
            cron.absent(name='bar', identifier='1')
            self.assertEqual(
                get_crontab(),
                '# Lines below here are managed by Salt, do not edit'
            )
            set_crontab(
                '# Lines below here are managed by Salt, do not edit\n'
                '* * * * * foo')
            cron.absent(name='bar', identifier='1')
            self.assertEqual(
                get_crontab(),
                '# Lines below here are managed by Salt, do not edit\n'
                '* * * * * foo'
            )
            # old behavior, do not remove with identifier set and
            # even if command match !
            set_crontab(
                '# Lines below here are managed by Salt, do not edit\n'
                '* * * * * foo')
            cron.absent(name='foo', identifier='1')
            self.assertEqual(
                get_crontab(),
                '# Lines below here are managed by Salt, do not edit'
            )
            # old behavior, remove if no identifier and command match
            set_crontab(
                '# Lines below here are managed by Salt, do not edit\n'
                '* * * * * foo')
            cron.absent(name='foo')
            self.assertEqual(
                get_crontab(),
                '# Lines below here are managed by Salt, do not edit'
            )

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_multiline_comments_are_updated(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '# First crontab - single line comment SALT_CRON_IDENTIFIER:1\n'
            '* 1 * * * foo'
        )
        cron.present(
            name='foo',
            hour='1',
            comment='First crontab\nfirst multi-line comment\n',
            identifier='1',
            user='root')
        cron.present(
            name='foo',
            hour='1',
            comment='First crontab\nsecond multi-line comment\n',
            identifier='1',
            user='root')
        cron.present(
            name='foo',
            hour='1',
            comment='Second crontab\nmulti-line comment\n',
            identifier='2',
            user='root')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# First crontab\n'
            '# second multi-line comment SALT_CRON_IDENTIFIER:1\n'
            '* 1 * * * foo\n'
            '# Second crontab\n'
            '# multi-line comment SALT_CRON_IDENTIFIER:2\n'
            '* 1 * * * foo')

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_existing_unmanaged_jobs_are_made_managed(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '0 2 * * * foo'
        )
        ret = cron._check_cron('root', 'foo', hour='2', minute='0')
        self.assertEqual(ret, 'present')
        ret = cron.present('foo', 'root', minute='0', hour='2')
        self.assertEqual(ret['changes'], {'root': 'foo'})
        self.assertEqual(ret['comment'], 'Cron foo updated')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:foo\n'
            '0 2 * * * foo')
        ret = cron.present('foo', 'root', minute='0', hour='2')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(ret['comment'], 'Cron foo already present')

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_existing_noid_jobs_are_updated_with_identifier(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:NO ID SET\n'
            '1 * * * * foo'
        )
        ret = cron._check_cron('root', 'foo', minute=1)
        self.assertEqual(ret, 'present')
        ret = cron.present('foo', 'root', minute=1)
        self.assertEqual(ret['changes'], {'root': 'foo'})
        self.assertEqual(ret['comment'], 'Cron foo updated')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:foo\n'
            '1 * * * * foo')

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_existing_duplicate_unmanaged_jobs_are_merged_and_given_id(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '0 2 * * * foo\n'
            '0 2 * * * foo'
        )
        ret = cron._check_cron('root', 'foo', hour='2', minute='0')
        self.assertEqual(ret, 'present')
        ret = cron.present('foo', 'root', minute='0', hour='2')
        self.assertEqual(ret['changes'], {'root': 'foo'})
        self.assertEqual(ret['comment'], 'Cron foo updated')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:foo\n'
            '0 2 * * * foo')
        ret = cron.present('foo', 'root', minute='0', hour='2')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(ret['comment'], 'Cron foo already present')

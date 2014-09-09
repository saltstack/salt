# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
from StringIO import StringIO

ensure_in_syspath('../../')

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

__low__ = {
    '__id__': 'noo'
}
__grains__ = {
    'os': 'Debian',
    'os_family': 'Debian',
}

cron.__opts__ = {
    'test': False,
}
cronmod.__low__ = cron.__low__ = __low__
cronmod.__grains__ = cron.__grains__ = __grains__
cronmod.__salt__ = cron.__salt__ = {
    'cmd.run_all': MagicMock(return_value={
        'pid': 5,
        'retcode': 0,
        'stderr': '',
        'stdout': ''}),
    'cron.list_tab': cronmod.list_tab,
    'cron.rm_job': cronmod.rm_job,
    'cron.set_job': cronmod.set_job,
}


CRONTAB = StringIO()


def get_crontab(*args, **kw):
    return CRONTAB.getvalue()


def set_crontab(val):
    CRONTAB.truncate(0)
    CRONTAB.write(val)


def write_crontab(*args, **kw):
    set_crontab('\n'.join(
        [a.strip() for a in args[1]]))
    return {
        'retcode': False,
    }


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CronTestCase(TestCase):

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
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 1 * * * foo')
        cron.present(
            name='foo',
            hour='2',
            identifier='1',
            user='root')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 2 * * * foo')
        cron.present(
            name='foo',
            hour='2',
            identifier='2',
            user='root')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '* 2 * * * foo\n'
            '# SALT_CRON_IDENTIFIER:2\n'
            '* 2 * * * foo')
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
            user='root')
        self.assertEqual(
            get_crontab(),
            ('# Lines below here are managed by Salt, do not edit\n'
             '# SALT_CRON_IDENTIFIER:1\n'
             '* 2 * * * foo\n'
             '# SALT_CRON_IDENTIFIER:2\n'
             '* 2 * * * foo\n'
             '* 2 * * * foo\n'))

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_remove(self):
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
    def test_aissue_1072(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '# I have a multi-line comment SALT_CRON_IDENTIFIER:1\n'
            '* 1 * * * foo'
        )
        cron.present(
            name='foo',
            hour='1',
            comment='1I have a multi-line comment\n2about my script here.\n',
            identifier='1',
            user='root')
        cron.present(
            name='foo',
            hour='1',
            comment='3I have a multi-line comment\n3about my script here.\n',
            user='root')
        cron.present(
            name='foo',
            hour='1',
            comment='I have a multi-line comment\nabout my script here.\n',
            identifier='2',
            user='root')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# 2about my script here. SALT_CRON_IDENTIFIER:1\n'
            '* 1 * * * foo\n'
            '# I have a multi-line comment\n'
            '# about my script here. SALT_CRON_IDENTIFIER:2\n'
            '* 1 * * * foo')

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_issue_11935(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '0 2 * * * find /var/www -type f '
            '-mtime -7 -print0 | xargs -0 '
            'clamscan -i --no-summary 2>/dev/null'
        )
        cmd = (
            'find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null'
        )
        self.assertEqual(cron._check_cron('root', cmd, hour='2', minute='0'),
                         'present')
        ret = cron.present(cmd, 'root', minute='0', hour='2')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null already present')
        self.assertEqual(cron._check_cron('root', cmd, hour='3', minute='0'),
                         'update')
        ret = cron.present(cmd, 'root', minute='0', hour='3')
        self.assertEqual(ret['changes'],
                         {'root': 'find /var/www -type f -mtime -7 -print0 | '
                          'xargs -0 clamscan -i --no-summary 2>/dev/null'})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null updated')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '0 3 * * * find /var/www -type f -mtime -7 -print0 |'
            ' xargs -0 clamscan -i --no-summary 2>/dev/null')

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_issue_11935_with_id(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '0 2 * * * find /var/www -type f '
            '-mtime -7 -print0 | xargs -0 '
            'clamscan -i --no-summary 2>/dev/null'
        )
        cmd = (
            'find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null'
        )
        self.assertEqual(cron._check_cron(
            'root', cmd, hour='2', minute='0', identifier=1), 'present')
        ret = cron.present(cmd, 'root', minute='0', hour='2', identifier='1')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null already present')
        self.assertEqual(cron._check_cron(
            'root', cmd, hour='3', minute='0', identifier='1'), 'update')
        ret = cron.present(cmd, 'root', minute='0', hour='3', identifier='1')
        self.assertEqual(ret['changes'],
                         {'root': 'find /var/www -type f -mtime -7 -print0 | '
                          'xargs -0 clamscan -i --no-summary 2>/dev/null'})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null updated')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '0 3 * * * find /var/www -type f -mtime -7 -print0 |'
            ' xargs -0 clamscan -i --no-summary 2>/dev/null')

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_issue_11935_mixed(self):
        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '0 2 * * * find /var/www -type f '
            '-mtime -7 -print0 | xargs -0 '
            'clamscan -i --no-summary 2>/dev/null'
        )
        cmd = (
            'find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null'
        )
        self.assertEqual(cron._check_cron('root', cmd, hour='2', minute='0'),
                         'present')
        ret = cron.present(cmd, 'root', minute='0', hour='2')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null already present')
        self.assertEqual(cron._check_cron('root', cmd, hour='3', minute='0'),
                         'update')
        ret = cron.present(cmd, 'root', minute='0', hour='3')
        self.assertEqual(ret['changes'],
                         {'root': 'find /var/www -type f -mtime -7 -print0 | '
                          'xargs -0 clamscan -i --no-summary 2>/dev/null'})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null updated')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '0 3 * * * find /var/www -type f -mtime -7 -print0 |'
            ' xargs -0 clamscan -i --no-summary 2>/dev/null')
        self.assertEqual(cron._check_cron(
            'root', cmd, hour='2', minute='0', identifier='1'), 'update')
        ret = cron.present(cmd, 'root', minute='0', hour='2', identifier='1')
        self.assertEqual(
            ret['changes'],
            {'root': 'find /var/www -type f -mtime -7 -print0 | '
             'xargs -0 clamscan -i --no-summary 2>/dev/null'})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null updated')
        self.assertEqual(cron._check_cron(
            'root', cmd, hour='3', minute='0', identifier='1'), 'update')
        ret = cron.present(cmd, 'root', minute='0', hour='3', identifier='1')
        self.assertEqual(ret['changes'],
                         {'root': 'find /var/www -type f -mtime -7 -print0 | '
                          'xargs -0 clamscan -i --no-summary 2>/dev/null'})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 '
            '| xargs -0 clamscan -i --no-summary 2>/dev/null updated')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '0 3 * * * find /var/www -type f -mtime -7 -print0 |'
            ' xargs -0 clamscan -i --no-summary 2>/dev/null')

        set_crontab(
            '# Lines below here are managed by Salt, do not edit\n'
            '0 2 * * * find /var/www -type f '
            '-mtime -7 -print0 | xargs -0 '
            'clamscan -i --no-summary 2>/dev/null'
        )
        self.assertEqual(cron._check_cron(
            'root', cmd + "a", hour='2', minute='0', identifier='1'), 'absent')
        ret = cron.present(
            cmd + "a", 'root', minute='0', hour='2', identifier='1')
        self.assertEqual(
            ret['changes'],
            {'root': 'find /var/www -type f -mtime -7 -print0 | '
             'xargs -0 clamscan -i --no-summary 2>/dev/nulla'})
        self.assertEqual(
            ret['comment'],
            'Cron find /var/www -type f -mtime -7 -print0 | '
            'xargs -0 clamscan -i --no-summary 2>/dev/nulla added '
            'to root\'s crontab')
        self.assertEqual(
            get_crontab(),
            '# Lines below here are managed by Salt, do not edit\n'
            '0 2 * * *'
            ' find /var/www -type f -mtime -7 -print0'
            ' | xargs -0 clamscan -i --no-summary 2>/dev/null\n'
            '# SALT_CRON_IDENTIFIER:1\n'
            '0 2 * * *'
            ' find /var/www -type f -mtime -7 -print0'
            ' | xargs -0 clamscan -i --no-summary 2>/dev/nulla')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CronTestCase, needs_daemon=False)

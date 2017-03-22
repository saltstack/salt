# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

# Import Salt libs
import salt.modules.cron as cron
from salt.ext.six.moves import builtins, StringIO

STUB_USER = 'root'
STUB_PATH = '/tmp'

STUB_CRON_TIMESTAMP = {'minute': '1',
                       'hour': '2',
                       'daymonth': '3',
                       'month': '4',
                       'dayweek': '5'}

STUB_SIMPLE_RAW_CRON = '5 0 * * * /tmp/no_script.sh'
STUB_SIMPLE_CRON_DICT = {'pre': ['5 0 * * * /tmp/no_script.sh'], 'crons': [], 'env': [], 'special': []}
STUB_CRON_SPACES = """
# Lines below here are managed by Salt, do not edit
TEST_VAR="a string with plenty of spaces"
# SALT_CRON_IDENTIFIER:echo "must  be  double  spaced"
11 * * * * echo "must  be  double  spaced"
"""

L = '# Lines below here are managed by Salt, do not edit\n'

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
    return MagicMock()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CronTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {cron: {}}

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=get_crontab))
    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test__need_changes_new(self):
        '''
        New behavior, identifier will get track of the managed lines!
        '''

        # when there are no identifiers,
        # we do not touch it
        set_crontab(
            L + '# SALT_CRON_IDENTIFIER:booh\n'
            '* * * * * ls\n')
        cron.set_job(
            user='root',
            minute='*',
            hour='*',
            daymonth='*',
            month='*',
            dayweek='*',
            cmd='ls',
            comment=None,
            identifier=None,
        )
        c1 = get_crontab()
        set_crontab(L + '* * * * * ls\n')
        self.assertEqual(
            c1,
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:booh\n'
            '* * * * * ls\n'
            '* * * * * ls'
        )
        # whenever we have an identifier, hourray even without comment
        # we can match and edit the crontab in place
        # without cluttering the crontab with new cmds
        set_crontab(
            L + '# SALT_CRON_IDENTIFIER:bar\n'
            '* * * * * ls\n')
        cron.set_job(
            user='root',
            minute='*',
            hour='*',
            daymonth='*',
            month='*',
            dayweek='*',
            cmd='ls',
            comment=None,
            identifier='bar',
        )
        c5 = get_crontab()
        set_crontab(L + '* * * * * ls\n')
        self.assertEqual(
            c5,
            '# Lines below here are managed by Salt, do not edit\n'
            '# SALT_CRON_IDENTIFIER:bar\n'
            '* * * * * ls\n'
        )
        # we can even change the other parameters as well
        # thx to the id
        set_crontab(
            L + '# SALT_CRON_IDENTIFIER:bar\n* * * * * ls\n')
        cron.set_job(
            user='root',
            minute='1',
            hour='2',
            daymonth='3',
            month='4',
            dayweek='5',
            cmd='foo',
            comment='moo',
            identifier='bar',
        )
        c6 = get_crontab()
        self.assertEqual(
            c6,
            '# Lines below here are managed by Salt, do not edit\n'
            '# moo SALT_CRON_IDENTIFIER:bar\n'
            '1 2 3 4 5 foo'
        )

    def test__unicode_match(self):
        with patch.object(builtins, '__salt_system_encoding__', 'utf-8'):
            self.assertTrue(cron._cron_matched({'identifier': '1'}, 'foo', 1))
            self.assertTrue(cron._cron_matched({'identifier': 'é'}, 'foo', 'é'))
            self.assertTrue(cron._cron_matched({'identifier': u'é'}, 'foo', 'é'))
            self.assertTrue(cron._cron_matched({'identifier': 'é'}, 'foo', u'é'))
            self.assertTrue(cron._cron_matched({'identifier': u'é'}, 'foo', u'é'))

    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test__need_changes_old(self):
        '''
        old behavior; ID has no special action
        - If an id is found, it will be added as a new crontab
          even if there is a cmd that looks like this one
        - no comment, delete the cmd and readd it
        - comment: idem
        '''
        with patch(
            'salt.modules.cron.raw_cron',
            new=MagicMock(side_effect=get_crontab)
        ):
            set_crontab(L + '* * * * * ls\n\n')
            cron.set_job(
                user='root',
                minute='*',
                hour='*',
                daymonth='*',
                month='*',
                dayweek='*',
                cmd='ls',
                comment=None,
                identifier=cron.SALT_CRON_NO_IDENTIFIER,
            )
            c1 = get_crontab()
            set_crontab(L + '* * * * * ls\n')
            self.assertEqual(
                c1,
                '# Lines below here are managed by Salt, do not edit\n'
                '* * * * * ls\n'
                '\n'
            )
            cron.set_job(
                user='root',
                minute='*',
                hour='*',
                daymonth='*',
                month='*',
                dayweek='*',
                cmd='ls',
                comment='foo',
                identifier=cron.SALT_CRON_NO_IDENTIFIER,
            )
            c2 = get_crontab()
            self.assertEqual(
                c2,
                '# Lines below here are managed by Salt, do not edit\n'
                '# foo\n* * * * * ls'
            )
            set_crontab(L + '* * * * * ls\n')
            cron.set_job(
                user='root',
                minute='*',
                hour='*',
                daymonth='*',
                month='*',
                dayweek='*',
                cmd='lsa',
                comment='foo',
                identifier='bar',
            )
            c3 = get_crontab()
            self.assertEqual(
                c3,
                '# Lines below here are managed by Salt, do not edit\n'
                '* * * * * ls\n'
                '# foo SALT_CRON_IDENTIFIER:bar\n'
                '* * * * * lsa'
            )
            set_crontab(L + '* * * * * ls\n')
            cron.set_job(
                user='root',
                minute='*',
                hour='*',
                daymonth='*',
                month='*',
                dayweek='*',
                cmd='foo',
                comment='foo',
                identifier='bar',
            )
            c4 = get_crontab()
            self.assertEqual(
                c4,
                '# Lines below here are managed by Salt, do not edit\n'
                '* * * * * ls\n'
                '# foo SALT_CRON_IDENTIFIER:bar\n'
                '* * * * * foo'
            )
            set_crontab(L + '* * * * * ls\n')
            cron.set_job(
                user='root',
                minute='*',
                hour='*',
                daymonth='*',
                month='*',
                dayweek='*',
                cmd='ls',
                comment='foo',
                identifier='bbar',
            )
            c4 = get_crontab()
            self.assertEqual(
                c4,
                '# Lines below here are managed by Salt, do not edit\n'
                '# foo SALT_CRON_IDENTIFIER:bbar\n'
                '* * * * * ls'
            )

    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test__issue10959(self):
        '''
        handle multi old style crontabs
        https://github.com/saltstack/salt/issues/10959
        '''
        with patch(
            'salt.modules.cron.raw_cron',
            new=MagicMock(side_effect=get_crontab)
        ):
            set_crontab(
                '# Lines below here are managed by Salt, do not edit\n'
                '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                # as managed per salt, the last lines will be merged together !
                '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                '* * * * * samecmd\n'
                '* * * * * otheridcmd\n'
                '* * * * * otheridcmd\n'
                '# SALT_CRON_IDENTIFIER:NO ID SET\n0 * * * * samecmd1\n'
                '1 * * * * samecmd1\n'
                '0 * * * * otheridcmd1\n'
                '1 * * * * otheridcmd1\n'
                # special case here, none id managed line with same command
                # as a later id managed line will become managed
                '# SALT_CRON_IDENTIFIER:1\n0 * * * * otheridcmd1\n'
                '# SALT_CRON_IDENTIFIER:2\n0 * * * * otheridcmd1\n'
            )
            crons1 = cron.list_tab('root')
            # the filtering is done on save, we reflect in listing
            # the same that we have in a file, no matter what we
            # have
            self.assertEqual(crons1, {
                'crons': [
                    {'cmd': 'ls', 'comment': 'uoo', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'too', 'comment': 'uuoo', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'zoo', 'comment': 'uuuoo', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'yoo', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'xoo', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'samecmd', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'samecmd', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'otheridcmd', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'otheridcmd', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '*', 'month': '*', 'commented': False},
                    {'cmd': 'samecmd1', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '0', 'month': '*', 'commented': False},
                    {'cmd': 'samecmd1', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '1', 'month': '*', 'commented': False},
                    {'cmd': 'otheridcmd1', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '0', 'month': '*', 'commented': False},
                    {'cmd': 'otheridcmd1', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '1', 'month': '*', 'commented': False},
                    {'cmd': 'otheridcmd1', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': '1',
                     'minute': '0', 'month': '*', 'commented': False},
                    {'cmd': 'otheridcmd1',
                     'comment': '', 'daymonth': '*', 'dayweek': '*',
                     'hour': '*', 'identifier': '2', 'minute': '0',
                     'month': '*', 'commented': False}
                ],
                'env': [],
                'pre': [],
                'special': []})
            # so yood so far, no problem for now, trying to save the
            # multilines without id crons now
            inc_tests = [
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n'
                 '0 * * * * samecmd1'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n'
                 '0 * * * * otheridcmd1'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n'
                 '1 * * * * otheridcmd1'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n'
                 '# SALT_CRON_IDENTIFIER:1\n0 * * * * otheridcmd1'),
                #
                ('# Lines below here are managed by Salt, do not edit\n'
                 '# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n'
                 '# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n'
                 '# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n'
                 '* * * * * otheridcmd\n'
                 '# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n'
                 '# SALT_CRON_IDENTIFIER:1\n0 * * * * otheridcmd1\n'
                 '# SALT_CRON_IDENTIFIER:2\n0 * * * * otheridcmd1')
            ]
            set_crontab('')
            for idx, cr in enumerate(crons1['crons']):
                cron.set_job('root', **cr)
                self.assertEqual(
                    get_crontab(),
                    inc_tests[idx], (
                        "idx {0}\n'{1}'\n != \n'{2}'\n\n\n"
                        "\'{1}\' != \'{2}\'"
                    ).format(
                        idx, get_crontab(), inc_tests[idx]))

    @patch('salt.modules.cron._write_cron_lines',
           new=MagicMock(side_effect=write_crontab))
    def test_list_tab_commented_cron_jobs(self):
        '''
        handle commented cron jobs
        https://github.com/saltstack/salt/issues/29082
        '''
        self.maxDiff = None
        with patch(
            'salt.modules.cron.raw_cron',
            new=MagicMock(side_effect=get_crontab)
        ):
            set_crontab(
                '# An unmanaged commented cron job\n'
                '#0 * * * * /bin/true\n'
                '# Lines below here are managed by Salt, do not edit\n'
                '# cron_1 SALT_CRON_IDENTIFIER:cron_1\n#DISABLED#0 * * * * my_cmd_1\n'
                '# cron_2 SALT_CRON_IDENTIFIER:cron_2\n#DISABLED#* * * * * my_cmd_2\n'
                '# cron_3 SALT_CRON_IDENTIFIER:cron_3\n'
                '#DISABLED#but it is a comment line'
                '#DISABLED#0 * * * * my_cmd_3\n'
                '# cron_4 SALT_CRON_IDENTIFIER:cron_4\n0 * * * * my_cmd_4\n'
            )
            crons1 = cron.list_tab('root')
            self.assertEqual(crons1, {
                'crons': [
                    {'cmd': 'my_cmd_1', 'comment': 'cron_1', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'cron_1',
                     'minute': '0', 'month': '*', 'commented': True},
                    {'cmd': 'my_cmd_2', 'comment': 'cron_2', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'cron_2',
                     'minute': '*', 'month': '*', 'commented': True},
                    {'cmd': 'line#DISABLED#0 * * * * my_cmd_3',
                     'comment': 'cron_3', 'daymonth': 'is',
                     'dayweek': 'comment', 'hour': 'it', 'identifier': 'cron_3',
                     'minute': 'but', 'month': 'a', 'commented': True},
                    {'cmd': 'my_cmd_4', 'comment': 'cron_4', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'cron_4',
                     'minute': '0', 'month': '*', 'commented': False},
                ],
                'env': [],
                'pre': ['# An unmanaged commented cron job', '#0 * * * * /bin/true'],
                'special': []})

    @patch('salt.modules.cron.raw_cron', new=MagicMock(return_value=STUB_CRON_SPACES))
    def test_cron_extra_spaces(self):
        '''
        Issue #38449
        '''
        self.maxDiff = None
        with patch.dict(cron.__grains__, {'os': None}):
            ret = cron.list_tab('root')
            eret = {'crons': [{'cmd': 'echo "must  be  double  spaced"',
                               'comment': '',
                               'commented': False,
                               'daymonth': '*',
                               'dayweek': '*',
                               'hour': '*',
                               'identifier': 'echo "must  be  double  spaced"',
                               'minute': '11',
                               'month': '*'}],
                    'env': [{'name': 'TEST_VAR', 'value': '"a string with plenty of spaces"'}],
                    'pre': [''],
                    'special': []}
            self.assertEqual(eret, ret)

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=[
               (L + '\n'),
               (L + '* * * * * ls\nn'),
               (L + '# commented\n'
                '#DISABLED#* * * * * ls\n'),
               (L + '# foo\n'
                '* * * * * ls\n'),
               (L + '# foo {0}:blah\n'.format(
                   cron.SALT_CRON_IDENTIFIER) +
                   '* * * * * ls\n'),
           ]))
    def test__load_tab(self):
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            crons1 = cron.list_tab('root')
            crons2 = cron.list_tab('root')
            crons3 = cron.list_tab('root')
            crons4 = cron.list_tab('root')
            crons5 = cron.list_tab('root')
            self.assertEqual(
                crons1,
                {'pre': [], 'crons': [], 'env': [], 'special': []})
            self.assertEqual(
                crons2['crons'][0],
                {'comment': None,
                 'commented': False,
                 'dayweek': '*',
                 'hour': '*',
                 'identifier': None,
                 'cmd': 'ls',
                 'daymonth': '*',
                 'minute': '*',
                 'month': '*'})
            self.assertEqual(
                crons3['crons'][0],
                {'comment': 'commented',
                 'commented': True,
                 'dayweek': '*',
                 'hour': '*',
                 'identifier': None,
                 'cmd': 'ls',
                 'daymonth': '*',
                 'minute': '*',
                 'month': '*'})
            self.assertEqual(
                crons4['crons'][0],
                {'comment': 'foo',
                 'commented': False,
                 'dayweek': '*',
                 'hour': '*',
                 'identifier': None,
                 'cmd': 'ls',
                 'daymonth': '*',
                 'minute': '*',
                 'month': '*'})
            self.assertEqual(
                crons5['crons'][0],
                {'comment': 'foo',
                 'commented': False,
                 'dayweek': '*',
                 'hour': '*',
                 'identifier': 'blah',
                 'cmd': 'ls',
                 'daymonth': '*',
                 'minute': '*',
                 'month': '*'})

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_write_cron_file_root_rh(self):
        '''
        Assert that write_cron_file() is called with the correct cron command and user: RedHat
          - If instance running uid matches crontab user uid, runas STUB_USER without -u flag.
        '''
        with patch.dict(cron.__grains__, {'os_family': 'RedHat'}):
            with patch.dict(cron.__salt__, {'cmd.retcode': MagicMock()}):
                cron.write_cron_file(STUB_USER, STUB_PATH)
                cron.__salt__['cmd.retcode'].assert_called_with("crontab /tmp",
                                                                runas=STUB_USER,
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_write_cron_file_foo_rh(self):
        '''
        Assert that write_cron_file() is called with the correct cron command and user: RedHat
          - If instance running with uid that doesn't match crontab user uid, run with -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'RedHat'}):
            with patch.dict(cron.__salt__, {'cmd.retcode': MagicMock()}):
                cron.write_cron_file('foo', STUB_PATH)
                cron.__salt__['cmd.retcode'].assert_called_with("crontab -u foo /tmp",
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_write_cron_file_root_sol(self):
        '''
        Assert that write_cron_file() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'RedHat'}):
            with patch.dict(cron.__salt__, {'cmd.retcode': MagicMock()}):
                cron.write_cron_file(STUB_USER, STUB_PATH)
                cron.__salt__['cmd.retcode'].assert_called_with("crontab /tmp",
                                                                runas=STUB_USER,
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_write_cron_file_foo_sol(self):
        '''
        Assert that write_cron_file() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            with patch.dict(cron.__salt__, {'cmd.retcode': MagicMock()}):
                cron.write_cron_file('foo', STUB_PATH)
                cron.__salt__['cmd.retcode'].assert_called_with("crontab /tmp",
                                                                runas='foo',
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_write_cron_file_root_aix(self):
        '''
        Assert that write_cron_file() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'AIX'}):
            with patch.dict(cron.__salt__, {'cmd.retcode': MagicMock()}):
                cron.write_cron_file(STUB_USER, STUB_PATH)
                cron.__salt__['cmd.retcode'].assert_called_with("crontab /tmp",
                                                                runas=STUB_USER,
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_write_cron_file_foo_aix(self):
        '''
        Assert that write_cron_file() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'AIX'}):
            with patch.dict(cron.__salt__, {'cmd.retcode': MagicMock()}):
                cron.write_cron_file('foo', STUB_PATH)
                cron.__salt__['cmd.retcode'].assert_called_with("crontab /tmp",
                                                                runas='foo',
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_write_cr_file_v_root_rh(self):
        '''
        Assert that write_cron_file_verbose() is called with the correct cron command and user: RedHat
          - If instance running uid matches crontab user uid, runas STUB_USER without -u flag.
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Redhat'}):
            with patch.dict(cron.__salt__, {'cmd.run_all': MagicMock()}):
                cron.write_cron_file_verbose(STUB_USER, STUB_PATH)
                cron.__salt__['cmd.run_all'].assert_called_with("crontab /tmp",
                                                                runas=STUB_USER,
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_write_cr_file_v_foo_rh(self):
        '''
        Assert that write_cron_file_verbose() is called with the correct cron command and user: RedHat
          - If instance running with uid that doesn't match crontab user uid, run with -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Redhat'}):
            with patch.dict(cron.__salt__, {'cmd.run_all': MagicMock()}):
                cron.write_cron_file_verbose('foo', STUB_PATH)
                cron.__salt__['cmd.run_all'].assert_called_with("crontab -u foo /tmp",
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_write_cr_file_v_root_sol(self):
        '''
        Assert that write_cron_file_verbose() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            with patch.dict(cron.__salt__, {'cmd.run_all': MagicMock()}):
                cron.write_cron_file_verbose(STUB_USER, STUB_PATH)
                cron.__salt__['cmd.run_all'].assert_called_with("crontab /tmp",
                                                                runas=STUB_USER,
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_write_cr_file_v_foo_sol(self):
        '''
        Assert that write_cron_file_verbose() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            with patch.dict(cron.__salt__, {'cmd.run_all': MagicMock()}):
                cron.write_cron_file_verbose('foo', STUB_PATH)
                cron.__salt__['cmd.run_all'].assert_called_with("crontab /tmp",
                                                                runas='foo',
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_write_cr_file_v_root_aix(self):
        '''
        Assert that write_cron_file_verbose() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'AIX'}):
            with patch.dict(cron.__salt__, {'cmd.run_all': MagicMock()}):
                cron.write_cron_file_verbose(STUB_USER, STUB_PATH)
                cron.__salt__['cmd.run_all'].assert_called_with("crontab /tmp",
                                                                runas=STUB_USER,
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_write_cr_file_v_foo_aix(self):
        '''
        Assert that write_cron_file_verbose() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'AIX'}):
            with patch.dict(cron.__salt__, {'cmd.run_all': MagicMock()}):
                cron.write_cron_file_verbose('foo', STUB_PATH)
                cron.__salt__['cmd.run_all'].assert_called_with("crontab /tmp",
                                                                runas='foo',
                                                                python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_raw_cron_root_redhat(self):
        '''
        Assert that raw_cron() is called with the correct cron command and user: RedHat
          - If instance running uid matches crontab user uid, runas STUB_USER without -u flag.
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Redhat'}):
            with patch.dict(cron.__salt__, {'cmd.run_stdout': MagicMock()}):
                cron.raw_cron(STUB_USER)
                cron.__salt__['cmd.run_stdout'].assert_called_with("crontab -l",
                                                                   runas=STUB_USER,
                                                                   rstrip=False,
                                                                   python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_raw_cron_foo_redhat(self):
        '''
        Assert that raw_cron() is called with the correct cron command and user: RedHat
          - If instance running with uid that doesn't match crontab user uid, run with -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Redhat'}):
            with patch.dict(cron.__salt__, {'cmd.run_stdout': MagicMock()}):
                cron.raw_cron(STUB_USER)
                cron.__salt__['cmd.run_stdout'].assert_called_with("crontab -u root -l",
                                                                   rstrip=False,
                                                                   python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_raw_cron_root_solaris(self):
        '''
        Assert that raw_cron() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            with patch.dict(cron.__salt__, {'cmd.run_stdout': MagicMock()}):
                cron.raw_cron(STUB_USER)
                cron.__salt__['cmd.run_stdout'].assert_called_with("crontab -l",
                                                                   runas=STUB_USER,
                                                                   rstrip=False,
                                                                   python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_raw_cron_foo_solaris(self):
        '''
        Assert that raw_cron() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            with patch.dict(cron.__salt__, {'cmd.run_stdout': MagicMock()}):
                cron.raw_cron(STUB_USER)
                cron.__salt__['cmd.run_stdout'].assert_called_with("crontab -l",
                                                                   runas=STUB_USER,
                                                                   rstrip=False,
                                                                   python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=True))
    def test_raw_cron_root_aix(self):
        '''
        Assert that raw_cron() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'AIX'}):
            with patch.dict(cron.__salt__, {'cmd.run_stdout': MagicMock()}):
                cron.raw_cron(STUB_USER)
                cron.__salt__['cmd.run_stdout'].assert_called_with("crontab -l",
                                                                   runas=STUB_USER,
                                                                   rstrip=False,
                                                                   python_shell=False)

    @patch("salt.modules.cron._check_instance_uid_match", new=MagicMock(return_value=False))
    def test_raw_cron_foo_aix(self):
        '''
        Assert that raw_cron() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        '''
        with patch.dict(cron.__grains__, {'os_family': 'AIX'}):
            with patch.dict(cron.__salt__, {'cmd.run_stdout': MagicMock()}):
                cron.raw_cron(STUB_USER)
                cron.__salt__['cmd.run_stdout'].assert_called_with("crontab -l",
                                                                   runas=STUB_USER,
                                                                   rstrip=False,
                                                                   python_shell=False)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PsTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {cron: {}}

    def test__needs_change(self):
        self.assertTrue(cron._needs_change(True, False))

    def test__needs_change_random(self):
        '''
        Assert that if the new var is 'random' and old is '* that we return True
        '''
        self.assertTrue(cron._needs_change('*', 'random'))

    ## Still trying to figure this one out.
    # def test__render_tab(self):
    #     pass
    def test__get_cron_cmdstr(self):
        self.assertEqual('crontab /tmp', cron._get_cron_cmdstr(STUB_PATH))

    # Test get_cron_cmdstr() when user is added
    def test__get_cron_cmdstr_user(self):
        '''
        Passes if a user is added to crontab command
        '''
        self.assertEqual('crontab -u root /tmp', cron._get_cron_cmdstr(STUB_PATH, STUB_USER))

    def test__date_time_match(self):
        '''
        Passes if a match is found on all elements. Note the conversions to strings here!
        :return:
        '''
        self.assertTrue(cron._date_time_match(STUB_CRON_TIMESTAMP,
                                    minute=STUB_CRON_TIMESTAMP['minute'],
                                    hour=STUB_CRON_TIMESTAMP['hour'],
                                    daymonth=STUB_CRON_TIMESTAMP['daymonth'],
                                    dayweek=STUB_CRON_TIMESTAMP['dayweek']
                                    ))

    @patch('salt.modules.cron.raw_cron', new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON))
    def test_list_tab(self):
        self.assertDictEqual(STUB_SIMPLE_CRON_DICT, cron.list_tab('DUMMY_USER'))

    @patch('salt.modules.cron._write_cron_lines')
    @patch('salt.modules.cron.list_tab', new=MagicMock(return_value=STUB_SIMPLE_CRON_DICT))
    def test_set_special(self, write_cron_lines_mock):
        expected_write_call = call('DUMMY_USER',
                                   ['5 0 * * * /tmp/no_script.sh\n',
                                    '# Lines below here are managed by Salt, do not edit\n',
                                    '@hourly echo Hi!\n'])
        ret = cron.set_special('DUMMY_USER', '@hourly', 'echo Hi!')
        write_cron_lines_mock.assert_has_calls((expected_write_call,), any_order=True)

    def test__get_cron_date_time(self):
        ret = cron._get_cron_date_time(minute=STUB_CRON_TIMESTAMP['minute'],
                                    hour=STUB_CRON_TIMESTAMP['hour'],
                                    daymonth=STUB_CRON_TIMESTAMP['daymonth'],
                                    dayweek=STUB_CRON_TIMESTAMP['dayweek'],
                                    month=STUB_CRON_TIMESTAMP['month'])
        self.assertDictEqual(ret, STUB_CRON_TIMESTAMP)

    ## FIXME: More sophisticated _get_cron_date_time checks should be added here.

    @patch('salt.modules.cron._write_cron_lines', new=MagicMock(return_value={'retcode': False}))
    @patch('salt.modules.cron.raw_cron', new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON))
    def test_set_job(self):
        with patch.dict(cron.__grains__, {'os': None}):
            cron.set_job('DUMMY_USER', 1, 2, 3, 4, 5,
                         '/bin/echo NOT A DROID',
                         'WERE YOU LOOKING FOR ME?')
            expected_call = call('DUMMY_USER',
                                 ['5 0 * * * /tmp/no_script.sh\n',
                                  '# Lines below here are managed by Salt, do not edit\n',
                                  '# WERE YOU LOOKING FOR ME?\n',
                                  '1 2 3 4 5 /bin/echo NOT A DROID\n'])
            cron._write_cron_lines.call_args.assert_called_with(expected_call)

    @patch('salt.modules.cron._write_cron_lines', new=MagicMock(return_value={'retcode': False}))
    @patch('salt.modules.cron.raw_cron', new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON))
    def test_rm_job_is_absent(self):
        with patch.dict(cron.__grains__, {'os': None}):
            ret = cron.rm_job('DUMMY_USER', '/bin/echo NOT A DROID', 1, 2, 3, 4, 5)
            self.assertEqual('absent', ret)

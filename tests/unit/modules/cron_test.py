# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from StringIO import StringIO
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

ensure_in_syspath('../../')

from salt.modules import cron

STUB_USER = 'root'
STUB_PATH = '/tmp'

STUB_CRON_TIMESTAMP = {'minute': '1',
                  'hour': '2',
                  'daymonth': '3',
                  'month': '4',
                  'dayweek': '5'}

STUB_SIMPLE_RAW_CRON = '5 0 * * * /tmp/no_script.sh'
STUB_SIMPLE_CRON_DICT = {'pre': ['5 0 * * * /tmp/no_script.sh'], 'crons': [], 'env': [], 'special': []}

__grains__ = {}
L = '# Lines below here are managed by Salt, do not edit\n'


CRONTAB = StringIO()


def get_crontab(*args, **kw):
    return CRONTAB.getvalue()


def set_crontab(val):
    CRONTAB.truncate(0)
    CRONTAB.write(val)


def write_crontab(*args, **kw):
    set_crontab('\n'.join(
        [a.strip() for a in args[1]]))
    return MagicMock()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CronTestCase(TestCase):

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
            set_crontab(L + '* * * * * ls\n')
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
                     'minute': '*', 'month': '*'},
                    {'cmd': 'too', 'comment': 'uuoo', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*'},
                    {'cmd': 'zoo', 'comment': 'uuuoo', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*'},
                    {'cmd': 'yoo', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*'},
                    {'cmd': 'xoo', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*'},
                    {'cmd': 'samecmd', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '*', 'month': '*'},
                    {'cmd': 'samecmd', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '*', 'month': '*'},
                    {'cmd': 'otheridcmd', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '*', 'month': '*'},
                    {'cmd': 'otheridcmd', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '*', 'month': '*'},
                    {'cmd': 'samecmd1', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': 'NO ID SET',
                     'minute': '0', 'month': '*'},
                    {'cmd': 'samecmd1', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '1', 'month': '*'},
                    {'cmd': 'otheridcmd1', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '0', 'month': '*'},
                    {'cmd': 'otheridcmd1', 'comment': None, 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': None,
                     'minute': '1', 'month': '*'},
                    {'cmd': 'otheridcmd1', 'comment': '', 'daymonth': '*',
                     'dayweek': '*', 'hour': '*', 'identifier': '1',
                     'minute': '0', 'month': '*'},
                    {'cmd': 'otheridcmd1',
                     'comment': '', 'daymonth': '*', 'dayweek': '*',
                     'hour': '*', 'identifier': '2', 'minute': '0',
                     'month': '*'}
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
                        "idx {0}\n '{1}'\n != \n'{2}'\n\n\n"
                        "{1!r} != {2!r}"
                    ).format(
                        idx, get_crontab(), inc_tests[idx]))

    @patch('salt.modules.cron.raw_cron',
           new=MagicMock(side_effect=[
               (L + '\n'),
               (L + '* * * * * ls\nn'),
               (L + '# foo\n'
                '* * * * * ls\n'),
               (L + '# foo {0}:blah\n'.format(
                   cron.SALT_CRON_IDENTIFIER) +
                   '* * * * * ls\n'),
           ]))
    def test__load_tab(self):
        cron.__grains__ = __grains__
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            crons1 = cron.list_tab('root')
            crons2 = cron.list_tab('root')
            crons3 = cron.list_tab('root')
            crons4 = cron.list_tab('root')
            self.assertEqual(
                crons1,
                {'pre': [], 'crons': [], 'env': [], 'special': []})
            self.assertEqual(
                crons2['crons'][0],
                {'comment': None,
                 'dayweek': '*',
                 'hour': '*',
                 'identifier': None,
                 'cmd': 'ls',
                 'daymonth': '*',
                 'minute': '*',
                 'month': '*'})
            self.assertEqual(
                crons3['crons'][0],
                {'comment': 'foo',
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
                 'dayweek': '*',
                 'hour': '*',
                 'identifier': 'blah',
                 'cmd': 'ls',
                 'daymonth': '*',
                 'minute': '*',
                 'month': '*'})


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PsTestCase(TestCase):
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
    def test__get_cron_cmdstr_solaris(self):
        cron.__grains__ = __grains__
        with patch.dict(cron.__grains__, {'os_family': 'Solaris'}):
            self.assertEqual('su - root -c "crontab /tmp"',
                             cron._get_cron_cmdstr(STUB_USER, STUB_PATH))

    def test__get_cron_cmdstr(self):
        cron.__grains__ = __grains__
        with patch.dict(cron.__grains__, {'os_family': None}):
            self.assertEqual('crontab -u root /tmp',
                             cron._get_cron_cmdstr(STUB_USER, STUB_PATH))

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
        write_cron_lines_mock.assert_has_calls(expected_write_call)

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
        cron.__grains__ = __grains__
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests([
        PsTestCase,
        CronTestCase
    ], needs_daemon=False)

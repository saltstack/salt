"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

import builtins
import io

import salt.modules.cron as cron
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, mock_open, patch
from tests.support.unit import TestCase

STUB_USER = "root"
STUB_PATH = "/tmp"

STUB_CRON_TIMESTAMP = {
    "minute": "1",
    "hour": "2",
    "daymonth": "3",
    "month": "4",
    "dayweek": "5",
}

STUB_SIMPLE_RAW_CRON = "5 0 * * * /tmp/no_script.sh"
STUB_SIMPLE_CRON_DICT = {
    "pre": ["5 0 * * * /tmp/no_script.sh"],
    "crons": [],
    "env": [],
    "special": [],
}
STUB_CRON_SPACES = """
# Lines below here are managed by Salt, do not edit
TEST_VAR="a string with plenty of spaces"
# SALT_CRON_IDENTIFIER:echo "must  be  double  spaced"
11 * * * * echo "must  be  double  spaced"
"""
STUB_AT_SIGN = """
# Lines below here are managed by Salt, do not edit
# SALT_CRON_IDENTIFIER:echo "cron with @ sign"
@daily echo "cron with @ sign"
@daily
"""
STUB_NO_AT_SIGN = """
# Lines below here are managed by Salt, do not edit
# SALT_CRON_IDENTIFIER:echo "cron without @ sign"
1 2 3 4 5 echo "cron without @ sign"
"""

L = "# Lines below here are managed by Salt, do not edit\n"

CRONTAB = io.StringIO()


def get_crontab(*args, **kw):
    return CRONTAB.getvalue()


def set_crontab(val):
    CRONTAB.seek(0)
    CRONTAB.truncate(0)
    CRONTAB.write(val)


def write_crontab(*args, **kw):
    set_crontab("\n".join([a.strip() for a in args[1]]))
    return MagicMock()


class CronTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {cron: {}}

    def test__need_changes_new(self):
        """
        New behavior, identifier will get track of the managed lines!
        """
        with patch(
            "salt.modules.cron.raw_cron", new=MagicMock(side_effect=get_crontab)
        ), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(side_effect=write_crontab),
        ):
            # when there are no identifiers,
            # we do not touch it
            set_crontab(L + "# SALT_CRON_IDENTIFIER:booh\n* * * * * ls\n")
            cron.set_job(
                user="root",
                minute="*",
                hour="*",
                daymonth="*",
                month="*",
                dayweek="*",
                cmd="ls",
                comment=None,
                identifier=None,
            )
            c1 = get_crontab()
            set_crontab(L + "* * * * * ls\n")
            self.assertEqual(
                c1,
                "# Lines below here are managed by Salt, do not edit\n"
                "# SALT_CRON_IDENTIFIER:booh\n"
                "* * * * * ls\n"
                "* * * * * ls",
            )
            # whenever we have an identifier, hourray even without comment
            # we can match and edit the crontab in place
            # without cluttering the crontab with new cmds
            set_crontab(L + "# SALT_CRON_IDENTIFIER:bar\n* * * * * ls\n")
            cron.set_job(
                user="root",
                minute="*",
                hour="*",
                daymonth="*",
                month="*",
                dayweek="*",
                cmd="ls",
                comment=None,
                identifier="bar",
            )
            c5 = get_crontab()
            set_crontab(L + "* * * * * ls\n")
            self.assertEqual(
                c5,
                "# Lines below here are managed by Salt, do not edit\n"
                "# SALT_CRON_IDENTIFIER:bar\n"
                "* * * * * ls\n",
            )
            # we can even change the other parameters as well
            # thx to the id
            set_crontab(L + "# SALT_CRON_IDENTIFIER:bar\n* * * * * ls\n")
            cron.set_job(
                user="root",
                minute="1",
                hour="2",
                daymonth="3",
                month="4",
                dayweek="5",
                cmd="foo",
                comment="moo",
                identifier="bar",
            )
            c6 = get_crontab()
            self.assertEqual(
                c6,
                "# Lines below here are managed by Salt, do not edit\n"
                "# moo SALT_CRON_IDENTIFIER:bar\n"
                "1 2 3 4 5 foo",
            )

    def test__unicode_match(self):
        with patch.object(builtins, "__salt_system_encoding__", "utf-8"):
            self.assertTrue(cron._cron_matched({"identifier": "1"}, "foo", 1))
            self.assertTrue(cron._cron_matched({"identifier": "é"}, "foo", "é"))
            self.assertTrue(cron._cron_matched({"identifier": "é"}, "foo", "é"))
            self.assertTrue(cron._cron_matched({"identifier": "é"}, "foo", "é"))
            self.assertTrue(cron._cron_matched({"identifier": "é"}, "foo", "é"))

    def test__need_changes_old(self):
        """
        old behavior; ID has no special action
        - If an id is found, it will be added as a new crontab
          even if there is a cmd that looks like this one
        - no comment, delete the cmd and readd it
        - comment: idem
        """
        with patch(
            "salt.modules.cron.raw_cron", new=MagicMock(side_effect=get_crontab)
        ), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(side_effect=write_crontab),
        ):
            set_crontab(L + "* * * * * ls\n\n")
            cron.set_job(
                user="root",
                minute="*",
                hour="*",
                daymonth="*",
                month="*",
                dayweek="*",
                cmd="ls",
                comment=None,
                identifier=cron.SALT_CRON_NO_IDENTIFIER,
            )
            c1 = get_crontab()
            set_crontab(L + "* * * * * ls\n")
            self.assertEqual(
                c1,
                "# Lines below here are managed by Salt, do not edit\n* * * * * ls\n\n",
            )
            cron.set_job(
                user="root",
                minute="*",
                hour="*",
                daymonth="*",
                month="*",
                dayweek="*",
                cmd="ls",
                comment="foo",
                identifier=cron.SALT_CRON_NO_IDENTIFIER,
            )
            c2 = get_crontab()
            self.assertEqual(
                c2,
                "# Lines below here are managed by Salt, do not edit\n"
                "# foo\n* * * * * ls",
            )
            set_crontab(L + "* * * * * ls\n")
            cron.set_job(
                user="root",
                minute="*",
                hour="*",
                daymonth="*",
                month="*",
                dayweek="*",
                cmd="lsa",
                comment="foo",
                identifier="bar",
            )
            c3 = get_crontab()
            self.assertEqual(
                c3,
                "# Lines below here are managed by Salt, do not edit\n"
                "* * * * * ls\n"
                "# foo SALT_CRON_IDENTIFIER:bar\n"
                "* * * * * lsa",
            )
            set_crontab(L + "* * * * * ls\n")
            cron.set_job(
                user="root",
                minute="*",
                hour="*",
                daymonth="*",
                month="*",
                dayweek="*",
                cmd="foo",
                comment="foo",
                identifier="bar",
            )
            c4 = get_crontab()
            self.assertEqual(
                c4,
                "# Lines below here are managed by Salt, do not edit\n"
                "* * * * * ls\n"
                "# foo SALT_CRON_IDENTIFIER:bar\n"
                "* * * * * foo",
            )
            set_crontab(L + "* * * * * ls\n")
            cron.set_job(
                user="root",
                minute="*",
                hour="*",
                daymonth="*",
                month="*",
                dayweek="*",
                cmd="ls",
                comment="foo",
                identifier="bbar",
            )
            c4 = get_crontab()
            self.assertEqual(
                c4,
                "# Lines below here are managed by Salt, do not edit\n"
                "# foo SALT_CRON_IDENTIFIER:bbar\n"
                "* * * * * ls",
            )

    def test__issue10959(self):
        """
        handle multi old style crontabs
        https://github.com/saltstack/salt/issues/10959
        """
        with patch(
            "salt.modules.cron.raw_cron", new=MagicMock(side_effect=get_crontab)
        ), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(side_effect=write_crontab),
        ):
            set_crontab(
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                # as managed per salt, the last lines will be merged together !
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * samecmd\n"
                "* * * * * otheridcmd\n"
                "* * * * * otheridcmd\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n0 * * * * samecmd1\n"
                "1 * * * * samecmd1\n"
                "0 * * * * otheridcmd1\n"
                "1 * * * * otheridcmd1\n"
                # special case here, none id managed line with same command
                # as a later id managed line will become managed
                "# SALT_CRON_IDENTIFIER:1\n0 * * * * otheridcmd1\n"
                "# SALT_CRON_IDENTIFIER:2\n0 * * * * otheridcmd1\n"
            )
            crons1 = cron.list_tab("root")
            # the filtering is done on save, we reflect in listing
            # the same that we have in a file, no matter what we
            # have
            self.assertEqual(
                crons1,
                {
                    "crons": [
                        {
                            "cmd": "ls",
                            "comment": "uoo",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "NO ID SET",
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "too",
                            "comment": "uuoo",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "NO ID SET",
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "zoo",
                            "comment": "uuuoo",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "NO ID SET",
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "yoo",
                            "comment": "",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "NO ID SET",
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "xoo",
                            "comment": "",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "NO ID SET",
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "samecmd",
                            "comment": "",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "NO ID SET",
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "samecmd",
                            "comment": None,
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": None,
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "otheridcmd",
                            "comment": None,
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": None,
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "otheridcmd",
                            "comment": None,
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": None,
                            "minute": "*",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "samecmd1",
                            "comment": "",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "NO ID SET",
                            "minute": "0",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "samecmd1",
                            "comment": None,
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": None,
                            "minute": "1",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "otheridcmd1",
                            "comment": None,
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": None,
                            "minute": "0",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "otheridcmd1",
                            "comment": None,
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": None,
                            "minute": "1",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "otheridcmd1",
                            "comment": "",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "1",
                            "minute": "0",
                            "month": "*",
                            "commented": False,
                        },
                        {
                            "cmd": "otheridcmd1",
                            "comment": "",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "2",
                            "minute": "0",
                            "month": "*",
                            "commented": False,
                        },
                    ],
                    "env": [],
                    "pre": [],
                    "special": [],
                },
            )
            # so yood so far, no problem for now, trying to save the
            # multilines without id crons now
            inc_tests = [
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n"
                "0 * * * * samecmd1",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n"
                "0 * * * * otheridcmd1",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n"
                "1 * * * * otheridcmd1",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n"
                "# SALT_CRON_IDENTIFIER:1\n0 * * * * otheridcmd1",
                #
                "# Lines below here are managed by Salt, do not edit\n"
                "# uoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * ls\n"
                "# uuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * too\n"
                "# uuuoo SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * zoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * yoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * xoo\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n* * * * * samecmd\n"
                "* * * * * otheridcmd\n"
                "# SALT_CRON_IDENTIFIER:NO ID SET\n1 * * * * samecmd1\n"
                "# SALT_CRON_IDENTIFIER:1\n0 * * * * otheridcmd1\n"
                "# SALT_CRON_IDENTIFIER:2\n0 * * * * otheridcmd1",
            ]
            set_crontab("")
            for idx, cr in enumerate(crons1["crons"]):
                cron.set_job("root", **cr)
                self.assertEqual(
                    get_crontab(),
                    inc_tests[idx],
                    ("idx {0}\n'{1}'\n != \n'{2}'\n\n\n'{1}' != '{2}'").format(
                        idx, get_crontab(), inc_tests[idx]
                    ),
                )

    def test_list_tab_commented_cron_jobs(self):
        """
        handle commented cron jobs
        https://github.com/saltstack/salt/issues/29082
        """
        with patch(
            "salt.modules.cron.raw_cron", MagicMock(side_effect=get_crontab)
        ), patch(
            "salt.modules.cron._write_cron_lines", MagicMock(side_effect=write_crontab)
        ):
            set_crontab(
                "# An unmanaged commented cron job\n"
                "#0 * * * * /bin/true\n"
                "# Lines below here are managed by Salt, do not edit\n"
                "# cron_1 SALT_CRON_IDENTIFIER:cron_1\n#DISABLED#0 * * * * my_cmd_1\n"
                "# cron_2 SALT_CRON_IDENTIFIER:cron_2\n#DISABLED#* * * * * my_cmd_2\n"
                "# cron_3 SALT_CRON_IDENTIFIER:cron_3\n"
                "#DISABLED#but it is a comment line"
                "#DISABLED#0 * * * * my_cmd_3\n"
                "# cron_4 SALT_CRON_IDENTIFIER:cron_4\n0 * * * * my_cmd_4\n"
            )
            crons1 = cron.list_tab("root")
            self.assertEqual(
                crons1,
                {
                    "crons": [
                        {
                            "cmd": "my_cmd_1",
                            "comment": "cron_1",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "cron_1",
                            "minute": "0",
                            "month": "*",
                            "commented": True,
                        },
                        {
                            "cmd": "my_cmd_2",
                            "comment": "cron_2",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "cron_2",
                            "minute": "*",
                            "month": "*",
                            "commented": True,
                        },
                        {
                            "cmd": "line#DISABLED#0 * * * * my_cmd_3",
                            "comment": "cron_3",
                            "daymonth": "is",
                            "dayweek": "comment",
                            "hour": "it",
                            "identifier": "cron_3",
                            "minute": "but",
                            "month": "a",
                            "commented": True,
                        },
                        {
                            "cmd": "my_cmd_4",
                            "comment": "cron_4",
                            "daymonth": "*",
                            "dayweek": "*",
                            "hour": "*",
                            "identifier": "cron_4",
                            "minute": "0",
                            "month": "*",
                            "commented": False,
                        },
                    ],
                    "env": [],
                    "pre": [
                        "# An unmanaged commented cron job",
                        "#0 * * * * /bin/true",
                    ],
                    "special": [],
                },
            )

    def test_get_entry(self):
        """
        test get_entry function
        """
        list_tab_output = {
            "crons": [
                {
                    "cmd": "my_cmd_1",
                    "comment": "cron_1",
                    "daymonth": "*",
                    "dayweek": "*",
                    "hour": "*",
                    "identifier": "cron_1",
                    "minute": "0",
                    "month": "*",
                    "commented": True,
                },
                {
                    "cmd": "my_cmd_2",
                    "comment": "cron_2",
                    "daymonth": "*",
                    "dayweek": "*",
                    "hour": "*",
                    "identifier": "cron_2",
                    "minute": "*",
                    "month": "*",
                    "commented": True,
                },
                {
                    "cmd": "line#DISABLED#0 * * * * my_cmd_3",
                    "comment": "cron_3",
                    "daymonth": "is",
                    "dayweek": "comment",
                    "hour": "it",
                    "identifier": "cron_3",
                    "minute": "but",
                    "month": "a",
                    "commented": True,
                },
                {
                    "cmd": "my_cmd_4",
                    "comment": "cron_4",
                    "daymonth": "*",
                    "dayweek": "*",
                    "hour": "*",
                    "identifier": "cron_4",
                    "minute": "0",
                    "month": "*",
                    "commented": False,
                },
            ],
            "env": [],
            "pre": ["# An unmanaged commented cron job", "#0 * * * * /bin/true"],
            "special": [],
        }
        get_entry_2 = {
            "comment": "cron_2",
            "cmd": "my_cmd_2",
            "identifier": "cron_2",
            "dayweek": "*",
            "daymonth": "*",
            "hour": "*",
            "minute": "*",
            "month": "*",
            "commented": True,
        }
        get_entry_3 = {
            "comment": "cron_3",
            "identifier": "cron_3",
            "dayweek": "comment",
            "hour": "it",
            "cmd": "line#DISABLED#0 * * * * my_cmd_3",
            "daymonth": "is",
            "commented": True,
            "minute": "but",
            "month": "a",
        }
        with patch(
            "salt.modules.cron.list_tab", new=MagicMock(return_value=list_tab_output)
        ):
            # Test get_entry identifier
            get_entry_output = cron.get_entry("root", identifier="cron_3")
            self.assertDictEqual(get_entry_output, get_entry_3)
            # Test get_entry cmd
            get_entry_output = cron.get_entry("root", cmd="my_cmd_2")
            self.assertDictEqual(get_entry_output, get_entry_2)
            # Test identifier wins when both specified
            get_entry_output = cron.get_entry(
                "root", identifier="cron_3", cmd="my_cmd_2"
            )
            self.assertDictEqual(get_entry_output, get_entry_3)

    def test_cron_extra_spaces(self):
        """
        Issue #38449
        """
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron.raw_cron", MagicMock(return_value=STUB_CRON_SPACES)
        ):
            ret = cron.list_tab("root")
            eret = {
                "crons": [
                    {
                        "cmd": 'echo "must  be  double  spaced"',
                        "comment": "",
                        "commented": False,
                        "daymonth": "*",
                        "dayweek": "*",
                        "hour": "*",
                        "identifier": 'echo "must  be  double  spaced"',
                        "minute": "11",
                        "month": "*",
                    }
                ],
                "env": [
                    {"name": "TEST_VAR", "value": '"a string with plenty of spaces"'}
                ],
                "pre": [""],
                "special": [],
            }
            self.assertEqual(eret, ret)

    def test_cron_at_sign(self):
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron.raw_cron", MagicMock(return_value=STUB_AT_SIGN)
        ):
            ret = cron.list_tab("root")
            eret = {
                "crons": [],
                "env": [],
                "pre": [""],
                "special": [
                    {
                        "cmd": 'echo "cron with @ sign"',
                        "comment": "",
                        "commented": False,
                        "identifier": 'echo "cron with @ sign"',
                        "spec": "@daily",
                    }
                ],
            }
            self.assertDictEqual(eret, ret)

    def test__load_tab(self):
        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch(
            "salt.modules.cron.raw_cron",
            new=MagicMock(
                side_effect=[
                    (L + "\n"),
                    (L + "* * * * * ls\nn"),
                    (L + "# commented\n#DISABLED#* * * * * ls\n"),
                    (L + "# foo\n* * * * * ls\n"),
                    (
                        L
                        + f"# foo {cron.SALT_CRON_IDENTIFIER}:blah\n"
                        + "* * * * * ls\n"
                    ),
                ]
            ),
        ):
            crons1 = cron.list_tab("root")
            crons2 = cron.list_tab("root")
            crons3 = cron.list_tab("root")
            crons4 = cron.list_tab("root")
            crons5 = cron.list_tab("root")
            self.assertEqual(crons1, {"pre": [], "crons": [], "env": [], "special": []})
            self.assertEqual(
                crons2["crons"][0],
                {
                    "comment": None,
                    "commented": False,
                    "dayweek": "*",
                    "hour": "*",
                    "identifier": None,
                    "cmd": "ls",
                    "daymonth": "*",
                    "minute": "*",
                    "month": "*",
                },
            )
            self.assertEqual(
                crons3["crons"][0],
                {
                    "comment": "commented",
                    "commented": True,
                    "dayweek": "*",
                    "hour": "*",
                    "identifier": None,
                    "cmd": "ls",
                    "daymonth": "*",
                    "minute": "*",
                    "month": "*",
                },
            )
            self.assertEqual(
                crons4["crons"][0],
                {
                    "comment": "foo",
                    "commented": False,
                    "dayweek": "*",
                    "hour": "*",
                    "identifier": None,
                    "cmd": "ls",
                    "daymonth": "*",
                    "minute": "*",
                    "month": "*",
                },
            )
            self.assertEqual(
                crons5["crons"][0],
                {
                    "comment": "foo",
                    "commented": False,
                    "dayweek": "*",
                    "hour": "*",
                    "identifier": "blah",
                    "cmd": "ls",
                    "daymonth": "*",
                    "minute": "*",
                    "month": "*",
                },
            )

    def test_write_cron_file_root_rh(self):
        """
        Assert that write_cron_file() is called with the correct cron command and user: RedHat
          - If instance running uid matches crontab user uid, run without -u flag.
        """
        with patch.dict(cron.__grains__, {"os_family": "RedHat"}), patch.dict(
            cron.__salt__, {"cmd.retcode": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match",
            new=MagicMock(return_value=True),
        ):
            cron.write_cron_file(STUB_USER, STUB_PATH)
            cron.__salt__["cmd.retcode"].assert_called_with(
                "crontab /tmp", python_shell=False
            )

    def test_write_cron_file_foo_rh(self):
        """
        Assert that write_cron_file() is called with the correct cron command and user: RedHat
          - If instance running with uid that doesn't match crontab user uid, runas foo
        """
        with patch.dict(cron.__grains__, {"os_family": "RedHat"}), patch.dict(
            cron.__salt__, {"cmd.retcode": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=False)
        ):
            cron.write_cron_file("foo", STUB_PATH)
            cron.__salt__["cmd.retcode"].assert_called_with(
                "crontab /tmp", runas="foo", python_shell=False
            )

    def test_write_cron_file_root_sol(self):
        """
        Assert that write_cron_file() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch.dict(
            cron.__salt__, {"cmd.retcode": MagicMock()}
        ):
            cron.write_cron_file(STUB_USER, STUB_PATH)
            cron.__salt__["cmd.retcode"].assert_called_with(
                "crontab /tmp", runas=STUB_USER, python_shell=False
            )

    def test_write_cron_file_foo_sol(self):
        """
        Assert that write_cron_file() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch.dict(
            cron.__salt__, {"cmd.retcode": MagicMock()}
        ):
            cron.write_cron_file("foo", STUB_PATH)
            cron.__salt__["cmd.retcode"].assert_called_with(
                "crontab /tmp", runas="foo", python_shell=False
            )

    def test_write_cron_file_root_aix(self):
        """
        Assert that write_cron_file() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "AIX"}), patch.dict(
            cron.__salt__, {"cmd.retcode": MagicMock()}
        ):
            cron.write_cron_file(STUB_USER, STUB_PATH)
            cron.__salt__["cmd.retcode"].assert_called_with(
                "crontab /tmp", runas=STUB_USER, python_shell=False
            )

    def test_write_cron_file_foo_aix(self):
        """
        Assert that write_cron_file() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "AIX"}), patch.dict(
            cron.__salt__, {"cmd.retcode": MagicMock()}
        ):
            cron.write_cron_file("foo", STUB_PATH)
            cron.__salt__["cmd.retcode"].assert_called_with(
                "crontab /tmp", runas="foo", python_shell=False
            )

    def test_write_cr_file_v_root_rh(self):
        """
        Assert that write_cron_file_verbose() is called with the correct cron command and user: RedHat
          - If instance running uid matches crontab user uid, run without -u flag.
        """
        with patch.dict(cron.__grains__, {"os_family": "Redhat"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=True)
        ):
            cron.write_cron_file_verbose(STUB_USER, STUB_PATH)
            cron.__salt__["cmd.run_all"].assert_called_with(
                "crontab /tmp", python_shell=False
            )

    def test_write_cr_file_v_foo_rh(self):
        """
        Assert that write_cron_file_verbose() is called with the correct cron command and user: RedHat
          - If instance running with uid that doesn't match crontab user uid, runas 'foo'
        """
        with patch.dict(cron.__grains__, {"os_family": "Redhat"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=False)
        ):
            cron.write_cron_file_verbose("foo", STUB_PATH)
            cron.__salt__["cmd.run_all"].assert_called_with(
                "crontab /tmp", runas="foo", python_shell=False
            )

    def test_write_cr_file_v_root_sol(self):
        """
        Assert that write_cron_file_verbose() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ):
            cron.write_cron_file_verbose(STUB_USER, STUB_PATH)
            cron.__salt__["cmd.run_all"].assert_called_with(
                "crontab /tmp", runas=STUB_USER, python_shell=False
            )

    def test_write_cr_file_v_foo_sol(self):
        """
        Assert that write_cron_file_verbose() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ):
            cron.write_cron_file_verbose("foo", STUB_PATH)
            cron.__salt__["cmd.run_all"].assert_called_with(
                "crontab /tmp", runas="foo", python_shell=False
            )

    def test_write_cr_file_v_root_aix(self):
        """
        Assert that write_cron_file_verbose() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "AIX"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ):
            cron.write_cron_file_verbose(STUB_USER, STUB_PATH)
            cron.__salt__["cmd.run_all"].assert_called_with(
                "crontab /tmp", runas=STUB_USER, python_shell=False
            )

    def test_write_cr_file_v_foo_aix(self):
        """
        Assert that write_cron_file_verbose() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "AIX"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ):
            cron.write_cron_file_verbose("foo", STUB_PATH)
            cron.__salt__["cmd.run_all"].assert_called_with(
                "crontab /tmp", runas="foo", python_shell=False
            )

    def test_raw_cron_root_redhat(self):
        """
        Assert that raw_cron() is called with the correct cron command and user: RedHat
          - If instance running uid matches crontab user uid, runas STUB_USER without -u flag.
        """
        with patch.dict(cron.__grains__, {"os_family": "Redhat"}), patch.dict(
            cron.__salt__, {"cmd.run_stdout": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=True)
        ):
            cron.raw_cron(STUB_USER)
            cron.__salt__["cmd.run_stdout"].assert_called_with(
                "crontab -l", ignore_retcode=True, rstrip=False, python_shell=False
            )

    def test_raw_cron_foo_redhat(self):
        """
        Assert that raw_cron() is called with the correct cron command and user: RedHat
          - If instance running with uid that doesn't match crontab user uid, run with -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "Redhat"}), patch.dict(
            cron.__salt__, {"cmd.run_stdout": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=False)
        ):
            cron.raw_cron(STUB_USER)
            cron.__salt__["cmd.run_stdout"].assert_called_with(
                "crontab -l",
                runas=STUB_USER,
                ignore_retcode=True,
                rstrip=False,
                python_shell=False,
            )

    def test_raw_cron_root_solaris(self):
        """
        Assert that raw_cron() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch.dict(
            cron.__salt__, {"cmd.run_stdout": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=True)
        ):
            cron.raw_cron(STUB_USER)
            cron.__salt__["cmd.run_stdout"].assert_called_with(
                "crontab -l",
                runas=STUB_USER,
                ignore_retcode=True,
                rstrip=False,
                python_shell=False,
            )

    def test_raw_cron_foo_solaris(self):
        """
        Assert that raw_cron() is called with the correct cron command and user: Solaris
          - Solaris should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch.dict(
            cron.__salt__, {"cmd.run_stdout": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=False)
        ):
            cron.raw_cron(STUB_USER)
            cron.__salt__["cmd.run_stdout"].assert_called_with(
                "crontab -l",
                runas=STUB_USER,
                ignore_retcode=True,
                rstrip=False,
                python_shell=False,
            )

    def test_raw_cron_root_aix(self):
        """
        Assert that raw_cron() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "AIX"}), patch.dict(
            cron.__salt__, {"cmd.run_stdout": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=True)
        ):
            cron.raw_cron(STUB_USER)
            cron.__salt__["cmd.run_stdout"].assert_called_with(
                "crontab -l",
                runas=STUB_USER,
                ignore_retcode=True,
                rstrip=False,
                python_shell=False,
            )

    def test_raw_cron_foo_aix(self):
        """
        Assert that raw_cron() is called with the correct cron command and user: AIX
          - AIX should always run without a -u flag
        """
        with patch.dict(cron.__grains__, {"os_family": "AIX"}), patch.dict(
            cron.__salt__, {"cmd.run_stdout": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match", MagicMock(return_value=False)
        ):
            cron.raw_cron(STUB_USER)
            cron.__salt__["cmd.run_stdout"].assert_called_with(
                "crontab -l",
                runas=STUB_USER,
                ignore_retcode=True,
                rstrip=False,
                python_shell=False,
            )


class PsTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {cron: {}}

    def test__needs_change(self):
        self.assertTrue(cron._needs_change(True, False))

    def test__needs_change_random(self):
        """
        Assert that if the new var is 'random' and old is '* that we return True
        """
        self.assertTrue(cron._needs_change("*", "random"))

    ## Still trying to figure this one out.
    # def test__render_tab(self):
    #     pass
    def test__get_cron_cmdstr(self):
        self.assertEqual("crontab /tmp", cron._get_cron_cmdstr(STUB_PATH))

    # Test get_cron_cmdstr() when user is added
    def test__get_cron_cmdstr_user(self):
        """
        Passes if a user is added to crontab command
        """
        self.assertEqual(
            "crontab -u root /tmp", cron._get_cron_cmdstr(STUB_PATH, STUB_USER)
        )

    def test__date_time_match(self):
        """
        Passes if a match is found on all elements. Note the conversions to strings here!
        :return:
        """
        self.assertTrue(
            cron._date_time_match(
                STUB_CRON_TIMESTAMP,
                minute=STUB_CRON_TIMESTAMP["minute"],
                hour=STUB_CRON_TIMESTAMP["hour"],
                daymonth=STUB_CRON_TIMESTAMP["daymonth"],
                dayweek=STUB_CRON_TIMESTAMP["dayweek"],
            )
        )

    def test_list_tab(self):
        with patch(
            "salt.modules.cron.raw_cron",
            new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON),
        ):
            self.assertDictEqual(STUB_SIMPLE_CRON_DICT, cron.list_tab("DUMMY_USER"))

    def test_set_special(self):
        with patch(
            "salt.modules.cron._write_cron_lines"
        ) as write_cron_lines_mock, patch(
            "salt.modules.cron.list_tab",
            new=MagicMock(return_value=STUB_SIMPLE_CRON_DICT),
        ):
            expected_write_call = call(
                "DUMMY_USER",
                [
                    "5 0 * * * /tmp/no_script.sh\n",
                    "# Lines below here are managed by Salt, do not edit\n",
                    "@hourly echo Hi!\n",
                ],
            )
            ret = cron.set_special("DUMMY_USER", "@hourly", "echo Hi!")
            write_cron_lines_mock.assert_has_calls(
                (expected_write_call,), any_order=True
            )

    def test_set_special_from_job(self):
        """Use set_special to turn a non-special entry into a special one"""
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(return_value={"retcode": False}),
        ), patch(
            "salt.modules.cron.raw_cron",
            new=MagicMock(side_effect=[STUB_NO_AT_SIGN, STUB_NO_AT_SIGN, L]),
        ):
            expected_call = call(
                "DUMMY_USER",
                [
                    "# Lines below here are managed by Salt, do not edit\n",
                    '# SALT_CRON_IDENTIFIER:echo "cron without @ sign"\n',
                    '@daily echo "cron without @ sign"\n',
                ],
            )
            ret = cron.set_special(
                "DUMMY_USER",
                "@daily",
                'echo "cron without @ sign"',
                identifier='echo "cron without @ sign"',
            )
            cron._write_cron_lines.assert_has_calls((expected_call,), any_order=True)

    def test__get_cron_date_time(self):
        ret = cron._get_cron_date_time(
            minute=STUB_CRON_TIMESTAMP["minute"],
            hour=STUB_CRON_TIMESTAMP["hour"],
            daymonth=STUB_CRON_TIMESTAMP["daymonth"],
            dayweek=STUB_CRON_TIMESTAMP["dayweek"],
            month=STUB_CRON_TIMESTAMP["month"],
        )
        self.assertDictEqual(ret, STUB_CRON_TIMESTAMP)

    def test__get_cron_date_time_daymonth_max(self):
        ret = cron._get_cron_date_time(
            minute="random",
            hour="random",
            daymonth="random",
            dayweek="random",
            month="random",
        )
        self.assertTrue(int(ret["minute"]) in range(0, 60))
        self.assertTrue(int(ret["hour"]) in range(0, 24))
        self.assertTrue(int(ret["daymonth"]) in range(1, 32))
        self.assertTrue(int(ret["dayweek"]) in range(0, 8))
        self.assertTrue(int(ret["month"]) in range(1, 13))

    def test_set_job(self):
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(return_value={"retcode": False}),
        ), patch(
            "salt.modules.cron.raw_cron",
            new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON),
        ):
            cron.set_job(
                "DUMMY_USER",
                1,
                2,
                3,
                4,
                5,
                "/bin/echo NOT A DROID",
                comment="WERE YOU LOOKING FOR ME?",
            )
            expected_call = call(
                "DUMMY_USER",
                [
                    "5 0 * * * /tmp/no_script.sh\n",
                    "# Lines below here are managed by Salt, do not edit\n",
                    "# WERE YOU LOOKING FOR ME?\n",
                    "1 2 3 4 5 /bin/echo NOT A DROID\n",
                ],
            )
            cron._write_cron_lines.assert_has_calls((expected_call,), any_order=True)

    def test_set_job_from_special(self):
        """Use set_job to turn a special entry into a non-special one"""
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(return_value={"retcode": False}),
        ), patch(
            "salt.modules.cron.raw_cron",
            new=MagicMock(side_effect=[STUB_AT_SIGN, STUB_AT_SIGN, L]),
        ):
            cron.set_job(
                "DUMMY_USER",
                1,
                2,
                3,
                4,
                5,
                'echo "cron with @ sign"',
                identifier='echo "cron with @ sign"',
            )
            expected_call = call(
                "DUMMY_USER",
                [
                    "# Lines below here are managed by Salt, do not edit\n",
                    '# SALT_CRON_IDENTIFIER:echo "cron with @ sign"\n',
                    '1 2 3 4 5 echo "cron with @ sign"\n',
                ],
            )
            cron._write_cron_lines.assert_has_calls((expected_call,), any_order=True)

    def test_rm_special(self):
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(return_value={"retcode": False}),
        ), patch(
            "salt.modules.cron.raw_cron", new=MagicMock(return_value=STUB_AT_SIGN)
        ):
            ret = cron.rm_special(
                "root",
                'echo "cron with @ sign"',
                special="@daily",
                identifier='echo "cron with @ sign"',
            )
            self.assertEqual("removed", ret)

    def test_rm_special_default_special(self):
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(return_value={"retcode": False}),
        ), patch(
            "salt.modules.cron.raw_cron", new=MagicMock(return_value=STUB_AT_SIGN)
        ):
            ret = cron.rm_special(
                "root", 'echo "cron with @ sign"', identifier='echo "cron with @ sign"'
            )
            self.assertEqual("removed", ret)

    def test_rm_special_absent(self):
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(return_value={"retcode": False}),
        ), patch(
            "salt.modules.cron.raw_cron", new=MagicMock(return_value=STUB_AT_SIGN)
        ):
            ret = cron.rm_special(
                "root", 'echo "there is no job"', identifier='echo "there is no job"'
            )
            self.assertEqual("absent", ret)

    def test_rm_job_is_absent(self):
        with patch.dict(cron.__grains__, {"os": None}), patch(
            "salt.modules.cron._write_cron_lines",
            new=MagicMock(return_value={"retcode": False}),
        ), patch(
            "salt.modules.cron.raw_cron",
            new=MagicMock(return_value=STUB_SIMPLE_RAW_CRON),
        ):
            ret = cron.rm_job("DUMMY_USER", "/bin/echo NOT A DROID", 1, 2, 3, 4, 5)
            self.assertEqual("absent", ret)

    def test_write_cron_lines_euid_match_user_rh(self):
        """
        Assert that _write_cron_lines() is called with the correct cron command and user
        OS: RedHat. EUID match User (either root, root or user, user).
        Expected to run without runas argument.
        """
        temp_path = "some_temp_path"
        crontab_cmd = f"crontab {temp_path}"

        with patch.dict(cron.__grains__, {"os_family": "RedHat"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match",
            new=MagicMock(return_value=True),
        ), patch(
            "salt.utils.files.fpopen", mock_open()
        ), patch(
            "salt.utils.files.mkstemp", MagicMock(return_value=temp_path)
        ), patch(
            "os.remove", MagicMock()
        ):
            cron._write_cron_lines("root", "test 123")
            cron.__salt__["cmd.run_all"].assert_called_with(
                crontab_cmd, python_shell=False
            )

    def test_write_cron_lines_root_non_root_rh(self):
        """
        Assert that _write_cron_lines() is called with the correct cron command and user
        OS: RedHat. EUID: root. User: non-root.
        Expected to run without runas argument and with -u non-root argument.
        """
        temp_path = "some_temp_path"
        crontab_cmd = "crontab -u {} {}".format("non-root", temp_path)

        with patch.dict(cron.__grains__, {"os_family": "RedHat"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match",
            new=MagicMock(side_effect=[False, True]),
        ), patch(
            "salt.utils.files.fpopen", mock_open()
        ), patch(
            "salt.utils.files.mkstemp", MagicMock(return_value=temp_path)
        ), patch(
            "os.remove", MagicMock()
        ):
            cron._write_cron_lines("non-root", "test 123")
            cron.__salt__["cmd.run_all"].assert_called_with(
                crontab_cmd, python_shell=False
            )

    def test_write_cron_lines_non_root_euid_doesnt_match_user_rh(self):
        """
        Assert that _write_cron_lines() is called with the correct cron command and user
        OS: RedHat. EUID: non-root. EUID doesn't match User.
        Expected to run with runas argument.
        """
        temp_path = "some_temp_path"
        crontab_cmd = f"crontab {temp_path}"

        with patch.dict(cron.__grains__, {"os_family": "RedHat"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ), patch(
            "salt.modules.cron._check_instance_uid_match",
            new=MagicMock(return_value=False),
        ), patch(
            "salt.utils.files.fpopen", mock_open()
        ), patch.dict(
            cron.__salt__, {"file.user_to_uid": MagicMock(return_value=1)}
        ), patch(
            "salt.utils.files.mkstemp", MagicMock(return_value=temp_path)
        ), patch(
            "os.remove", MagicMock()
        ):
            cron._write_cron_lines("non-root", "test 123")
            cron.__salt__["cmd.run_all"].assert_called_with(
                crontab_cmd, python_shell=False, runas="non-root"
            )

    def test_write_cron_lines_non_root_aix(self):
        """
        Assert that _write_cron_lines() is called with the correct cron command and user
        OS: AIX. User: non-root.
        Expected to run with runas argument.
        """
        temp_path = "some_temp_path"
        crontab_cmd = f"crontab {temp_path}"

        with patch.dict(cron.__grains__, {"os_family": "AIX"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ), patch("salt.utils.files.fpopen", mock_open()), patch.dict(
            cron.__salt__, {"file.user_to_uid": MagicMock(return_value=1)}
        ), patch(
            "salt.utils.files.mkstemp", MagicMock(return_value=temp_path)
        ), patch(
            "os.remove", MagicMock()
        ):
            cron._write_cron_lines("non-root", "test 123")
            cron.__salt__["cmd.run_all"].assert_called_with(
                crontab_cmd, python_shell=False, runas="non-root"
            )

    def test_write_cron_lines_non_root_solaris(self):
        """
        Assert that _write_cron_lines() is called with the correct cron command and user
        OS: Solaris. User: non-root.
        Expected to run with runas argument.
        """
        temp_path = "some_temp_path"
        crontab_cmd = f"crontab {temp_path}"

        with patch.dict(cron.__grains__, {"os_family": "Solaris"}), patch.dict(
            cron.__salt__, {"cmd.run_all": MagicMock()}
        ), patch("salt.utils.files.fpopen", mock_open()), patch.dict(
            cron.__salt__, {"file.user_to_uid": MagicMock(return_value=1)}
        ), patch(
            "salt.utils.files.mkstemp", MagicMock(return_value=temp_path)
        ), patch(
            "os.remove", MagicMock()
        ):
            cron._write_cron_lines("non-root", "test 123")
            cron.__salt__["cmd.run_all"].assert_called_with(
                crontab_cmd, python_shell=False, runas="non-root"
            )

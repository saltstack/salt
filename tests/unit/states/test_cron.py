"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

import io

import salt.modules.cron as cronmod
import salt.states.cron as cron
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class CronTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        loader_gloabals = {
            "__low__": {"__id__": "noo"},
            "__grains__": {"os": "Debian", "os_family": "Debian"},
            "__opts__": {"test": False},
            "__salt__": {
                "cmd.run_all": MagicMock(
                    return_value={"pid": 5, "retcode": 0, "stderr": "", "stdout": ""}
                ),
                "cron.list_tab": cronmod.list_tab,
                "cron.rm_job": cronmod.rm_job,
                "cron.set_job": cronmod.set_job,
                "cron.rm_special": cronmod.rm_special,
                "cron.set_special": cronmod.set_special,
            },
        }
        return {cron: loader_gloabals, cronmod: loader_gloabals}

    def get_crontab(self, *args, **kwargs):
        return self._crontab.getvalue()

    def set_crontab(self, data):
        self._crontab.seek(0)
        self._crontab.truncate(0)
        self._crontab.write(data)

    def write_crontab(self, *args, **kw):
        self.set_crontab("\n".join([a.strip() for a in args[1]]))
        return {
            "retcode": False,
        }

    def setUp(self):
        super().setUp()
        self._crontab = io.StringIO()
        self.addCleanup(delattr, self, "_crontab")
        self.set_crontab("")
        for mod, mock in (
            ("salt.modules.cron.raw_cron", MagicMock(side_effect=self.get_crontab)),
            (
                "salt.modules.cron._write_cron_lines",
                MagicMock(side_effect=self.write_crontab),
            ),
        ):
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.set_crontab, "")

    def test_present(self):
        cron.present(name="foo", hour="1", identifier="1", user="root")
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 1 * * * foo",
        )
        cron.present(name="foo", hour="2", identifier="1", user="root")
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 2 * * * foo",
        )
        cron.present(
            name="cmd1",
            minute="0",
            comment="Commented cron job",
            commented=True,
            identifier="commented_1",
            user="root",
        )
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 2 * * * foo\n"
            "# Commented cron job SALT_CRON_IDENTIFIER:commented_1\n"
            "#DISABLED#0 * * * * cmd1",
        )
        cron.present(name="foo", hour="2", identifier="2", user="root")
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 2 * * * foo\n"
            "# Commented cron job SALT_CRON_IDENTIFIER:commented_1\n"
            "#DISABLED#0 * * * * cmd1\n"
            "# SALT_CRON_IDENTIFIER:2\n"
            "* 2 * * * foo",
        )
        cron.present(name="cmd2", commented=True, identifier="commented_2", user="root")
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 2 * * * foo\n"
            "# Commented cron job SALT_CRON_IDENTIFIER:commented_1\n"
            "#DISABLED#0 * * * * cmd1\n"
            "# SALT_CRON_IDENTIFIER:2\n"
            "* 2 * * * foo\n"
            "# SALT_CRON_IDENTIFIER:commented_2\n"
            "#DISABLED#* * * * * cmd2",
        )
        self.set_crontab(
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 2 * * * foo\n"
            "# SALT_CRON_IDENTIFIER:2\n"
            "* 2 * * * foo\n"
            "* 2 * * * foo\n"
        )
        cron.present(name="foo", hour="2", user="root", identifier=None)
        self.assertEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 2 * * * foo\n"
            "# SALT_CRON_IDENTIFIER:2\n"
            "* 2 * * * foo\n"
            "* 2 * * * foo",
        )

    def test_present_special(self):
        cron.present(name="foo", special="@hourly", identifier="1", user="root")
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "@hourly foo",
        )

    def test_present_special_after_unspecial(self):
        """cron.present should remove an unspecial entry with the same identifier"""
        cron.present(name="foo", hour="1", identifier="1", user="root")
        cron.present(name="foo", special="@hourly", identifier="1", user="root")
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "@hourly foo",
        )

    def test_present_unspecial_after_special(self):
        """cron.present should remove an special entry with the same identifier"""
        cron.present(name="foo", special="@hourly", identifier="1", user="root")
        cron.present(name="foo", hour="1", identifier="1", user="root")
        self.assertMultiLineEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:1\n"
            "* 1 * * * foo",
        )

    def test_remove(self):
        with patch.dict(cron.__opts__, {"test": True}):
            self.set_crontab(
                "# Lines below here are managed by Salt, do not edit\n"
                "# SALT_CRON_IDENTIFIER:1\n"
                "* 1 * * * foo"
            )
            result = cron.absent(name="bar", identifier="1")
            self.assertEqual(
                result,
                {
                    "changes": {},
                    "comment": "Cron bar is set to be removed",
                    "name": "bar",
                    "result": None,
                },
            )
            self.assertEqual(
                self.get_crontab(),
                "# Lines below here are managed by Salt, do not edit\n"
                "# SALT_CRON_IDENTIFIER:1\n"
                "* 1 * * * foo",
            )
        with patch.dict(cron.__opts__, {"test": False}):
            self.set_crontab(
                "# Lines below here are managed by Salt, do not edit\n"
                "# SALT_CRON_IDENTIFIER:1\n"
                "* 1 * * * foo"
            )
            cron.absent(name="bar", identifier="1")
            self.assertEqual(
                self.get_crontab(),
                "# Lines below here are managed by Salt, do not edit",
            )
            self.set_crontab(
                "# Lines below here are managed by Salt, do not edit\n* * * * * foo"
            )
            cron.absent(name="bar", identifier="1")
            self.assertEqual(
                self.get_crontab(),
                "# Lines below here are managed by Salt, do not edit\n* * * * * foo",
            )
            # old behavior, do not remove with identifier set and
            # even if command match !
            self.set_crontab(
                "# Lines below here are managed by Salt, do not edit\n* * * * * foo"
            )
            cron.absent(name="foo", identifier="1")
            self.assertEqual(
                self.get_crontab(),
                "# Lines below here are managed by Salt, do not edit",
            )
            # old behavior, remove if no identifier and command match
            self.set_crontab(
                "# Lines below here are managed by Salt, do not edit\n* * * * * foo"
            )
            cron.absent(name="foo")
            self.assertEqual(
                self.get_crontab(),
                "# Lines below here are managed by Salt, do not edit",
            )

    def test_multiline_comments_are_updated(self):
        self.set_crontab(
            "# Lines below here are managed by Salt, do not edit\n"
            "# First crontab - single line comment SALT_CRON_IDENTIFIER:1\n"
            "* 1 * * * foo"
        )
        cron.present(
            name="foo",
            hour="1",
            comment="First crontab\nfirst multi-line comment\n",
            identifier="1",
            user="root",
        )
        cron.present(
            name="foo",
            hour="1",
            comment="First crontab\nsecond multi-line comment\n",
            identifier="1",
            user="root",
        )
        cron.present(
            name="foo",
            hour="1",
            comment="Second crontab\nmulti-line comment\n",
            identifier="2",
            user="root",
        )
        self.assertEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# First crontab\n"
            "# second multi-line comment\n"
            "#  SALT_CRON_IDENTIFIER:1\n"
            "* 1 * * * foo\n"
            "# Second crontab\n"
            "# multi-line comment\n"
            "#  SALT_CRON_IDENTIFIER:2\n"
            "* 1 * * * foo",
        )

    def test_existing_unmanaged_jobs_are_made_managed(self):
        self.set_crontab(
            "# Lines below here are managed by Salt, do not edit\n0 2 * * * foo"
        )
        ret = cron._check_cron("root", "foo", hour="2", minute="0")
        self.assertEqual(ret, "present")
        ret = cron.present("foo", "root", minute="0", hour="2")
        self.assertEqual(ret["changes"], {"root": "foo"})
        self.assertEqual(ret["comment"], "Cron foo updated")
        self.assertEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:foo\n"
            "0 2 * * * foo",
        )
        ret = cron.present("foo", "root", minute="0", hour="2")
        self.assertEqual(ret["changes"], {})
        self.assertEqual(ret["comment"], "Cron foo already present")

    def test_existing_noid_jobs_are_updated_with_identifier(self):
        self.set_crontab(
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:NO ID SET\n"
            "1 * * * * foo"
        )
        ret = cron._check_cron("root", "foo", minute=1)
        self.assertEqual(ret, "present")
        ret = cron.present("foo", "root", minute=1)
        self.assertEqual(ret["changes"], {"root": "foo"})
        self.assertEqual(ret["comment"], "Cron foo updated")
        self.assertEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:foo\n"
            "1 * * * * foo",
        )

    def test_existing_duplicate_unmanaged_jobs_are_merged_and_given_id(self):
        self.set_crontab(
            "# Lines below here are managed by Salt, do not edit\n"
            "0 2 * * * foo\n"
            "0 2 * * * foo"
        )
        ret = cron._check_cron("root", "foo", hour="2", minute="0")
        self.assertEqual(ret, "present")
        ret = cron.present("foo", "root", minute="0", hour="2")
        self.assertEqual(ret["changes"], {"root": "foo"})
        self.assertEqual(ret["comment"], "Cron foo updated")
        self.assertEqual(
            self.get_crontab(),
            "# Lines below here are managed by Salt, do not edit\n"
            "# SALT_CRON_IDENTIFIER:foo\n"
            "0 2 * * * foo",
        )
        ret = cron.present("foo", "root", minute="0", hour="2")
        self.assertEqual(ret["changes"], {})
        self.assertEqual(ret["comment"], "Cron foo already present")

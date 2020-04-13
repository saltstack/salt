# -*- coding: utf-8 -*-
"""
    :codeauthor: Andrew Colin Kissa <andrew@topdog.za.net>
"""
from __future__ import absolute_import, print_function, unicode_literals

import salt.states.postgres_language as postgres_language
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PostgresLanguageTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.postgres_language
    """

    def setup_loader_modules(self):
        return {postgres_language: {}}

    def setUp(self):
        """
        Setup data for the tests
        """
        self.name = "plpgsql"
        self.ret = {"name": self.name, "changes": {}, "result": False, "comment": ""}
        self.mock_true = MagicMock(return_value=True)
        self.mock_false = MagicMock(return_value=False)
        self.mock_empty_language_list = MagicMock(return_value={})
        self.mock_language_list = MagicMock(return_value={"plpgsql": self.name})

    def tearDown(self):
        del self.ret
        del self.mock_true
        del self.mock_false
        del self.mock_language_list
        del self.mock_empty_language_list

    def test_present_existing(self):
        """
        Test present, language is already present in database
        """
        with patch.dict(
            postgres_language.__salt__,
            {"postgres.language_list": self.mock_language_list},
        ):
            comt = "Language {0} is already installed".format(self.name)
            self.ret.update({"comment": comt, "result": True})
            self.assertDictEqual(
                postgres_language.present(self.name, "testdb"), self.ret
            )

    def test_present_non_existing_pass(self):
        """
        Test present, language not present in database - pass
        """
        with patch.dict(
            postgres_language.__salt__,
            {
                "postgres.language_list": self.mock_empty_language_list,
                "postgres.language_create": self.mock_true,
            },
        ):
            with patch.dict(postgres_language.__opts__, {"test": True}):
                comt = "Language {0} is set to be installed".format(self.name)
                self.ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    postgres_language.present(self.name, "testdb"), self.ret
                )

            with patch.dict(postgres_language.__opts__, {"test": False}):
                comt = "Language {0} has been installed".format(self.name)
                self.ret.update(
                    {"comment": comt, "result": True, "changes": {"plpgsql": "Present"}}
                )
                self.assertDictEqual(
                    postgres_language.present(self.name, "testdb"), self.ret
                )

    def test_present_non_existing_fail(self):
        """
        Test present, language not present in database - fail
        """
        with patch.dict(
            postgres_language.__salt__,
            {
                "postgres.language_list": self.mock_empty_language_list,
                "postgres.language_create": self.mock_false,
            },
        ):
            with patch.dict(postgres_language.__opts__, {"test": True}):
                comt = "Language {0} is set to be installed".format(self.name)
                self.ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    postgres_language.present(self.name, "testdb"), self.ret
                )

            with patch.dict(postgres_language.__opts__, {"test": False}):
                comt = "Failed to install language {0}".format(self.name)
                self.ret.update({"comment": comt, "result": False})
                self.assertDictEqual(
                    postgres_language.present(self.name, "testdb"), self.ret
                )

    def test_absent_existing(self):
        """
        Test absent, language present in database
        """
        with patch.dict(
            postgres_language.__salt__,
            {
                "postgres.language_exists": self.mock_true,
                "postgres.language_remove": self.mock_true,
            },
        ):
            with patch.dict(postgres_language.__opts__, {"test": True}):
                comt = "Language {0} is set to be removed".format(self.name)
                self.ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    postgres_language.absent(self.name, "testdb"), self.ret
                )

            with patch.dict(postgres_language.__opts__, {"test": False}):
                comt = "Language {0} has been removed".format(self.name)
                self.ret.update(
                    {"comment": comt, "result": True, "changes": {"plpgsql": "Absent"}}
                )
                self.assertDictEqual(
                    postgres_language.absent(self.name, "testdb"), self.ret
                )

    def test_absent_non_existing(self):
        """
        Test absent, language not present in database
        """
        with patch.dict(
            postgres_language.__salt__, {"postgres.language_exists": self.mock_false}
        ):
            with patch.dict(postgres_language.__opts__, {"test": True}):
                comt = "Language {0} is not present so " "it cannot be removed".format(
                    self.name
                )
                self.ret.update({"comment": comt, "result": True})
                self.assertDictEqual(
                    postgres_language.absent(self.name, "testdb"), self.ret
                )

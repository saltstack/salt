# -*- coding: utf-8 -*-
"""
    :codeauthor: Lukas Raska <lukas@raska.me>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.utils.dictdiffer as dictdiffer
from salt.exceptions import CommandExecutionError
from salt.states import elasticsearch

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ElasticsearchTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.elasticsearch
    """

    def setup_loader_modules(self):
        return {
            elasticsearch: {
                "__opts__": {"test": False},
                "__utils__": {"dictdiffer.deep_diff": dictdiffer.deep_diff},
            }
        }

    # 'index_absent' function tests: 1

    def test_index_absent(self):
        """
        Test to manage a elasticsearch index.
        """
        name = "foo"

        ret = {
            "name": name,
            "result": True,
            "comment": "Index foo is already absent",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                None,
                {name: {"test": "key"}},
                {name: {}},
                {name: {"test": "key"}},
                CommandExecutionError,
                {name: {"test": "key"}},
            ]
        )
        mock_delete = MagicMock(side_effect=[True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.index_get": mock_get,
                "elasticsearch.index_delete": mock_delete,
            },
        ):
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

            ret.update(
                {
                    "comment": "Successfully removed index foo",
                    "changes": {"old": {"test": "key"}},
                }
            )
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

            ret.update(
                {
                    "comment": "Failed to remove index foo for unknown reasons",
                    "result": False,
                    "changes": {},
                }
            )
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Index foo will be removed",
                        "result": None,
                        "changes": {"old": {"test": "key"}},
                    }
                )
                self.assertDictEqual(elasticsearch.index_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

    # 'index_present' function tests: 1

    def test_index_present(self):
        """
        Test to manage a elasticsearch index.
        """
        name = "foo"

        ret = {
            "name": name,
            "result": True,
            "comment": "Index foo is already present",
            "changes": {},
        }

        mock_exists = MagicMock(
            side_effect=[True, False, False, False, CommandExecutionError, False, False]
        )
        mock_get = MagicMock(
            side_effect=[{name: {"test": "key"}}, CommandExecutionError]
        )
        mock_create = MagicMock(side_effect=[True, False, CommandExecutionError, True])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.index_get": mock_get,
                "elasticsearch.index_exists": mock_exists,
                "elasticsearch.index_create": mock_create,
            },
        ):
            self.assertDictEqual(elasticsearch.index_present(name), ret)

            ret.update(
                {
                    "comment": "Successfully created index foo",
                    "changes": {"new": {"test": "key"}},
                }
            )
            self.assertDictEqual(elasticsearch.index_present(name), ret)

            ret.update(
                {
                    "comment": "Cannot create index foo, False",
                    "result": False,
                    "changes": {},
                }
            )
            self.assertDictEqual(elasticsearch.index_present(name), ret)

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Index foo does not exist and will be created",
                        "result": None,
                        "changes": {"new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.index_present(name, {"test2": "key"}), ret
                )

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_absent(name), ret)

    # 'alias_absent' function tests: 1

    def test_alias_absent(self):
        """
        Test to manage a elasticsearch alias.
        """
        name = "foo"
        index = "bar"

        alias = {index: {"aliases": {name: {"test": "key"}}}}

        ret = {
            "name": name,
            "result": True,
            "comment": "Alias foo for index bar is already absent",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                None,
                {"foo2": {}},
                alias,
                alias,
                alias,
                CommandExecutionError,
                alias,
            ]
        )
        mock_delete = MagicMock(side_effect=[True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.alias_get": mock_get,
                "elasticsearch.alias_delete": mock_delete,
            },
        ):
            self.assertDictEqual(elasticsearch.alias_absent(name, index), ret)
            self.assertDictEqual(elasticsearch.alias_absent(name, index), ret)

            ret.update(
                {
                    "comment": "Successfully removed alias foo for index bar",
                    "changes": {"old": {"test": "key"}},
                }
            )
            self.assertDictEqual(elasticsearch.alias_absent(name, index), ret)

            ret.update(
                {
                    "comment": "Failed to remove alias foo for index bar for unknown reasons",
                    "result": False,
                    "changes": {},
                }
            )
            self.assertDictEqual(elasticsearch.alias_absent(name, index), ret)

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Alias foo for index bar will be removed",
                        "result": None,
                        "changes": {"old": {"test": "key"}},
                    }
                )
                self.assertDictEqual(elasticsearch.alias_absent(name, index), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.alias_absent(name, index), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.alias_absent(name, index), ret)

    # 'alias_present' function tests: 1

    def test_alias_present(self):
        """
        Test to manage a elasticsearch alias.
        """
        name = "foo"
        index = "bar"

        alias = {index: {"aliases": {name: {"test": "key"}}}}

        ret = {
            "name": name,
            "result": True,
            "comment": "Alias foo for index bar is already present",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                alias,
                alias,
                None,
                None,
                None,
                alias,
                CommandExecutionError,
                None,
            ]
        )
        mock_create = MagicMock(side_effect=[True, True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.alias_get": mock_get,
                "elasticsearch.alias_create": mock_create,
            },
        ):
            self.assertDictEqual(
                elasticsearch.alias_present(name, index, {"test": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Successfully replaced alias foo for index bar",
                    "changes": {"old": {"test": "key"}, "new": {"test2": "key"}},
                }
            )
            self.assertDictEqual(
                elasticsearch.alias_present(name, index, {"test2": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Successfully created alias foo for index bar",
                    "changes": {"new": {"test2": "key"}},
                }
            )
            self.assertDictEqual(
                elasticsearch.alias_present(name, index, {"test2": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Cannot create alias foo for index bar, False",
                    "result": False,
                }
            )
            self.assertDictEqual(
                elasticsearch.alias_present(name, index, {"test2": "key"}), ret
            )

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Alias foo for index bar does not exist and will be created",
                        "result": None,
                        "changes": {"new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.alias_present(name, index, {"test2": "key"}), ret
                )

                ret.update(
                    {
                        "comment": "Alias foo for index bar exists with wrong configuration and will be overridden",
                        "result": None,
                        "changes": {"old": {"test": "key"}, "new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.alias_present(name, index, {"test2": "key"}), ret
                )

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.alias_present(name, index), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.alias_present(name, index), ret)

    # 'index_template_absent' function tests: 1

    def test_index_template_absent(self):
        """
        Test to manage a elasticsearch index template.
        """
        name = "foo"

        index_template = {name: {"test": "key"}}

        ret = {
            "name": name,
            "result": True,
            "comment": "Index template foo is already absent",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                None,
                {"bar": {}},
                index_template,
                index_template,
                index_template,
                CommandExecutionError,
                index_template,
            ]
        )
        mock_delete = MagicMock(side_effect=[True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.index_template_get": mock_get,
                "elasticsearch.index_template_delete": mock_delete,
            },
        ):
            self.assertDictEqual(elasticsearch.index_template_absent(name), ret)
            self.assertDictEqual(elasticsearch.index_template_absent(name), ret)

            ret.update(
                {
                    "comment": "Successfully removed index template foo",
                    "changes": {"old": {"test": "key"}},
                }
            )
            self.assertDictEqual(elasticsearch.index_template_absent(name), ret)

            ret.update(
                {
                    "comment": "Failed to remove index template foo for unknown reasons",
                    "result": False,
                    "changes": {},
                }
            )
            self.assertDictEqual(elasticsearch.index_template_absent(name), ret)

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Index template foo will be removed",
                        "result": None,
                        "changes": {"old": {"test": "key"}},
                    }
                )
                self.assertDictEqual(elasticsearch.index_template_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_template_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_template_absent(name), ret)

    # 'index_template_present' function tests: 1

    def test_index_template_present(self):
        """
        Test to manage a elasticsearch index template.
        """
        name = "foo"

        index_template = {name: {"test": "key"}}

        ret = {
            "name": name,
            "result": True,
            "comment": "Index template foo is already present",
            "changes": {},
        }

        mock_exists = MagicMock(
            side_effect=[True, False, False, False, CommandExecutionError, False, False]
        )
        mock_create = MagicMock(side_effect=[True, False, CommandExecutionError, True])
        mock_get = MagicMock(side_effect=[index_template, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.index_template_get": mock_get,
                "elasticsearch.index_template_create": mock_create,
                "elasticsearch.index_template_exists": mock_exists,
            },
        ):
            self.assertDictEqual(
                elasticsearch.index_template_present(name, {"test2": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Successfully created index template foo",
                    "changes": {"new": {"test": "key"}},
                }
            )
            self.assertDictEqual(
                elasticsearch.index_template_present(name, {"test2": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Cannot create index template foo, False",
                    "result": False,
                    "changes": {},
                }
            )
            self.assertDictEqual(
                elasticsearch.index_template_present(name, {"test2": "key"}), ret
            )

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Index template foo does not exist and will be created",
                        "result": None,
                        "changes": {"new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.index_template_present(name, {"test2": "key"}), ret
                )

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_template_present(name, {}), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_template_present(name, {}), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.index_template_present(name, {}), ret)

    def test_index_template_present_check_definition(self):
        """
        Test to manage a elasticsearch index template.
        with check_definition set
        """
        name = "foo"

        index_template = {
            name: {"test2": "key", "aliases": {}, "mappings": {}, "settings": {}}
        }

        expected = {
            "name": name,
            "result": True,
            "comment": "Index template foo is already present and up to date",
            "changes": {},
        }

        mock_exists = MagicMock(side_effect=[True])
        mock_create = MagicMock(side_effect=[True])
        mock_get = MagicMock(side_effect=[index_template])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.index_template_get": mock_get,
                "elasticsearch.index_template_create": mock_create,
                "elasticsearch.index_template_exists": mock_exists,
            },
        ):

            ret = elasticsearch.index_template_present(
                name, {"test2": "key", "aliases": {}}, check_definition=True
            )
            self.assertDictEqual(expected, ret)

    def test_index_template_present_check_definition_alias_not_empty(self):
        """
        Test to manage a elasticsearch index template.
        with check_definition set and alias is not empty
        """
        name = "foo"

        index_template = {
            name: {"test2": "key", "aliases": {}, "mappings": {}, "settings": {}}
        }

        expected = {
            "name": name,
            "result": True,
            "comment": "Successfully updated index template foo",
            "changes": {"new": {"aliases": {"alias1": {}}}, "old": {"aliases": {}}},
        }

        mock_exists = MagicMock(side_effect=[True])
        mock_create = MagicMock(side_effect=[True])
        mock_get = MagicMock(side_effect=[index_template])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.index_template_get": mock_get,
                "elasticsearch.index_template_create": mock_create,
                "elasticsearch.index_template_exists": mock_exists,
            },
        ):

            ret = elasticsearch.index_template_present(
                name, {"test2": "key", "aliases": {"alias1": {}}}, check_definition=True
            )
            self.assertDictEqual(expected, ret)

    # 'pipeline_absent' function tests: 1

    def test_pipeline_absent(self):
        """
        Test to manage a elasticsearch pipeline.
        """
        name = "foo"

        pipeline = {name: {"test": "key"}}

        ret = {
            "name": name,
            "result": True,
            "comment": "Pipeline foo is already absent",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                None,
                {"foo2": {}},
                pipeline,
                pipeline,
                pipeline,
                CommandExecutionError,
                pipeline,
            ]
        )
        mock_delete = MagicMock(side_effect=[True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.pipeline_get": mock_get,
                "elasticsearch.pipeline_delete": mock_delete,
            },
        ):
            self.assertDictEqual(elasticsearch.pipeline_absent(name), ret)
            self.assertDictEqual(elasticsearch.pipeline_absent(name), ret)

            ret.update(
                {
                    "comment": "Successfully removed pipeline foo",
                    "changes": {"old": {"test": "key"}},
                }
            )
            self.assertDictEqual(elasticsearch.pipeline_absent(name), ret)

            ret.update(
                {
                    "comment": "Failed to remove pipeline foo for unknown reasons",
                    "result": False,
                    "changes": {},
                }
            )
            self.assertDictEqual(elasticsearch.pipeline_absent(name), ret)

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Pipeline foo will be removed",
                        "result": None,
                        "changes": {"old": {"test": "key"}},
                    }
                )
                self.assertDictEqual(elasticsearch.pipeline_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.pipeline_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.pipeline_absent(name), ret)

    # 'pipeline_present' function tests: 1

    def test_pipeline_present(self):
        """
        Test to manage a elasticsearch pipeline.
        """
        name = "foo"

        pipeline = {name: {"test": "key"}}

        ret = {
            "name": name,
            "result": True,
            "comment": "Pipeline foo is already present",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                pipeline,
                pipeline,
                None,
                None,
                None,
                pipeline,
                CommandExecutionError,
                None,
            ]
        )
        mock_create = MagicMock(side_effect=[True, True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.pipeline_get": mock_get,
                "elasticsearch.pipeline_create": mock_create,
            },
        ):
            self.assertDictEqual(
                elasticsearch.pipeline_present(name, {"test": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Successfully replaced pipeline foo",
                    "changes": {"old": {"test": "key"}, "new": {"test2": "key"}},
                }
            )
            self.assertDictEqual(
                elasticsearch.pipeline_present(name, {"test2": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Successfully created pipeline foo",
                    "changes": {"new": {"test2": "key"}},
                }
            )
            self.assertDictEqual(
                elasticsearch.pipeline_present(name, {"test2": "key"}), ret
            )

            ret.update(
                {"comment": "Cannot create pipeline foo, False", "result": False}
            )
            self.assertDictEqual(
                elasticsearch.pipeline_present(name, {"test2": "key"}), ret
            )

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Pipeline foo does not exist and will be created",
                        "result": None,
                        "changes": {"new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.pipeline_present(name, {"test2": "key"}), ret
                )

                ret.update(
                    {
                        "comment": "Pipeline foo exists with wrong configuration and will be overridden",
                        "result": None,
                        "changes": {"old": {"test": "key"}, "new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.pipeline_present(name, {"test2": "key"}), ret
                )

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.pipeline_present(name, {}), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.pipeline_present(name, {}), ret)

    # 'search_template_absent' function tests: 1

    def test_search_template_absent(self):
        """
        Test to manage a elasticsearch search template.
        """
        name = "foo"

        template = {"template": '{"test": "key"}'}

        ret = {
            "name": name,
            "result": True,
            "comment": "Search template foo is already absent",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                None,
                template,
                template,
                template,
                CommandExecutionError,
                template,
            ]
        )
        mock_delete = MagicMock(side_effect=[True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.search_template_get": mock_get,
                "elasticsearch.search_template_delete": mock_delete,
            },
        ):
            self.assertDictEqual(elasticsearch.search_template_absent(name), ret)

            ret.update(
                {
                    "comment": "Successfully removed search template foo",
                    "changes": {"old": {"test": "key"}},
                }
            )
            self.assertDictEqual(elasticsearch.search_template_absent(name), ret)

            ret.update(
                {
                    "comment": "Failed to remove search template foo for unknown reasons",
                    "result": False,
                    "changes": {},
                }
            )
            self.assertDictEqual(elasticsearch.search_template_absent(name), ret)

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Search template foo will be removed",
                        "result": None,
                        "changes": {"old": {"test": "key"}},
                    }
                )
                self.assertDictEqual(elasticsearch.search_template_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.search_template_absent(name), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.search_template_absent(name), ret)

    # 'pipeline_present' function tests: 1

    def test_search_template_present(self):
        """
        Test to manage a elasticsearch search template.
        """
        name = "foo"

        template = {"template": '{"test": "key"}'}

        ret = {
            "name": name,
            "result": True,
            "comment": "Search template foo is already present",
            "changes": {},
        }

        mock_get = MagicMock(
            side_effect=[
                template,
                template,
                None,
                None,
                None,
                template,
                CommandExecutionError,
                None,
            ]
        )
        mock_create = MagicMock(side_effect=[True, True, False, CommandExecutionError])

        with patch.dict(
            elasticsearch.__salt__,
            {
                "elasticsearch.search_template_get": mock_get,
                "elasticsearch.search_template_create": mock_create,
            },
        ):
            self.assertDictEqual(
                elasticsearch.search_template_present(name, {"test": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Successfully replaced search template foo",
                    "changes": {"old": {"test": "key"}, "new": {"test2": "key"}},
                }
            )
            self.assertDictEqual(
                elasticsearch.search_template_present(name, {"test2": "key"}), ret
            )

            ret.update(
                {
                    "comment": "Successfully created search template foo",
                    "changes": {"new": {"test2": "key"}},
                }
            )
            self.assertDictEqual(
                elasticsearch.search_template_present(name, {"test2": "key"}), ret
            )

            ret.update(
                {"comment": "Cannot create search template foo, False", "result": False}
            )
            self.assertDictEqual(
                elasticsearch.search_template_present(name, {"test2": "key"}), ret
            )

            with patch.dict(elasticsearch.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "Search template foo does not exist and will be created",
                        "result": None,
                        "changes": {"new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.search_template_present(name, {"test2": "key"}), ret
                )

                ret.update(
                    {
                        "comment": "Search template foo exists with wrong configuration and will be overridden",
                        "result": None,
                        "changes": {"old": {"test": "key"}, "new": {"test2": "key"}},
                    }
                )
                self.assertDictEqual(
                    elasticsearch.search_template_present(name, {"test2": "key"}), ret
                )

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.search_template_present(name, {}), ret)

            ret.update({"comment": "", "result": False, "changes": {}})
            self.assertDictEqual(elasticsearch.search_template_present(name, {}), ret)

# -*- coding: utf-8 -*-
"""
    :codeauthor: Lukas Raska <lukas@raska.me>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import Salt Libs
from salt.modules import elasticsearch
from tests.support.mock import MagicMock, patch

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

# Import elasticsearch exceptions
NO_ELASTIC = False
try:
    from elasticsearch import TransportError, NotFoundError
except Exception:  # pylint: disable=broad-except
    NO_ELASTIC = True


@skipIf(NO_ELASTIC, "Install elasticsearch-py before running Elasticsearch unit tests.")
class ElasticsearchTestCase(TestCase):
    """
    Test cases for salt.modules.elasticsearch
    """

    @staticmethod
    def es_return_true(hosts=None, profile=None):
        return True

    @staticmethod
    def es_raise_command_execution_error(hosts=None, profile=None):
        raise CommandExecutionError("custom message")

    # 'ping' function tests: 2

    def test_ping(self):
        """
        Test if ping succeeds
        """
        with patch.object(elasticsearch, "_get_instance", self.es_return_true):
            self.assertTrue(elasticsearch.ping())

    def test_ping_failure(self):
        """
        Test if ping fails
        """
        with patch.object(
            elasticsearch, "_get_instance", self.es_raise_command_execution_error
        ):
            self.assertFalse(elasticsearch.ping())

    # 'info' function tests: 2

    def test_info(self):
        """
        Test if status fetch succeeds
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def info(self):
                """
                Mock of info method
                """
                return [{"test": "key"}]

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertListEqual(elasticsearch.info(), [{"test": "key"}])

    def test_info_failure(self):
        """
        Test if status fetch fails with CommandExecutionError
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def info(self):
                """
                Mock of info method
                """
                raise TransportError("custom error", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(CommandExecutionError, elasticsearch.info)

    # 'node_info' function tests: 2

    def test_node_info(self):
        """
        Test if node status fetch succeeds
        """

        class MockElasticNodes(object):
            """
            Mock of Elasticsearch NodesClient
            """

            def info(self, node_id=None, flat_settings=None):
                """
                Mock of info method
                """
                return [{"test": "key"}]

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            nodes = MockElasticNodes()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertListEqual(elasticsearch.node_info(), [{"test": "key"}])

    def test_node_info_failure(self):
        """
        Test if node status fetch fails with CommandExecutionError
        """

        class MockElasticNodes(object):
            """
            Mock of Elasticsearch NodesClient
            """

            def info(self, node_id=None, flat_settings=None):
                """
                Mock of info method
                """
                raise TransportError("custom error", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            nodes = MockElasticNodes()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(CommandExecutionError, elasticsearch.node_info)

    # 'cluster_health' function tests: 2

    def test_cluster_health(self):
        """
        Test if cluster status health fetch succeeds
        """

        class MockElasticCluster(object):
            """
            Mock of Elasticsearch ClusterClient
            """

            def health(self, index=None, level=None, local=None):
                """
                Mock of health method
                """
                return [{"test": "key"}]

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            cluster = MockElasticCluster()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertListEqual(elasticsearch.cluster_health(), [{"test": "key"}])

    def test_cluster_health_failure(self):
        """
        Test if cluster status health fetch fails with CommandExecutionError
        """

        class MockElasticCluster(object):
            """
            Mock of Elasticsearch ClusterClient
            """

            def health(self, index=None, level=None, local=None):
                """
                Mock of health method
                """
                raise TransportError("custom error", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            cluster = MockElasticCluster()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(CommandExecutionError, elasticsearch.cluster_health)

    # 'cluster_stats' function tests: 2

    def test_cluster_stats(self):
        """
        Test if cluster stats fetch succeeds
        """

        class MockElasticCluster(object):
            """
            Mock of Elasticsearch ClusterClient
            """

            def stats(self, node_id=None):
                """
                Mock of health method
                """
                return [{"test": "key"}]

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            cluster = MockElasticCluster()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertListEqual(elasticsearch.cluster_stats(), [{"test": "key"}])

    def test_cluster_stats_failure(self):
        """
        Test if cluster stats fetch fails with CommandExecutionError
        """

        class MockElasticCluster(object):
            """
            Mock of Elasticsearch ClusterClient
            """

            def stats(self, node_id=None):
                """
                Mock of health method
                """
                raise TransportError("custom error", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            cluster = MockElasticCluster()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(CommandExecutionError, elasticsearch.cluster_stats)

    # 'alias_create' function tests: 3

    def test_alias_create(self):
        """
        Test if alias is created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_alias(self, index=None, name=None, body=None):
                """
                Mock of put_alias method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.alias_create("foo", "bar", body="baz"))

    def test_alias_create_unack(self):
        """
        Test if alias creation is not acked
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_alias(self, index=None, name=None, body=None):
                """
                Mock of put_alias method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.alias_create("foo", "bar", body="baz"))

    def test_alias_create_failure(self):
        """
        Test if alias creation fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_alias(self, index=None, name=None, body=None):
                """
                Mock of put_alias method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError,
                elasticsearch.alias_create,
                "foo",
                "bar",
                body="baz",
            )

    # 'alias_delete' function tests: 3

    def test_alias_delete(self):
        """
        Test if alias is deleted
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_alias(self, index=None, name=None):
                """
                Mock of delete_alias method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.alias_delete("foo", "bar"))

    def test_alias_delete_unack(self):
        """
        Test if alias deletion is not acked
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_alias(self, index=None, name=None):
                """
                Mock of delete_alias method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.alias_delete("foo", "bar"))

    def test_alias_delete_failure(self):
        """
        Test if alias deletion fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_alias(self, index=None, name=None):
                """
                Mock of delete_alias method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.alias_delete, "foo", "bar"
            )

    # 'alias_exists' function tests: 3

    def test_alias_exists(self):
        """
        Test if alias exists
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists_alias(self, index=None, name=None):
                """
                Mock of exists_alias method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.alias_exists("foo", "bar"))

    def test_alias_exists_not(self):
        """
        Test if alias doesn't exist
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists_alias(self, index=None, name=None):
                """
                Mock of exists_alias method
                """
                raise NotFoundError

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.alias_exists("foo", "bar"))

    def test_alias_exists_failure(self):
        """
        Test if alias status obtain fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists_alias(self, index=None, name=None):
                """
                Mock of exists_alias method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.alias_exists, "foo", "bar"
            )

    # 'alias_get' function tests: 3

    def test_alias_get(self):
        """
        Test if alias can be obtained
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_alias(self, index=None, name=None):
                """
                Mock of get_alias method
                """
                return {"test": "key"}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(elasticsearch.alias_get("foo", "bar"), {"test": "key"})

    def test_alias_get_not(self):
        """
        Test if alias doesn't exist
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_alias(self, index=None, name=None):
                """
                Mock of get_alias method
                """
                raise NotFoundError

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertIs(elasticsearch.alias_get("foo", "bar"), None)

    def test_alias_get_failure(self):
        """
        Test if alias obtain fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_alias(self, index=None, name=None):
                """
                Mock of get_alias method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.alias_get, "foo", "bar"
            )

    # 'document_create' function tests: 2

    def test_document_create(self):
        """
        Test if document can be created
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def index(self, index=None, doc_type=None, body=None, id=None):
                """
                Mock of index method
                """
                return {"test": "key"}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(
                elasticsearch.document_create("foo", "bar"), {"test": "key"}
            )

    def test_document_create_failure(self):
        """
        Test if document creation fails with CommandExecutionError
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def index(self, index=None, doc_type=None, body=None, id=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.document_create, "foo", "bar"
            )

    # 'document_delete' function tests: 2

    def test_document_delete(self):
        """
        Test if document can be deleted
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def delete(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                return {"test": "key"}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(
                elasticsearch.document_delete("foo", "bar", "baz"), {"test": "key"}
            )

    def test_document_delete_failure(self):
        """
        Test if document deletion fails with CommandExecutionError
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def delete(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError,
                elasticsearch.document_delete,
                "foo",
                "bar",
                "baz",
            )

    # 'document_exists' function tests: 3

    def test_document_exists(self):
        """
        Test if document status can be obtained
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def exists(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                return True

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.document_exists("foo", "bar"))

    def test_document_exists_not(self):
        """
        Test if document doesn't exist
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def exists(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                return False

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.document_exists("foo", "bar"))

    def test_document_exists_failure(self):
        """
        Test if document exist state fails with CommandExecutionError
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def exists(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.document_exists, "foo", "bar"
            )

    # 'document_get' function tests: 3

    def test_document_get(self):
        """
        Test if document exists
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def get(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                return {"test": "key"}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(
                elasticsearch.document_get("foo", "bar"), {"test": "key"}
            )

    def test_document_get_not(self):
        """
        Test if document doesn't exit
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def get(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                raise NotFoundError

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertIs(elasticsearch.document_get("foo", "bar"), None)

    def test_document_get_failure(self):
        """
        Test if document obtain fails with CommandExecutionError
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def get(self, index=None, doc_type=None, id=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.document_get, "foo", "bar"
            )

    # 'index_create' function tests: 5

    def test_index_create(self):
        """
        Test if index can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def create(self, index=None, body=None):
                """
                Mock of index method
                """
                return {"acknowledged": True, "shards_acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_create("foo", "bar"))

    def test_index_create_no_shards(self):
        """
        Test if index is created and no shards info is returned
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def create(self, index=None, body=None):
                """
                Mock of index method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_create("foo", "bar"))

    def test_index_create_not_shards(self):
        """
        Test if index is created and shards didn't acked
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def create(self, index=None, body=None):
                """
                Mock of index method
                """
                return {"acknowledged": True, "shards_acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_create("foo", "bar"))

    def test_index_create_not(self):
        """
        Test if index is created and shards didn't acked
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def create(self, index=None, body=None):
                """
                Mock of index method
                """
                return {"acknowledged": False, "shards_acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_create("foo", "bar"))

    def test_index_create_failure(self):
        """
        Test if index creation fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def create(self, index=None, body=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_create, "foo", "bar"
            )

    # 'index_delete' function tests: 3

    def test_index_delete(self):
        """
        Test if index can be deleted
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete(self, index=None):
                """
                Mock of index method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_delete("foo", "bar"))

    def test_index_delete_not(self):
        """
        Test if index is deleted and shards didn't acked
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete(self, index=None):
                """
                Mock of index method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_delete("foo", "bar"))

    def test_index_delete_failure(self):
        """
        Test if index deletion fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete(self, index=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_delete, "foo", "bar"
            )

    # 'index_exists' function tests: 3

    def test_index_exists(self):
        """
        Test if index exists
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists(self, index=None):
                """
                Mock of index method
                """
                return True

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_exists("foo", "bar"))

    def test_index_exists_not(self):
        """
        Test if index doesn't exist
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists(self, index=None):
                """
                Mock of index method
                """
                raise NotFoundError

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_exists("foo", "bar"))

    def test_index_exists_failure(self):
        """
        Test if alias exist state fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists(self, index=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_exists, "foo", "bar"
            )

    def test_index_get_settings(self):
        """
        Test if settings can be obtained from the index
        """

        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.get_settings = MagicMock(return_value={"foo": "key"})
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertDictEqual(
                elasticsearch.index_get_settings("foo", "bar"), {"foo": "key"}
            )

    def test_index_get_settings_not_exists(self):
        """
        Test index_get_settings if index doesn't exist
        """

        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.get_settings = MagicMock()
        fake_es.indices.get_settings.side_effect = NotFoundError("custom error", 123)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertIs(elasticsearch.index_get_settings(index="foo"), None)

    def test_get_settings_failure(self):
        """
        Test if index settings get fails with CommandExecutionError
        """

        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.get_settings = MagicMock()
        fake_es.indices.get_settings.side_effect = TransportError("custom error", 123)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_get_settings, index="foo"
            )

    def test_index_put_settings(self):
        """
        Test if we can put settings for the index
        """

        body = {"settings": {"index": {"number_of_replicas": 2}}}
        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.put_settings = MagicMock(return_value={"acknowledged": True})
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertTrue(elasticsearch.index_put_settings(index="foo", body=body))

    def test_index_put_settings_not_exists(self):
        """
        Test if settings put executed agains non-existinf index
        """

        body = {"settings": {"index": {"number_of_replicas": 2}}}
        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.put_settings = MagicMock()
        fake_es.indices.put_settings.side_effect = NotFoundError("custom error", 123)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertIs(
                elasticsearch.index_put_settings(index="foo", body=body), None
            )

    def test_index_put_settings_failure(self):
        """
        Test if settings put failed with CommandExecutionError
        """

        body = {"settings": {"index": {"number_of_replicas": 2}}}
        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.put_settings = MagicMock()
        fake_es.indices.put_settings.side_effect = TransportError("custom error", 123)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertRaises(
                CommandExecutionError,
                elasticsearch.index_put_settings,
                index="foo",
                body=body,
            )

    # 'index_get' function tests: 3

    def test_index_get(self):
        """
        Test if index can be obtained
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get(self, index=None):
                """
                Mock of index method
                """
                return {"test": "key"}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(elasticsearch.index_get("foo", "bar"), {"test": "key"})

    def test_index_get_not(self):
        """
        Test if index doesn't exist
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get(self, index=None):
                """
                Mock of index method
                """
                raise NotFoundError

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertIs(elasticsearch.index_get("foo", "bar"), None)

    def test_index_get_failure(self):
        """
        Test if index obtain fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get(self, index=None):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_get, "foo", "bar"
            )

    # 'index_open' function tests: 3

    def test_index_open(self):
        """
        Test if index can be opened
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def open(
                self,
                index=None,
                allow_no_indices=None,
                expand_wildcards=None,
                ignore_unavailable=None,
            ):
                """
                Mock of index method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_open("foo", "bar"))

    def test_index_open_not(self):
        """
        Test if index open isn't acked
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def open(
                self,
                index=None,
                allow_no_indices=None,
                expand_wildcards=None,
                ignore_unavailable=None,
            ):
                """
                Mock of index method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_open("foo", "bar"))

    def test_index_open_failure(self):
        """
        Test if alias opening fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def open(
                self,
                index=None,
                allow_no_indices=None,
                expand_wildcards=None,
                ignore_unavailable=None,
            ):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_open, "foo", "bar"
            )

    # 'index_close' function tests: 3

    def test_index_close(self):
        """
        Test if index can be closed
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def close(
                self,
                index=None,
                allow_no_indices=None,
                expand_wildcards=None,
                ignore_unavailable=None,
            ):
                """
                Mock of index method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_close("foo", "bar"))

    def test_index_close_not(self):
        """
        Test if index close isn't acked
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def close(
                self,
                index=None,
                allow_no_indices=None,
                expand_wildcards=None,
                ignore_unavailable=None,
            ):
                """
                Mock of index method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_close("foo", "bar"))

    def test_index_close_failure(self):
        """
        Test if index closing fails with CommandExecutionError
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def close(
                self,
                index=None,
                allow_no_indices=None,
                expand_wildcards=None,
                ignore_unavailable=None,
            ):
                """
                Mock of index method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_close, "foo", "bar"
            )

    # 'mapping_create' function tests: 3

    def test_mapping_create(self):
        """
        Test if mapping can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_mapping(self, index=None, doc_type=None, body=None):
                """
                Mock of put_mapping method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.mapping_create("foo", "bar", "baz"))

    def test_mapping_create_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_mapping(self, index=None, doc_type=None, body=None):
                """
                Mock of put_mapping method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.mapping_create("foo", "bar", "baz"))

    def test_mapping_create_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_mapping(self, index=None, doc_type=None, body=None):
                """
                Mock of put_mapping method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.mapping_create, "foo", "bar", "baz"
            )

    # 'mapping_delete' function tests: 3

    def test_mapping_delete(self):
        """
        Test if mapping can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_mapping(self, index=None, doc_type=None):
                """
                Mock of put_mapping method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.mapping_delete("foo", "bar", "baz"))

    def test_mapping_delete_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_mapping(self, index=None, doc_type=None):
                """
                Mock of put_mapping method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.mapping_delete("foo", "bar", "baz"))

    def test_mapping_delete_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_mapping(self, index=None, doc_type=None):
                """
                Mock of put_mapping method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.mapping_delete, "foo", "bar", "baz"
            )

    # 'mapping_get' function tests: 3

    def test_mapping_get(self):
        """
        Test if mapping can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_mapping(self, index=None, doc_type=None):
                """
                Mock of get_mapping method
                """
                return {"test": "key"}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(
                elasticsearch.mapping_get("foo", "bar", "baz"), {"test": "key"}
            )

    def test_mapping_get_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_mapping(self, index=None, doc_type=None):
                """
                Mock of get_mapping method
                """
                raise NotFoundError

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertIs(elasticsearch.mapping_get("foo", "bar", "baz"), None)

    def test_mapping_get_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_mapping(self, index=None, doc_type=None):
                """
                Mock of get_mapping method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.mapping_get, "foo", "bar", "baz"
            )

    # 'index_template_create' function tests: 3

    def test_index_template_create(self):
        """
        Test if mapping can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_template(self, name=None, body=None):
                """
                Mock of put_template method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_template_create("foo", "bar"))

    def test_index_template_create_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_template(self, name=None, body=None):
                """
                Mock of put_template method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_template_create("foo", "bar"))

    def test_index_template_create_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_template(self, name=None, body=None):
                """
                Mock of put_template method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_template_create, "foo", "bar"
            )

    # 'index_template_delete' function tests: 3

    def test_index_template_delete(self):
        """
        Test if mapping can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_template(self, name=None):
                """
                Mock of delete_template method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_template_delete("foo"))

    def test_index_template_delete_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_template(self, name=None):
                """
                Mock of delete_template method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_template_delete("foo"))

    def test_index_template_delete_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_template(self, name=None):
                """
                Mock of delete_template method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_template_delete, "foo"
            )

    # 'index_template_exists' function tests: 3

    def test_index_template_exists(self):
        """
        Test if mapping can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists_template(self, name=None):
                """
                Mock of exists_template method
                """
                return True

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.index_template_exists("foo"))

    def test_index_template_exists_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists_template(self, name=None):
                """
                Mock of exists_template method
                """
                return False

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.index_template_exists("foo"))

    def test_index_template_exists_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def exists_template(self, name=None):
                """
                Mock of exists_template method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_template_exists, "foo"
            )

    # 'index_template_get' function tests: 3

    def test_index_template_get(self):
        """
        Test if mapping can be created
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_template(self, name=None):
                """
                Mock of get_template method
                """
                return {"test": "key"}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(
                elasticsearch.index_template_get("foo"), {"test": "key"}
            )

    def test_index_template_get_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_template(self, name=None):
                """
                Mock of get_template method
                """
                raise NotFoundError

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertIs(elasticsearch.index_template_get("foo"), None)

    def test_index_template_get_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIndices(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_template(self, name=None):
                """
                Mock of get_template method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            indices = MockElasticIndices()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.index_template_get, "foo"
            )

    # 'pipeline_get' function tests: 4

    def test_pipeline_get(self):
        """
        Test if mapping can be created
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_pipeline(self, id=None):
                """
                Mock of get_pipeline method
                """
                return {"test": "key"}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(elasticsearch.pipeline_get("foo"), {"test": "key"})

    def test_pipeline_get_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_pipeline(self, id=None):
                """
                Mock of get_pipeline method
                """
                raise NotFoundError

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertIs(elasticsearch.pipeline_get("foo"), None)

    def test_pipeline_get_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def get_pipeline(self, id=None):
                """
                Mock of get_pipeline method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(CommandExecutionError, elasticsearch.pipeline_get, "foo")

    def test_pipeline_get_wrong_version(self):
        """
        Test if mapping creation fails with CEE on invalid elasticsearch-py version
        """

        class MockElasticIngest(object):
            pass

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(CommandExecutionError, elasticsearch.pipeline_get, "foo")

    # 'pipeline_delete' function tests: 4

    def test_pipeline_delete(self):
        """
        Test if mapping can be created
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_pipeline(self, id=None):
                """
                Mock of delete_pipeline method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.pipeline_delete("foo"))

    def test_pipeline_delete_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_pipeline(self, id=None):
                """
                Mock of delete_pipeline method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.pipeline_delete("foo"))

    def test_pipeline_delete_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def delete_pipeline(self, id=None):
                """
                Mock of delete_pipeline method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.pipeline_delete, "foo"
            )

    def test_pipeline_delete_wrong_version(self):
        """
        Test if mapping creation fails with CEE on invalid elasticsearch-py version
        """

        class MockElasticIngest(object):
            pass

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.pipeline_delete, "foo"
            )

    # 'pipeline_create' function tests: 4

    def test_pipeline_create(self):
        """
        Test if mapping can be created
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_pipeline(self, id=None, body=None):
                """
                Mock of put_pipeline method
                """
                return {"acknowledged": True}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.pipeline_create("foo", "bar"))

    def test_pipeline_create_not(self):
        """
        Test if mapping creation didn't ack
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_pipeline(self, id=None, body=None):
                """
                Mock of put_pipeline method
                """
                return {"acknowledged": False}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.pipeline_create("foo", "bar"))

    def test_pipeline_create_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def put_pipeline(self, id=None, body=None):
                """
                Mock of put_pipeline method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.pipeline_create, "foo", "bar"
            )

    def test_pipeline_create_wrong_version(self):
        """
        Test if mapping creation fails with CEE on invalid elasticsearch-py version
        """

        class MockElasticIngest(object):
            pass

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.pipeline_create, "foo", "bar"
            )

    # 'pipeline_simulate' function tests: 3

    def test_pipeline_simulate(self):
        """
        Test if mapping can be created
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def simulate(self, id=None, body=None, verbose=None):
                """
                Mock of simulate method
                """
                return {"test": "key"}

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(
                elasticsearch.pipeline_simulate("foo", "bar"), {"test": "key"}
            )

    def test_pipeline_simulate_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElasticIngest(object):
            """
            Mock of Elasticsearch IndicesClient
            """

            def simulate(self, id=None, body=None, verbose=None):
                """
                Mock of simulate method
                """
                raise TransportError("custom message", 123)

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.pipeline_simulate, "foo", "bar"
            )

    def test_pipeline_simulate_wrong_version(self):
        """
        Test if mapping creation fails with CEE on invalid elasticsearch-py version
        """

        class MockElasticIngest(object):
            pass

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            ingest = MockElasticIngest()

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.pipeline_simulate, "foo", "bar"
            )

    # 'search_template_get' function tests: 3

    def test_search_template_get(self):
        """
        Test if mapping can be created
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def get_template(self, id=None):
                """
                Mock of get_template method
                """
                return {"test": "key"}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertDictEqual(
                elasticsearch.search_template_get("foo"), {"test": "key"}
            )

    def test_search_template_get_not(self):
        """
        Test if mapping can be created
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def get_template(self, id=None):
                """
                Mock of get_template method
                """
                raise NotFoundError

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertIs(elasticsearch.search_template_get("foo"), None)

    def test_search_template_get_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def get_template(self, id=None):
                """
                Mock of get_template method
                """
                raise TransportError("custom message", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.search_template_get, "foo"
            )

    # 'search_template_create' function tests: 3

    def test_search_template_create(self):
        """
        Test if mapping can be created
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def put_template(self, id=None, body=None):
                """
                Mock of put_template method
                """
                return {"acknowledged": True}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.search_template_create("foo", "bar"))

    def test_search_template_create_not(self):
        """
        Test if mapping can be created
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def put_template(self, id=None, body=None):
                """
                Mock of put_template method
                """
                return {"acknowledged": False}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.search_template_create("foo", "bar"))

    def test_search_template_create_failure(self):
        """
        Test if mapping creation fails
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def put_template(self, id=None, body=None):
                """
                Mock of put_template method
                """
                raise TransportError("custom message", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError,
                elasticsearch.search_template_create,
                "foo",
                "bar",
            )

    # 'search_template_delete' function tests: 4

    def test_search_template_delete(self):
        """
        Test if mapping can be deleted
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def delete_template(self, id=None):
                """
                Mock of delete_template method
                """
                return {"acknowledged": True}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.search_template_delete("foo"))

    def test_search_template_delete_not(self):
        """
        Test if mapping can be deleted but not acked
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def delete_template(self, id=None):
                """
                Mock of delete_template method
                """
                return {"acknowledged": False}

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertFalse(elasticsearch.search_template_delete("foo"))

    def test_search_template_delete_not_exists(self):
        """
        Test if deleting mapping doesn't exist
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def delete_template(self, id=None):
                """
                Mock of delete_template method
                """
                raise NotFoundError

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertTrue(elasticsearch.search_template_delete("foo"))

    def test_search_template_delete_failure(self):
        """
        Test if mapping deletion fails
        """

        class MockElastic(object):
            """
            Mock of Elasticsearch client
            """

            def delete_template(self, id=None):
                """
                Mock of delete_template method
                """
                raise TransportError("custom message", 123)

        with patch.object(
            elasticsearch, "_get_instance", MagicMock(return_value=MockElastic())
        ):
            self.assertRaises(
                CommandExecutionError, elasticsearch.search_template_delete, "foo"
            )

    # Cluster settings tests below.
    # We're assuming that _get_instance is properly tested
    # These tests are very simple in nature, mostly checking default arguments.
    def test_cluster_get_settings_succeess(self):
        """
        Test if cluster get_settings fetch succeeds
        """

        expected_settings = {"transient": {}, "persistent": {}}
        fake_es = MagicMock()
        fake_es.cluster = MagicMock()
        fake_es.cluster.get_settings = MagicMock(return_value=expected_settings)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            actual_settings = elasticsearch.cluster_get_settings()
            fake_es.cluster.get_settings.assert_called_with(
                flat_settings=False, include_defaults=False
            )
            assert actual_settings == expected_settings

    def test_cluster_get_settings_failure(self):
        """
        Test if cluster get_settings fetch fails with CommandExecutionError
        """

        fake_es = MagicMock()
        fake_es.cluster = MagicMock()
        fake_es.cluster.get_settings = MagicMock()
        fake_es.cluster.get_settings.side_effect = TransportError("custom error", 123)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertRaises(CommandExecutionError, elasticsearch.cluster_get_settings)

    def test_cluster_put_settings_succeess(self):
        """
        Test if cluster put_settings succeeds
        """

        expected_settings = {
            "acknowledged": True,
            "transient": {},
            "persistent": {"indices": {"recovery": {"max_bytes_per_sec": "50mb"}}},
        }
        body = {
            "transient": {},
            "persistent": {"indices.recovery.max_bytes_per_sec": "50mb"},
        }
        fake_es = MagicMock()
        fake_es.cluster = MagicMock()
        fake_es.cluster.put_settings = MagicMock(return_value=expected_settings)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            actual_settings = elasticsearch.cluster_put_settings(body=body)
            fake_es.cluster.put_settings.assert_called_with(
                body=body, flat_settings=False
            )
            assert actual_settings == expected_settings

    def test_cluster_put_settings_failure(self):
        """
        Test if cluster put_settings fails with CommandExecutionError
        """

        body = {
            "transient": {},
            "persistent": {"indices.recovery.max_bytes_per_sec": "50mb"},
        }
        fake_es = MagicMock()
        fake_es.cluster = MagicMock()
        fake_es.cluster.put_settings = MagicMock()
        fake_es.cluster.put_settings.side_effect = TransportError("custom error", 123)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertRaises(
                CommandExecutionError, elasticsearch.cluster_put_settings, body=body
            )

    def test_cluster_put_settings_nobody(self):
        """
        Test if cluster put_settings fails with SaltInvocationError
        """

        self.assertRaises(SaltInvocationError, elasticsearch.cluster_put_settings)

    # flush_synced tests below.
    # We're assuming that _get_instance is properly tested
    # These tests are very simple in nature, mostly checking default arguments.
    def test_flush_synced_succeess(self):
        """
        Test if flush_synced succeeds
        """

        expected_return = {"_shards": {"failed": 0, "successful": 0, "total": 0}}
        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.flush_synced = MagicMock(return_value=expected_return)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            output = elasticsearch.flush_synced(
                index="_all",
                ignore_unavailable=True,
                allow_no_indices=True,
                expand_wildcards="all",
            )
            fake_es.indices.flush_synced.assert_called_with(
                {
                    "index": "_all",
                    "ignore_unavailable": True,
                    "allow_no_indices": True,
                    "expand_wildcards": "all",
                }
            )
            assert output == expected_return

    def test_flush_synced_failure(self):
        """
        Test if flush_synced fails with CommandExecutionError
        """

        fake_es = MagicMock()
        fake_es.indices = MagicMock()
        fake_es.indices.flush_synced = MagicMock()
        fake_es.indices.flush_synced.side_effect = TransportError("custom error", 123)
        fake_instance = MagicMock(return_value=fake_es)

        with patch.object(elasticsearch, "_get_instance", fake_instance):
            self.assertRaises(CommandExecutionError, elasticsearch.flush_synced)

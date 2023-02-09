"""
Test the elasticsearch module
"""
import pytest

import salt.modules.elasticsearch as elasticsearch_mod
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {elasticsearch_mod: {}}


WRONG_VERSION = False
try:
    import elasticsearch

    if elasticsearch.__version__[0] == 8:
        WRONG_VERSION = True
except ImportError:
    pass

if WRONG_VERSION:
    pytestmark = pytest.mark.skip("Skipping elasticsearch tests, incompatible version")
else:
    try:
        from elasticsearch import NotFoundError, TransportError
    except ImportError:
        pytestmark = pytest.mark.skip("Skipping elasticsearch tests, missing library")


def test__virtual_no_elasticsearch_lib():
    """
    Test __virtual__ function when elasticsearch is not installed
    and the elasticsearch module is not available
    """
    with patch.object(elasticsearch_mod, "HAS_ELASTICSEARCH", False):
        result = elasticsearch_mod.__virtual__()
        expected = (
            False,
            "Cannot load module elasticsearch: elasticsearch libraries not found",
        )
        assert expected == result


def test__virtual_with_elasticsearch_lib():
    """
    Test __virtual__ function when elasticsearch
    and the elasticsearch module is not available
    """
    with patch.multiple(elasticsearch_mod, HAS_ELASTICSEARCH=True, ES_MAJOR_VERSION=6):
        with patch.dict(
            elasticsearch_mod.__salt__, {"elasticsearch.index_exists": MagicMock()}
        ):
            result = elasticsearch_mod.__virtual__()
            expected = "elasticsearch"
            assert expected == result


def es_return_true(hosts=None, profile=None):
    return True


def es_raise_command_execution_error(hosts=None, profile=None):
    raise CommandExecutionError("custom message")


def test_ping():
    """
    Test if ping succeeds
    """
    with patch.object(elasticsearch_mod, "_get_instance", es_return_true):
        assert elasticsearch_mod.ping()


def test_ping_failure():
    """
    Test if ping fails
    """
    with patch.object(
        elasticsearch_mod, "_get_instance", es_raise_command_execution_error
    ):
        assert not elasticsearch_mod.ping()


def test_info():
    """
    Test if status fetch succeeds
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def info(self):
            """
            Mock of info method
            """
            return [{"test": "key"}]

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.info() == [{"test": "key"}]


def test_info_failure():
    """
    Test if status fetch fails with CommandExecutionError
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def info(self):
            """
            Mock of info method
            """
            raise TransportError("custom error", [123])

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError, match="custom error"):
            elasticsearch_mod.info()


def test_node_info():
    """
    Test if node status fetch succeeds
    """

    class MockElasticNodes:
        """
        Mock of Elasticsearch NodesClient
        """

        def info(self, node_id=None, flat_settings=None):
            """
            Mock of info method
            """
            return [{"test": "key"}]

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        nodes = MockElasticNodes()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.node_info() == [{"test": "key"}]


def test_node_info_failure():
    """
    Test if node status fetch fails with CommandExecutionError
    """

    class MockElasticNodes:
        """
        Mock of Elasticsearch NodesClient
        """

        def info(self, node_id=None, flat_settings=None):
            """
            Mock of info method
            """
            raise TransportError("custom error", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        nodes = MockElasticNodes()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.node_info()


def test_cluster_health():
    """
    Test if cluster status health fetch succeeds
    """

    class MockElasticCluster:
        """
        Mock of Elasticsearch ClusterClient
        """

        def health(self, index=None, level=None, local=None):
            """
            Mock of health method
            """
            return [{"test": "key"}]

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        cluster = MockElasticCluster()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.cluster_health() == [{"test": "key"}]


def test_cluster_health_failure():
    """
    Test if cluster status health fetch fails with CommandExecutionError
    """

    class MockElasticCluster:
        """
        Mock of Elasticsearch ClusterClient
        """

        def health(self, index=None, level=None, local=None):
            """
            Mock of health method
            """
            raise TransportError("custom error", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        cluster = MockElasticCluster()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.cluster_health()


def test_cluster_stats():
    """
    Test if cluster stats fetch succeeds
    """

    class MockElasticCluster:
        """
        Mock of Elasticsearch ClusterClient
        """

        def stats(self, node_id=None):
            """
            Mock of health method
            """
            return [{"test": "key"}]

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        cluster = MockElasticCluster()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.cluster_stats() == [{"test": "key"}]


def test_cluster_stats_failure():
    """
    Test if cluster stats fetch fails with CommandExecutionError
    """

    class MockElasticCluster:
        """
        Mock of Elasticsearch ClusterClient
        """

        def stats(self, node_id=None):
            """
            Mock of health method
            """
            raise TransportError("custom error", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        cluster = MockElasticCluster()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.cluster_stats()


def test_alias_create():
    """
    Test if alias is created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_alias(self, index=None, name=None, body=None):
            """
            Mock of put_alias method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.alias_create("foo", "bar", body="baz")


def test_alias_create_unack():
    """
    Test if alias creation is not acked
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_alias(self, index=None, name=None, body=None):
            """
            Mock of put_alias method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.alias_create("foo", "bar", body="baz")


def test_alias_create_failure():
    """
    Test if alias creation fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_alias(self, index=None, name=None, body=None):
            """
            Mock of put_alias method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.alias_create("foo", "bar", body="baz")


def test_alias_delete():
    """
    Test if alias is deleted
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_alias(self, index=None, name=None):
            """
            Mock of delete_alias method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.alias_delete("foo", "bar")


def test_alias_delete_unack():
    """
    Test if alias deletion is not acked
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_alias(self, index=None, name=None):
            """
            Mock of delete_alias method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.alias_delete("foo", "bar")


def test_alias_delete_failure():
    """
    Test if alias deletion fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_alias(self, index=None, name=None):
            """
            Mock of delete_alias method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.alias_delete("foo", "bar")


def test_alias_exists():
    """
    Test if alias exists
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists_alias(self, index=None, name=None):
            """
            Mock of exists_alias method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.alias_exists("foo", "bar")


def test_alias_exists_not():
    """
    Test if alias doesn't exist
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists_alias(self, index=None, name=None):
            """
            Mock of exists_alias method
            """
            raise NotFoundError

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.alias_exists("foo", "bar")


def test_alias_exists_failure():
    """
    Test if alias status obtain fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists_alias(self, index=None, name=None):
            """
            Mock of exists_alias method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.alias_exists("foo", "bar")


def test_alias_get():
    """
    Test if alias can be obtained
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_alias(self, index=None, name=None):
            """
            Mock of get_alias method
            """
            return {"test": "key"}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.alias_get("foo", "bar") == {"test": "key"}


def test_alias_get_not():
    """
    Test if alias doesn't exist
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_alias(self, index=None, name=None):
            """
            Mock of get_alias method
            """
            raise NotFoundError

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.alias_get("foo", "bar") is None


##############################################################################


def test_alias_get_failure():
    """
    Test if alias obtain fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_alias(self, index=None, name=None):
            """
            Mock of get_alias method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.alias_get("foo", "bar")


def test_document_create():
    """
    Test if document can be created
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def index(self, index=None, doc_type=None, body=None, id=None):
            """
            Mock of index method
            """
            return {"test": "key"}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.document_create("foo", "bar") == {"test": "key"}


def test_document_create_failure():
    """
    Test if document creation fails with CommandExecutionError
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def index(self, index=None, doc_type=None, body=None, id=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.document_create("foo", "bar")


def test_document_delete():
    """
    Test if document can be deleted
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def delete(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            return {"test": "key"}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.document_delete("foo", "bar", "baz") == {"test": "key"}


def test_document_delete_failure():
    """
    Test if document deletion fails with CommandExecutionError
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def delete(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.document_delete("foo", "bar", "baz")


def test_document_exists():
    """
    Test if document status can be obtained
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def exists(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            return True

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.document_exists("foo", "bar")


def test_document_exists_not():
    """
    Test if document doesn't exist
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def exists(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            return False

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.document_exists("foo", "bar")


def test_document_exists_failure():
    """
    Test if document exist state fails with CommandExecutionError
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def exists(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.document_exists("foo", "bar")


def test_document_get():
    """
    Test if document exists
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def get(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            return {"test": "key"}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.document_get("foo", "bar") == {"test": "key"}


def test_document_get_not():
    """
    Test if document doesn't exit
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def get(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            raise NotFoundError

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.document_get("foo", "bar") is None


def test_document_get_failure():
    """
    Test if document obtain fails with CommandExecutionError
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def get(self, index=None, doc_type=None, id=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.document_get("foo", "bar")


def test_index_create():
    """
    Test if index can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def create(self, index=None, body=None):
            """
            Mock of index method
            """
            return {"acknowledged": True, "shards_acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_create("foo", "bar")


def test_index_create_no_shards():
    """
    Test if index is created and no shards info is returned
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def create(self, index=None, body=None):
            """
            Mock of index method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_create("foo", "bar")


def test_index_create_not_shards():
    """
    Test if index is created and shards didn't acked
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def create(self, index=None, body=None):
            """
            Mock of index method
            """
            return {"acknowledged": True, "shards_acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_create("foo", "bar")


def test_index_create_not():
    """
    Test if index is created and shards didn't acked
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def create(self, index=None, body=None):
            """
            Mock of index method
            """
            return {"acknowledged": False, "shards_acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_create("foo", "bar")


def test_index_create_failure():
    """
    Test if index creation fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def create(self, index=None, body=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_create("foo", "bar")


# 'index_delete' function tests: 3


def test_index_delete():
    """
    Test if index can be deleted
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete(self, index=None):
            """
            Mock of index method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_delete("foo", "bar")


def test_index_delete_not():
    """
    Test if index is deleted and shards didn't acked
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete(self, index=None):
            """
            Mock of index method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_delete("foo", "bar")


def test_index_delete_failure():
    """
    Test if index deletion fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete(self, index=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_delete("foo", "bar")


def test_index_exists():
    """
    Test if index exists
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists(self, index=None):
            """
            Mock of index method
            """
            return True

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_exists("foo", "bar")


def test_index_exists_not():
    """
    Test if index doesn't exist
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists(self, index=None):
            """
            Mock of index method
            """
            raise NotFoundError

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_exists("foo", "bar")


def test_index_exists_failure():
    """
    Test if alias exist state fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists(self, index=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_exists("foo", "bar")


def test_index_get_settings():
    """
    Test if settings can be obtained from the index
    """

    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.get_settings = MagicMock(return_value={"foo": "key"})
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        assert elasticsearch_mod.index_get_settings("foo", "bar") == {"foo": "key"}


def test_index_get_settings_not_exists():
    """
    Test index_get_settings if index doesn't exist
    """

    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.get_settings = MagicMock()
    fake_es.indices.get_settings.side_effect = NotFoundError("custom error", 123)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        assert elasticsearch_mod.index_get_settings(index="foo") is None


def test_get_settings_failure():
    """
    Test if index settings get fails with CommandExecutionError
    """

    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.get_settings = MagicMock()
    fake_es.indices.get_settings.side_effect = TransportError("custom error", 123)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_get_settings(index="foo")


def test_index_put_settings():
    """
    Test if we can put settings for the index
    """

    body = {"settings": {"index": {"number_of_replicas": 2}}}
    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.put_settings = MagicMock(return_value={"acknowledged": True})
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        assert elasticsearch_mod.index_put_settings(index="foo", body=body)


def test_index_put_settings_not_exists():
    """
    Test if settings put executed against non-existing index
    """

    body = {"settings": {"index": {"number_of_replicas": 2}}}
    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.put_settings = MagicMock()
    fake_es.indices.put_settings.side_effect = NotFoundError("custom error", 123)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        assert elasticsearch_mod.index_put_settings(index="foo", body=body) is None


def test_index_put_settings_failure():
    """
    Test if settings put failed with CommandExecutionError
    """

    body = {"settings": {"index": {"number_of_replicas": 2}}}
    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.put_settings = MagicMock()
    fake_es.indices.put_settings.side_effect = TransportError("custom error", 123)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_put_settings(index="foo", body=body)


def test_index_get():
    """
    Test if index can be obtained
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get(self, index=None):
            """
            Mock of index method
            """
            return {"test": "key"}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_get("foo", "bar") == {"test": "key"}


def test_index_get_not():
    """
    Test if index doesn't exist
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get(self, index=None):
            """
            Mock of index method
            """
            raise NotFoundError

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_get("foo", "bar") is None


def test_index_get_failure():
    """
    Test if index obtain fails with CommandExecutionError
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get(self, index=None):
            """
            Mock of index method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_get("foo", "bar")


def test_index_open():
    """
    Test if index can be opened
    """

    class MockElasticIndices:
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

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_open("foo", "bar")


def test_index_open_not():
    """
    Test if index open isn't acked
    """

    class MockElasticIndices:
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

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_open("foo", "bar")


def test_index_open_failure():
    """
    Test if alias opening fails with CommandExecutionError
    """

    class MockElasticIndices:
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

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_open("foo", "bar")


def test_index_close():
    """
    Test if index can be closed
    """

    class MockElasticIndices:
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

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_close("foo", "bar")


def test_index_close_not():
    """
    Test if index close isn't acked
    """

    class MockElasticIndices:
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

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_close("foo", "bar")


def test_index_close_failure():
    """
    Test if index closing fails with CommandExecutionError
    """

    class MockElasticIndices:
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

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_close("foo", "bar")


def test_mapping_create():
    """
    Test if mapping can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_mapping(self, index=None, doc_type=None, body=None):
            """
            Mock of put_mapping method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.mapping_create("foo", "bar", "baz")


def test_mapping_create_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_mapping(self, index=None, doc_type=None, body=None):
            """
            Mock of put_mapping method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.mapping_create("foo", "bar", "baz")


def test_mapping_create_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_mapping(self, index=None, doc_type=None, body=None):
            """
            Mock of put_mapping method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.mapping_create("foo", "bar", "baz")


def test_mapping_delete():
    """
    Test if mapping can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_mapping(self, index=None, doc_type=None):
            """
            Mock of put_mapping method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.mapping_delete("foo", "bar", "baz")


def test_mapping_delete_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_mapping(self, index=None, doc_type=None):
            """
            Mock of put_mapping method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.mapping_delete("foo", "bar", "baz")


def test_mapping_delete_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_mapping(self, index=None, doc_type=None):
            """
            Mock of put_mapping method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.mapping_delete("foo", "bar", "baz")


def test_mapping_get():
    """
    Test if mapping can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_mapping(self, index=None, doc_type=None):
            """
            Mock of get_mapping method
            """
            return {"test": "key"}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.mapping_get("foo", "bar", "baz") == {"test": "key"}


def test_mapping_get_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_mapping(self, index=None, doc_type=None):
            """
            Mock of get_mapping method
            """
            raise NotFoundError

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.mapping_get("foo", "bar", "baz") is None


def test_mapping_get_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_mapping(self, index=None, doc_type=None):
            """
            Mock of get_mapping method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.mapping_get("foo", "bar", "baz")


def test_index_template_create():
    """
    Test if mapping can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_template(self, name=None, body=None):
            """
            Mock of put_template method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_template_create("foo", "bar")


def test_index_template_create_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_template(self, name=None, body=None):
            """
            Mock of put_template method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_template_create("foo", "bar")


def test_index_template_create_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_template(self, name=None, body=None):
            """
            Mock of put_template method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_template_create("foo", "bar")


def test_index_template_delete():
    """
    Test if mapping can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_template(self, name=None):
            """
            Mock of delete_template method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_template_delete("foo")


def test_index_template_delete_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_template(self, name=None):
            """
            Mock of delete_template method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_template_delete("foo")


def test_index_template_delete_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_template(self, name=None):
            """
            Mock of delete_template method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_template_delete("foo")


# 'index_template_exists' function tests: 3


def test_index_template_exists():
    """
    Test if mapping can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists_template(self, name=None):
            """
            Mock of exists_template method
            """
            return True

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_template_exists("foo")


def test_index_template_exists_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists_template(self, name=None):
            """
            Mock of exists_template method
            """
            return False

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.index_template_exists("foo")


def test_index_template_exists_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def exists_template(self, name=None):
            """
            Mock of exists_template method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_template_exists("foo")


def test_index_template_get():
    """
    Test if mapping can be created
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_template(self, name=None):
            """
            Mock of get_template method
            """
            return {"test": "key"}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_template_get("foo") == {"test": "key"}


def test_index_template_get_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_template(self, name=None):
            """
            Mock of get_template method
            """
            raise NotFoundError

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.index_template_get("foo") is None


def test_index_template_get_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIndices:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_template(self, name=None):
            """
            Mock of get_template method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        indices = MockElasticIndices()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.index_template_get("foo")


def test_pipeline_get():
    """
    Test if mapping can be created
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_pipeline(self, id=None):
            """
            Mock of get_pipeline method
            """
            return {"test": "key"}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.pipeline_get("foo") == {"test": "key"}


def test_pipeline_get_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_pipeline(self, id=None):
            """
            Mock of get_pipeline method
            """
            raise NotFoundError

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.pipeline_get("foo") is None


def test_pipeline_get_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def get_pipeline(self, id=None):
            """
            Mock of get_pipeline method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_get("foo")


def test_pipeline_get_wrong_version():
    """
    Test if mapping creation fails with CEE on invalid elasticsearch-py version
    """

    class MockElasticIngest:
        pass

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_get("foo")


def test_pipeline_delete():
    """
    Test if mapping can be created
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_pipeline(self, id=None):
            """
            Mock of delete_pipeline method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.pipeline_delete("foo")


def test_pipeline_delete_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_pipeline(self, id=None):
            """
            Mock of delete_pipeline method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.pipeline_delete("foo")


def test_pipeline_delete_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def delete_pipeline(self, id=None):
            """
            Mock of delete_pipeline method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_delete("foo")


def test_pipeline_delete_wrong_version():
    """
    Test if mapping creation fails with CEE on invalid elasticsearch-py version
    """

    class MockElasticIngest:
        pass

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_delete("foo")


# 'pipeline_create' function tests: 4


def test_pipeline_create():
    """
    Test if mapping can be created
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_pipeline(self, id=None, body=None):
            """
            Mock of put_pipeline method
            """
            return {"acknowledged": True}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.pipeline_create("foo", "bar")


def test_pipeline_create_not():
    """
    Test if mapping creation didn't ack
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_pipeline(self, id=None, body=None):
            """
            Mock of put_pipeline method
            """
            return {"acknowledged": False}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.pipeline_create("foo", "bar")


def test_pipeline_create_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def put_pipeline(self, id=None, body=None):
            """
            Mock of put_pipeline method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_create("foo", "bar")


def test_pipeline_create_wrong_version():
    """
    Test if mapping creation fails with CEE on invalid elasticsearch-py version
    """

    class MockElasticIngest:
        pass

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_create("foo", "bar")


def test_pipeline_simulate():
    """
    Test if mapping can be created
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def simulate(self, id=None, body=None, verbose=None):
            """
            Mock of simulate method
            """
            return {"test": "key"}

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.pipeline_simulate("foo", "bar") == {"test": "key"}


def test_pipeline_simulate_failure():
    """
    Test if mapping creation fails
    """

    class MockElasticIngest:
        """
        Mock of Elasticsearch IndicesClient
        """

        def simulate(self, id=None, body=None, verbose=None):
            """
            Mock of simulate method
            """
            raise TransportError("custom message", 123)

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_simulate("foo", "bar")


def test_pipeline_simulate_wrong_version():
    """
    Test if mapping creation fails with CEE on invalid elasticsearch-py version
    """

    class MockElasticIngest:
        pass

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        ingest = MockElasticIngest()

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.pipeline_simulate("foo", "bar")


def test_search_template_get():
    """
    Test if mapping can be created
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def get_template(self, id=None):
            """
            Mock of get_template method
            """
            return {"test": "key"}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.search_template_get("foo") == {"test": "key"}


def test_search_template_get_not():
    """
    Test if mapping can be created
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def get_template(self, id=None):
            """
            Mock of get_template method
            """
            raise NotFoundError

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.search_template_get("foo") is None


def test_search_template_get_failure():
    """
    Test if mapping creation fails
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def get_template(self, id=None):
            """
            Mock of get_template method
            """
            raise TransportError("custom message", 123)

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.search_template_get("foo")


def test_search_template_create():
    """
    Test if mapping can be created
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def put_template(self, id=None, body=None):
            """
            Mock of put_template method
            """
            return {"acknowledged": True}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.search_template_create("foo", "bar")


def test_search_template_create_not():
    """
    Test if mapping can be created
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def put_template(self, id=None, body=None):
            """
            Mock of put_template method
            """
            return {"acknowledged": False}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.search_template_create("foo", "bar")


def test_search_template_create_failure():
    """
    Test if mapping creation fails
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def put_template(self, id=None, body=None):
            """
            Mock of put_template method
            """
            raise TransportError("custom message", 123)

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.search_template_create("foo", "bar")


def test_search_template_delete():
    """
    Test if mapping can be deleted
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def delete_template(self, id=None):
            """
            Mock of delete_template method
            """
            return {"acknowledged": True}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.search_template_delete("foo")


def test_search_template_delete_not():
    """
    Test if mapping can be deleted but not acked
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def delete_template(self, id=None):
            """
            Mock of delete_template method
            """
            return {"acknowledged": False}

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert not elasticsearch_mod.search_template_delete("foo")


def test_search_template_delete_not_exists():
    """
    Test if deleting mapping doesn't exist
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def delete_template(self, id=None):
            """
            Mock of delete_template method
            """
            raise NotFoundError

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        assert elasticsearch_mod.search_template_delete("foo")


def test_search_template_delete_failure():
    """
    Test if mapping deletion fails
    """

    class MockElastic:
        """
        Mock of Elasticsearch client
        """

        def delete_template(self, id=None):
            """
            Mock of delete_template method
            """
            raise TransportError("custom message", 123)

    with patch.object(
        elasticsearch_mod, "_get_instance", MagicMock(return_value=MockElastic())
    ):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.search_template_delete("foo")


# Cluster settings tests below.
# We're assuming that _get_instance is properly tested
# These tests are very simple in nature, mostly checking default arguments.
def test_cluster_get_settings_succeess():
    """
    Test if cluster get_settings fetch succeeds
    """

    expected_settings = {"transient": {}, "persistent": {}}
    fake_es = MagicMock()
    fake_es.cluster = MagicMock()
    fake_es.cluster.get_settings = MagicMock(return_value=expected_settings)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        actual_settings = elasticsearch_mod.cluster_get_settings()
        fake_es.cluster.get_settings.assert_called_with(
            flat_settings=False, include_defaults=False
        )
        assert actual_settings == expected_settings


def test_cluster_get_settings_failure():
    """
    Test if cluster get_settings fetch fails with CommandExecutionError
    """

    fake_es = MagicMock()
    fake_es.cluster = MagicMock()
    fake_es.cluster.get_settings = MagicMock()
    fake_es.cluster.get_settings.side_effect = TransportError("custom error", 123)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.cluster_get_settings()


def test_cluster_put_settings_succeess():
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

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        actual_settings = elasticsearch_mod.cluster_put_settings(body=body)
        fake_es.cluster.put_settings.assert_called_with(body=body, flat_settings=False)
        assert actual_settings == expected_settings


def test_cluster_put_settings_failure():
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

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.cluster_put_settings(body=body)


def test_cluster_put_settings_nobody():
    """
    Test if cluster put_settings fails with SaltInvocationError
    """

    with pytest.raises(SaltInvocationError):
        elasticsearch_mod.cluster_put_settings()


# flush_synced tests below.
# We're assuming that _get_instance is properly tested
# These tests are very simple in nature, mostly checking default arguments.
def test_flush_synced_succeess():
    """
    Test if flush_synced succeeds
    """

    expected_return = {"_shards": {"failed": 0, "successful": 0, "total": 0}}
    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.flush_synced = MagicMock(return_value=expected_return)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        output = elasticsearch_mod.flush_synced(
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


def test_flush_synced_failure():
    """
    Test if flush_synced fails with CommandExecutionError
    """

    fake_es = MagicMock()
    fake_es.indices = MagicMock()
    fake_es.indices.flush_synced = MagicMock()
    fake_es.indices.flush_synced.side_effect = TransportError("custom error", 123)
    fake_instance = MagicMock(return_value=fake_es)

    with patch.object(elasticsearch_mod, "_get_instance", fake_instance):
        with pytest.raises(CommandExecutionError):
            elasticsearch_mod.flush_synced()

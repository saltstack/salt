"""
Test Salt ElasticSearch module
"""
import logging

import pytest
import salt.modules.elasticsearch as elasticsearch  # pylint: disable=unused-import

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.skipif(
        elasticsearch.HAS_ELASTICSEARCH is False,
        reason="No python elasticsearch client installed.",
    ),
]


@pytest.fixture(scope="module")
def salt_call_cli_wrapper(salt_call_cli, elasticsearch_container):
    def run_command(*command, **kwargs):
        return salt_call_cli.run(*command, **kwargs)

    return run_command


@pytest.fixture(scope="module")
def elasticsearch_host(elasticsearch_container):
    yield ["localhost:{}".format(elasticsearch_container.elasticsearch_port[0])]


def test_ping(salt_call_cli_wrapper, elasticsearch_host):
    ret = salt_call_cli_wrapper("elasticsearch.ping", hosts=elasticsearch_host)
    assert ret.json


def test_info(salt_call_cli_wrapper, elasticsearch_container, elasticsearch_host):
    ret = salt_call_cli_wrapper("elasticsearch.info", hosts=elasticsearch_host)

    assert ret.json
    assert "version" in ret.json
    assert "number" in ret.json["version"]
    assert (
        ret.json["version"]["number"] == elasticsearch_container.elasticsearch_version
    )


def test_node_info(salt_call_cli_wrapper, elasticsearch_host):
    ret = salt_call_cli_wrapper("elasticsearch.node_info", hosts=elasticsearch_host)
    assert ret.json


def test_cluster_health(salt_call_cli_wrapper, elasticsearch_host):
    ret = salt_call_cli_wrapper(
        "elasticsearch.cluster_health", hosts=elasticsearch_host
    )
    assert ret.json

    assert "number_of_data_nodes" in ret.json
    assert ret.json["number_of_data_nodes"] == 1

    assert "status" in ret.json
    assert ret.json["status"] == "green"


def test_index(salt_call_cli_wrapper, elasticsearch_host):
    ret = salt_call_cli_wrapper(
        "elasticsearch.index_create", index="testindex", hosts=elasticsearch_host
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.index_exists", index="testindex", hosts=elasticsearch_host
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.index_get", index="testindex", hosts=elasticsearch_host
    )
    assert ret.json
    assert "testindex" in ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.index_delete", index="testindex", hosts=elasticsearch_host
    )
    assert ret.json


def test_document(salt_call_cli_wrapper, elasticsearch_host):
    ret = salt_call_cli_wrapper(
        "elasticsearch.index_create", index="testindex", hosts=elasticsearch_host
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.index_exists", index="testindex", hosts=elasticsearch_host
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.document_create",
        index="testindex",
        doc_type="doctype1",
        body="{}",
        hosts=elasticsearch_host,
    )
    assert ret.json
    assert "_id" in ret.json

    document_id = ret.json["_id"]
    document_type = ret.json["_type"]

    ret = salt_call_cli_wrapper(
        "elasticsearch.document_exists",
        index="testindex",
        id=document_id,
        hosts=elasticsearch_host,
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.document_get",
        index="testindex",
        id=document_id,
        hosts=elasticsearch_host,
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.document_delete",
        index="testindex",
        doc_type=document_type,
        id=document_id,
        hosts=elasticsearch_host,
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "elasticsearch.index_delete", index="testindex", hosts=elasticsearch_host
    )
    assert ret.json

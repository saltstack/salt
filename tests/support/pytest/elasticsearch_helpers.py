import logging
import time

import attr
import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

docker = pytest.importorskip("docker")
docker_errors = pytest.importorskip("docker.errors")
log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class ElasticSearchImage:
    name = attr.ib()
    tag = attr.ib()
    container_id = attr.ib()

    def __str__(self):
        return "{}:{}".format(self.name, self.tag)


@attr.s(kw_only=True, slots=True)
class ElasticSearchCombo:
    elasticsearch_name = attr.ib()
    elasticsearch_version = attr.ib()
    # elasticsearch_port = attr.attrib(default=attr.Factory(list))
    elasticsearch_port = attr.ib()

    @elasticsearch_port.default
    def _elastic_search_port(self):
        return [get_unused_localhost_port(), get_unused_localhost_port()]


def get_test_versions():
    test_versions = []
    name = "elasticsearch"
    for version in ("6.8.16",):
        test_versions.append(
            ElasticSearchImage(
                name=name,
                tag=version,
                container_id=random_string("elasticsearch-{}-".format(version)),
            )
        )
    return test_versions


def get_test_version_id(value):
    return "container={}".format(value)


@pytest.fixture(scope="module", params=get_test_versions(), ids=get_test_version_id)
def elasticsearch_container(request, salt_factories, salt_call_cli):

    try:
        docker_client = docker.from_env()
    except docker_errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(docker_client)
    if connectable is not True:  # pragma: no cover
        pytest.skip(connectable)

    elasticsearch_image = request.param

    combo = ElasticSearchCombo(
        elasticsearch_name=elasticsearch_image.name,
        elasticsearch_version=elasticsearch_image.tag,
    )
    container = salt_factories.get_container(
        elasticsearch_image.container_id,
        "{}:{}".format(combo.elasticsearch_name, combo.elasticsearch_version),
        docker_client=docker_client,
        check_ports=combo.elasticsearch_port,
        container_run_kwargs={
            "ports": {
                "9200/tcp": combo.elasticsearch_port[0],
                "9300/tcp": combo.elasticsearch_port[1],
            },
            "environment": {"discovery.type": "single-node"},
        },
    )

    with container.started():
        available = False
        status_checks = 6
        check_host_cmd = "curl -X GET http://localhost:{}/_cluster/health".format(
            combo.elasticsearch_port[0]
        )

        while status_checks:
            status_checks -= 1
            # Make sure "ElasticSearch" is ready
            ret = salt_call_cli.run("cmd.run", cmd=check_host_cmd,)
            available = ret.exitcode == 0
            if available:
                break

            time.sleep(2)

        if available:
            yield combo
        else:
            pytest.fail(
                "Failed to check status of elasticsearch server running in container(id: {})".format(
                    elasticsearch_image.container_id
                )
            )

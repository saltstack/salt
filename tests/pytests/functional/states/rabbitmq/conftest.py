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
class RabbitMQImage:
    name = attr.ib()
    tag = attr.ib()
    container_id = attr.ib()

    def __str__(self):
        return "{}:{}".format(self.name, self.tag)


@attr.s(kw_only=True, slots=True)
class RabbitMQCombo:
    rabbitmq_name = attr.ib()
    rabbitmq_version = attr.ib()
    rabbitmq_port = attr.ib()

    @rabbitmq_port.default
    def _rabbitmq_port(self):
        return get_unused_localhost_port()


def get_test_versions():
    test_versions = []
    name = "rabbitmq"
    for version in ("3.8",):
        test_versions.append(
            RabbitMQImage(
                name=name,
                tag=version,
                container_id=random_string("rabbitmq-{}-".format(version)),
            )
        )
    return test_versions


def get_test_version_id(value):
    return "container={}".format(value)


@pytest.fixture(scope="module", params=get_test_versions(), ids=get_test_version_id)
def rabbitmq_container(request, salt_factories, modules):

    try:
        docker_client = docker.from_env()
    except docker_errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(docker_client)
    if connectable is not True:  # pragma: no cover
        pytest.skip(connectable)

    rabbitmq_image = request.param

    combo = RabbitMQCombo(
        rabbitmq_name=rabbitmq_image.name,
        rabbitmq_version=rabbitmq_image.tag,
    )
    container = salt_factories.get_container(
        rabbitmq_image.container_id,
        "{}:{}".format(combo.rabbitmq_name, combo.rabbitmq_version),
        docker_client=docker_client,
    )
    with container.started():
        # Sleep
        time.sleep(10)

        authenticated = False
        login_attempts = 6
        while login_attempts:
            login_attempts -= 1
            ret = container.run("rabbitmqctl status --formatter=json")
            authenticated = ret.exitcode == 0
            if authenticated:
                break

            time.sleep(10)

        if authenticated:
            yield container
        else:
            pytest.fail(
                "Failed to connect to rabbitmq in container(id: {})".format(
                    rabbitmq_image.container_id
                )
            )


@pytest.fixture(scope="module")
def docker_cmd_run_all_wrapper(rabbitmq_container):
    def run_command(cmd, **kwargs):
        # Update rabbitmqctl location
        if cmd[0] is None:
            cmd[0] = "/opt/rabbitmq/sbin/rabbitmqctl"

        ret = rabbitmq_container.run(cmd)
        res = {"retcode": ret.exitcode, "stdout": ret.stdout, "stderr": ret.stderr}
        return res

    return run_command

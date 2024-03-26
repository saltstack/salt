import logging
import time

import attr
import pytest
from saltfactories.utils import random_string

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class RabbitMQImage:
    name = attr.ib()
    tag = attr.ib()
    container_id = attr.ib()

    @container_id.default
    def _default_container_id(self):
        return random_string(f"{self.name}-{self.tag}-")

    def __str__(self):
        return f"{self.name}:{self.tag}"


@attr.s(kw_only=True, slots=True)
class RabbitMQCombo:
    rabbitmq_name = attr.ib()
    rabbitmq_version = attr.ib()


def get_test_versions():
    test_versions = []
    name = "rabbitmq"
    for version in (
        "3.9",
        "3.10",
    ):
        test_versions.append(
            RabbitMQImage(name=name, tag=version),
        )
    return test_versions


def get_test_version_id(value):
    return f"container={value}"


@pytest.fixture(scope="package", params=get_test_versions(), ids=get_test_version_id)
def rabbitmq_image(request):
    return request.param


def confirm_container_running(timeout_at, container):
    sleeptime = 1
    time.sleep(5)
    while time.time() <= timeout_at:
        ret = container.run("rabbitmqctl status --formatter=json")
        if ret.returncode == 0:
            break
        time.sleep(sleeptime)
        sleeptime *= 2
    else:
        return False
    return True


@pytest.fixture(scope="package")
def rabbitmq_container(salt_factories, rabbitmq_image):

    combo = RabbitMQCombo(
        rabbitmq_name=rabbitmq_image.name,
        rabbitmq_version=rabbitmq_image.tag,
    )
    container = salt_factories.get_container(
        rabbitmq_image.container_id,
        "ghcr.io/saltstack/salt-ci-containers/{}:{}".format(
            combo.rabbitmq_name, combo.rabbitmq_version
        ),
        container_run_kwargs={
            "ports": {"5672/tcp": None},
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    container.container_start_check(confirm_container_running, container)
    with container.started():
        yield container


@pytest.fixture(scope="package")
def docker_cmd_run_all_wrapper(rabbitmq_container):
    def run_command(cmd, **kwargs):
        # Update rabbitmqctl location
        if cmd[0] is None:
            cmd[0] = "/opt/rabbitmq/sbin/rabbitmqctl"

        ret = rabbitmq_container.run(cmd)
        res = {"retcode": ret.returncode, "stdout": ret.stdout, "stderr": ret.stderr}
        return res

    return run_command


@pytest.fixture(scope="package")
def docker_cmd_run_wrapper(rabbitmq_container):
    def run_command(cmd, **kwargs):
        # Update rabbitmqctl location
        if cmd[0] is None:
            cmd[0] = "/opt/rabbitmq/sbin/rabbitmqctl"

        ret = rabbitmq_container.run(cmd)
        return ret.stdout

    return run_command

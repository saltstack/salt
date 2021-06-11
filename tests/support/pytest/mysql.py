import time

import attr
import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

docker = pytest.importorskip("docker")
docker_errors = pytest.importorskip("docker.errors")


@attr.s(kw_only=True, slots=True)
class MySQLImage:
    name = attr.ib()
    tag = attr.ib()
    container_id = attr.ib()

    def __str__(self):
        return "{}:{}".format(self.name, self.tag)


@attr.s(kw_only=True, slots=True)
class MySQLCombo:
    mysql_name = attr.ib()
    mysql_version = attr.ib()
    mysql_port = attr.ib()
    mysql_user = attr.ib()
    mysql_passwd = attr.ib()

    @mysql_port.default
    def _mysql_port(self):
        return get_unused_localhost_port()


def get_test_versions():
    test_versions = []
    name = "mysql/mysql-server"
    for version in ("5.5", "5.6", "5.7", "8.0"):
        test_versions.append(
            MySQLImage(
                name=name,
                tag=version,
                container_id=random_string("mysql-{}-".format(version)),
            )
        )
    name = "mariadb"
    for version in ("10.1", "10.2", "10.3", "10.4", "10.5"):
        test_versions.append(
            MySQLImage(
                name=name,
                tag=version,
                container_id=random_string("mariadb-{}-".format(version)),
            )
        )
    name = "percona"
    for version in ("5.5", "5.6", "5.7", "8.0"):
        test_versions.append(
            MySQLImage(
                name=name,
                tag=version,
                container_id=random_string("percona-{}-".format(version)),
            )
        )
    return test_versions


def get_test_version_id(value):
    return "container={}".format(value)


@pytest.fixture(scope="module", params=get_test_versions(), ids=get_test_version_id)
def mysql_container(request, salt_factories, salt_call_cli):

    try:
        docker_client = docker.from_env()
    except docker_errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(docker_client)
    if connectable is not True:  # pragma: no cover
        pytest.skip(connectable)

    mysql_image = request.param

    mysql_user = "root"
    mysql_passwd = "password"

    combo = MySQLCombo(
        mysql_name=mysql_image.name,
        mysql_version=mysql_image.tag,
        mysql_user=mysql_user,
        mysql_passwd=mysql_passwd,
    )
    container = salt_factories.get_container(
        mysql_image.container_id,
        "{}:{}".format(combo.mysql_name, combo.mysql_version),
        docker_client=docker_client,
        check_ports=[combo.mysql_port],
        container_run_kwargs={
            "ports": {"3306/tcp": combo.mysql_port},
            "environment": {
                "MYSQL_ROOT_PASSWORD": mysql_passwd,
                "MYSQL_ROOT_HOST": "%",
            },
        },
    )
    with container.started():
        authenticated = False
        login_attempts = 6
        while login_attempts:
            login_attempts -= 1
            # Make sure "MYSQL" is ready
            ret = salt_call_cli.run(
                "docker.run",
                name=mysql_image.container_id,
                cmd="mysql --user=root --password=password -e 'SELECT 1'",
            )
            authenticated = ret.exitcode == 0
            if authenticated:
                break

            time.sleep(2)

        if authenticated:
            yield combo
        else:
            pytest.fail(
                "Failed to login into mysql server running in container(id: {})".format(
                    mysql_image.container_id
                )
            )

import logging
import time

import attr
import pytest
from saltfactories.utils import random_string

# This `pytest.importorskip` here actually works because this module
# is imported into test modules, otherwise, the skipping would just fail
pytest.importorskip("docker")
import docker.errors  # isort:skip  pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


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
    mysql_port = attr.ib(default=None)
    mysql_host = attr.ib(default="%")
    mysql_user = attr.ib()
    mysql_passwd = attr.ib()
    mysql_database = attr.ib(default=None)
    mysql_root_user = attr.ib(default="root")
    mysql_root_passwd = attr.ib()
    container = attr.ib(default=None)
    container_id = attr.ib()

    @container_id.default
    def _default_container_id(self):
        return random_string(
            "{}-{}-".format(
                self.mysql_name.replace("/", "-"),
                self.mysql_version,
            )
        )

    @mysql_root_passwd.default
    def _default_mysql_root_user_passwd(self):
        return self.mysql_passwd

    def get_credentials(self, **kwargs):
        return {
            "connection_user": kwargs.get("connection_user") or self.mysql_root_user,
            "connection_pass": kwargs.get("connection_pass") or self.mysql_root_passwd,
            "connection_db": kwargs.get("connection_db") or "mysql",
            "connection_port": kwargs.get("connection_port") or self.mysql_port,
        }


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
    for version in ("10.3", "10.4", "10.5", "10.6"):
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
def mysql_image(request):
    return request.param


@pytest.fixture(scope="module")
def create_mysql_combo(mysql_image):
    return MySQLCombo(
        mysql_name=mysql_image.name,
        mysql_version=mysql_image.tag,
        mysql_user="salt-mysql-user",
        mysql_passwd="Pa55w0rd!",
        container_id=mysql_image.container_id,
    )


@pytest.fixture(scope="module")
def mysql_combo(create_mysql_combo):
    return create_mysql_combo


def check_container_started(timeout_at, container, combo):
    sleeptime = 0.5
    while time.time() <= timeout_at:
        try:
            if not container.is_running():
                log.warning("%s is no longer running", container)
                return False
            ret = container.run(
                "mysql",
                "--user={}".format(combo.mysql_user),
                "--password={}".format(combo.mysql_passwd),
                "-e",
                "SELECT 1",
            )
            if ret.returncode == 0:
                break
        except docker.errors.APIError:
            log.exception("Failed to run start check")
        time.sleep(sleeptime)
        sleeptime *= 2
    else:
        return False
    time.sleep(0.5)
    return True


def set_container_name_before_start(container):
    """
    This is useful if the container has to be restared and the old
    container, under the same name was left running, but in a bad shape.
    """
    container.name = random_string("{}-".format(container.name.rsplit("-", 1)[0]))
    container.display_name = None
    return container


@pytest.fixture(scope="module")
def mysql_container(salt_factories, mysql_combo):

    container_environment = {
        "MYSQL_ROOT_PASSWORD": mysql_combo.mysql_passwd,
        "MYSQL_ROOT_HOST": mysql_combo.mysql_host,
        "MYSQL_USER": mysql_combo.mysql_user,
        "MYSQL_PASSWORD": mysql_combo.mysql_passwd,
    }
    if mysql_combo.mysql_database:
        container_environment["MYSQL_DATABASE"] = mysql_combo.mysql_database

    container = salt_factories.get_container(
        mysql_combo.container_id,
        "ghcr.io/saltstack/salt-ci-containers/{}:{}".format(
            mysql_combo.mysql_name, mysql_combo.mysql_version
        ),
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "ports": {"3306/tcp": None},
            "environment": container_environment,
        },
    )
    container.before_start(set_container_name_before_start, container)
    container.container_start_check(check_container_started, container, mysql_combo)
    with container.started():
        mysql_combo.container = container
        mysql_combo.mysql_port = container.get_host_port_binding(
            3306, protocol="tcp", ipv6=False
        )
        yield mysql_combo

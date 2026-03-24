import logging
import time
from contextlib import contextmanager

import attr
import pytest
from pytestskipmarkers.utils import platform
from saltfactories.utils import random_string

try:
    from docker.errors import APIError
except ImportError:
    APIError = OSError

log = logging.getLogger(__name__)


def _has_driver(driver_name):
    try:
        __import__(driver_name)
        return True
    except ImportError:
        return False


def db_param(db_name, version, driver_name=None):
    """
    Return a pytest.param for a database, optionally skipping if the driver is missing.

    :param db_name: Logical name of the database (e.g., 'postgres', 'mysql')
    :param driver_name: Python module to import for the driver (e.g., 'psycopg2')
    :return: pytest.param with conditional skip
    """
    if driver_name is None:
        return pytest.param((db_name, version), id=f"{db_name}-{version or 'default'}")
    else:
        has_driver = _has_driver(driver_name)
        return pytest.param(
            (db_name, version),
            marks=pytest.mark.skipif(
                not has_driver, reason=f"{driver_name} not installed"
            ),
            id=f"{db_name}-{version or 'default'}",
        )


def available_databases(subset=None):
    """
    Return a list of pytest.param objects for known databases,
    skipping those without drivers installed.
    if passed subset input, will skip dbs that have no driver.
    """
    driver_map = {
        "sqlite": None,
        "postgresql": "psycopg",
        "mysql-server": "pymysql",
        "percona": "pymysql",
        "mariadb": "pymysql",
    }

    all_configurations = [
        ("sqlite"),
        ("postgresql", "13"),
        ("postgresql", "17"),
        ("mysql-server", "5.5"),
        ("mysql-server", "5.6"),
        ("mysql-server", "5.7"),
        ("mysql-server", "8.0"),
        ("mariadb", "10.3"),
        ("mariadb", "10.4"),
        ("mariadb", "10.5"),
        ("percona", "5.6"),
        ("percona", "5.7"),
        ("percona", "8.0"),
    ]

    if not subset:
        subset = all_configurations

    marks = []
    for tup in subset:
        if len(tup) == 3:
            db_name, version, driver = tup
            marks.append(db_param(db_name, version, driver_name=driver))
        else:
            db_name, version = tup
            marks.append(db_param(db_name, version, driver_name=driver_map[db_name]))

    return marks


@attr.s(kw_only=True, slots=True)
class DockerImage:
    name = attr.ib()
    tag = attr.ib()
    container_id = attr.ib()

    def __str__(self):
        return f"{self.name}:{self.tag}"


@attr.s(kw_only=True, slots=True)
class DatabaseCombo:
    name = attr.ib()
    dialect = attr.ib()
    version = attr.ib()
    port = attr.ib(default=None)
    host = attr.ib(default="%")
    user = attr.ib()
    passwd = attr.ib()
    database = attr.ib(default=None)
    root_user = attr.ib(default="root")
    root_passwd = attr.ib()
    container = attr.ib(default=None)
    container_id = attr.ib()

    @container_id.default
    def _default_container_id(self):
        return random_string(
            "{}-{}-".format(
                self.name.replace("/", "-"),
                self.version,
            )
        )

    @root_passwd.default
    def _default_root_user_passwd(self):
        return self.passwd

    def get_credentials(self, **kwargs):
        return {
            "connection_user": kwargs.get("connection_user") or self.root_user,
            "connection_pass": kwargs.get("connection_pass") or self.root_passwd,
            "connection_db": kwargs.get("connection_db") or self.database,
            "connection_port": kwargs.get("connection_port") or self.port,
        }


def set_container_name_before_start(container):
    """
    This is useful if the container has to be restared and the old
    container, under the same name was left running, but in a bad shape.
    """
    container.name = random_string("{}-".format(container.name.rsplit("-", 1)[0]))
    container.display_name = None
    return container


def check_container_started(timeout_at, container, container_test):
    sleeptime = 0.5
    while time.time() <= timeout_at:
        try:
            if not container.is_running():
                log.warning("%s is no longer running", container)
                return False
            ret = container_test()
            if ret.returncode == 0:
                break
        except APIError:
            log.exception("Failed to run start check")
        time.sleep(sleeptime)
        sleeptime *= 2
    else:
        return False
    time.sleep(0.5)
    return True


@pytest.fixture(scope="module")
def database_backend(request, salt_factories):
    backend_type, version = request.param

    docker_image = DockerImage(
        name=backend_type.replace("postgresql", "postgres"),
        tag=version,
        container_id=random_string(f"{backend_type}-{version}-"),
    )

    if platform.is_fips_enabled():
        if (
            docker_image.name in ("mysql-server", "percona")
            and docker_image.tag == "8.0"
        ):
            pytest.skip(f"These tests fail on {docker_image.name}:{docker_image.tag}")

    if backend_type == "postgresql":
        with make_postgresql_backend(salt_factories, docker_image) as container:
            yield container
    elif backend_type in ("mysql-server", "percona", "mariadb"):
        with make_mysql_backend(salt_factories, docker_image, request) as container:
            yield container
    elif backend_type == "sqlite":
        # just a stub to make sqlite act the same as ms/pg
        yield DatabaseCombo(
            name="sqlite", dialect="sqlite", version=version, user=None, passwd=None
        )
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


@contextmanager
def make_postgresql_backend(salt_factories, postgresql_image):
    postgresql_combo = DatabaseCombo(
        name=postgresql_image.name,
        dialect="postgresql",
        version=postgresql_image.tag,
        user="salt-postgres-user",
        passwd="Pa55w0rd!",
        database="salt",
        container_id=postgresql_image.container_id,
    )

    container_environment = {
        "POSTGRES_USER": postgresql_combo.user,
        "POSTGRES_PASSWORD": postgresql_combo.passwd,
    }
    if postgresql_combo.database:
        container_environment["POSTGRES_DB"] = postgresql_combo.database

    container = salt_factories.get_container(
        postgresql_combo.container_id,
        f"{postgresql_combo.name}:{postgresql_combo.version}",
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "ports": {"5432/tcp": None},
            "environment": container_environment,
        },
    )

    def _test():
        return container.run(
            "psql",
            f"--user={postgresql_combo.user}",
            postgresql_combo.database,
            "-e",
            "SELECT 1",
            environment={"PG_PASSWORD": postgresql_combo.passwd},
        )

    container.before_start(set_container_name_before_start, container)
    container.container_start_check(check_container_started, container, _test)
    with container.started():
        postgresql_combo.container = container
        postgresql_combo.port = container.get_host_port_binding(
            5432, protocol="tcp", ipv6=False
        )
        yield postgresql_combo


@contextmanager
def make_mysql_backend(salt_factories, mysql_image, request):
    # modules.test_mysql explicitly expects no database pre-created
    mysql_combo = DatabaseCombo(
        name=mysql_image.name,
        dialect="mysql",
        version=mysql_image.tag,
        user="salt-mysql-user",
        passwd="Pa55w0rd!",
        database=(
            None
            # the mysql module test expects no database
            if request.module.__name__ == "tests.pytests.functional.modules.test_mysql"
            else "salt"
        ),
        container_id=mysql_image.container_id,
    )

    container_environment = {
        "MYSQL_ROOT_PASSWORD": mysql_combo.passwd,
        "MYSQL_ROOT_HOST": mysql_combo.host,
        "MYSQL_USER": mysql_combo.user,
        "MYSQL_PASSWORD": mysql_combo.passwd,
    }
    if mysql_combo.database:
        container_environment["MYSQL_DATABASE"] = mysql_combo.database

    container = salt_factories.get_container(
        mysql_combo.container_id,
        "ghcr.io/saltstack/salt-ci-containers/{}:{}".format(
            mysql_combo.name, mysql_combo.version
        ),
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "ports": {"3306/tcp": None},
            "environment": container_environment,
        },
    )

    def _test():
        return container.run(
            "mysql",
            f"--user={mysql_combo.user}",
            f"--password={mysql_combo.passwd}",
            "-e",
            "SELECT 1",
        )

    container.before_start(set_container_name_before_start, container)
    container.container_start_check(check_container_started, container, _test)
    with container.started():
        mysql_combo.container = container
        mysql_combo.port = container.get_host_port_binding(
            3306, protocol="tcp", ipv6=False
        )
        yield mysql_combo

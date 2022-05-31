import logging
import threading
import time

import pytest
import salt.modules.etcd_mod as etcd_mod
from pytestshellutils.utils import ports
from salt.utils.etcd_util import HAS_ETCD_V2, HAS_ETCD_V3, get_conn
from saltfactories.utils import random_string

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        etcd_mod: {
            "__opts__": minion_opts,
            "__utils__": {
                "etcd_util.get_conn": get_conn,
            },
        },
    }


@pytest.fixture(scope="module")
def etcd_port():
    return ports.get_unused_localhost_port()


# TODO: Use our own etcd image to avoid reliance on a third party
@pytest.fixture(scope="module", autouse=True)
def etcd_apiv2_container(salt_factories, etcd_port):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name="bitnami/etcd:3",
        check_ports=[etcd_port],
        container_run_kwargs={
            "environment": {
                "ALLOW_NONE_AUTHENTICATION": "yes",
                "ETCD_ENABLE_V2": "true",
            },
            "ports": {"2379/tcp": etcd_port},
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module", params=(True, False))
def use_v2(request):
    if request.param and not HAS_ETCD_V2:
        pytest.skip("No etcd library installed")
    if not request.param and not HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return request.param


@pytest.fixture(scope="module")
def profile_name():
    return "etcd_util_profile"


@pytest.fixture(scope="module")
def etcd_profile(profile_name, etcd_port, use_v2):
    profile = {
        profile_name: {
            "etcd.host": "127.0.0.1",
            "etcd.port": etcd_port,
            "etcd.require_v2": use_v2,
        }
    }

    return profile


@pytest.fixture(scope="module")
def minion_config_overrides(etcd_profile):
    return etcd_profile


@pytest.fixture(scope="module")
def etcd_client(minion_opts, profile_name):
    return get_conn(minion_opts, profile=profile_name)


@pytest.fixture(scope="module")
def prefix():
    return "/salt/util/test"


@pytest.fixture(autouse=True)
def cleanup_prefixed_entries(etcd_client, prefix):
    """
    Cleanup after each test to ensure a consistent starting state.
    """
    try:
        assert etcd_client.get(prefix, recurse=True) is None
        yield
    finally:
        etcd_client.delete(prefix, recurse=True)


def test_basic_operations(subtests, profile_name, prefix, use_v2):
    """
    Make sure we can do the basics
    """
    with subtests.test("There should be no entries at the start with our prefix."):
        assert etcd_mod.get_(prefix, recurse=True, profile=profile_name) is None

    with subtests.test("We should be able to set and retrieve simple values"):
        etcd_mod.set_("{}/1".format(prefix), "one", profile=profile_name)
        assert (
            etcd_mod.get_("{}/1".format(prefix), recurse=False, profile=profile_name)
            == "one"
        )

    with subtests.test("We should be able to update and retrieve those values"):
        updated = {
            "1": "not one",
            "2": {
                "3": "two-three",
                "4": "two-four",
            },
        }
        etcd_mod.update(updated, path=prefix, profile=profile_name)
        assert etcd_mod.get_(prefix, recurse=True, profile=profile_name) == updated

    with subtests.test("We should be list all top level values at a directory"):
        expected = {
            prefix: {
                "{}/1".format(prefix): "not one",
                "{}/2/".format(prefix): {},
            },
        }
        assert etcd_mod.ls_(path=prefix, profile=profile_name) == expected

    with subtests.test("We should be able to remove values and get a tree hierarchy"):
        updated = {
            "2": {
                "3": "two-three",
                "4": "two-four",
            },
        }
        etcd_mod.rm_("{}/1".format(prefix), profile=profile_name)
        assert etcd_mod.tree(path=prefix, profile=profile_name) == updated

    with subtests.test("updates should be able to be caught by waiting in read"):
        return_list = []

        def wait_func(return_list):
            return_list.append(
                etcd_mod.watch("{}/1".format(prefix), timeout=30, profile=profile_name)
            )

        wait_thread = threading.Thread(target=wait_func, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_mod.set_("{}/1".format(prefix), "one", profile=profile_name)
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == "{}/1".format(prefix)
        assert modified["value"] == "one"


def test_with_missing_profile(subtests, prefix, use_v2, etcd_port):
    """
    Test the correct response when the profile is missing and we can't connect
    """
    if use_v2 and etcd_port != 2379:
        # Only need to run this once
        with subtests.test("Test no profile and bad connection in get_"):
            assert etcd_mod.get_("{}/1".format(prefix)) is None

        with subtests.test("Test no profile and bad connection in set_"):
            assert etcd_mod.set_("{}/1".format(prefix), "lol") is None

        with subtests.test("Test no profile and bad connection in update"):
            assert etcd_mod.update({"{}/1".format(prefix): "SIUUU"}) is None

        with subtests.test("Test no profile and bad connection in watch"):
            assert etcd_mod.watch("{}/1".format(prefix)) is None

        with subtests.test("Test no profile and bad connection in ls_"):
            assert etcd_mod.ls_() is None

        with subtests.test("Test no profile and bad connection in rm"):
            assert etcd_mod.rm_("{}/1".format(prefix)) is None

        with subtests.test("Test no profile and bad connection in tree"):
            assert etcd_mod.tree() is None

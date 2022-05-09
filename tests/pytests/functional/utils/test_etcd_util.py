import copy
import logging
import threading
import time

import pytest
from salt.utils.etcd_util import (
    HAS_ETCD_V2,
    HAS_ETCD_V3,
    EtcdClient,
    EtcdClientV3,
    get_conn,
)
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: nocover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="module")
def docker_image_name(docker_client):
    image_name = "bitnami/etcd:3"
    try:
        docker_client.images.pull(image_name)
    except docker.errors.APIError as exc:
        pytest.skip("Failed to pull docker image '{}': {}".format(image_name, exc))
    return image_name


@pytest.fixture(scope="module")
def etcd_port():
    return get_unused_localhost_port()


# TODO: Use our own etcd image to avoid reliance on a third party
@pytest.fixture(scope="module", autouse=True)
def etcd_container(salt_factories, docker_client, etcd_port, docker_image_name):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name=docker_image_name,
        docker_client=docker_client,
        check_ports=[etcd_port],
        container_run_kwargs={
            "environment": {
                "ALLOW_NONE_AUTHENTICATION": "yes",
                "ETCD_ENABLE_V2": "true",
            },
            "ports": {"2379/tcp": etcd_port},
        },
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


def test_etcd_client_creation(minion_opts, profile_name, use_v2):
    """
    Client creation using client classes, just need to assert no errors.
    """
    if use_v2:
        EtcdClient(minion_opts, profile=profile_name)
    else:
        EtcdClientV3(minion_opts, profile=profile_name)


def test_etcd_client_creation_with_get_conn(minion_opts, profile_name):
    """
    Client creation using get_conn, just need to assert no errors.
    """
    get_conn(minion_opts, profile=profile_name)


def test_simple_operations(etcd_client, prefix):
    """
    Verify basic functionality in order to justify use of the cleanup fixture.
    """
    assert not etcd_client.get("{}/mtg/ambush".format(prefix))
    assert etcd_client.set("{}/mtg/ambush".format(prefix), "viper") == "viper"
    assert etcd_client.get("{}/mtg/ambush".format(prefix)) == "viper"
    assert etcd_client.set("{}/mtg/counter".format(prefix), "spell") == "spell"
    assert etcd_client.tree("{}/mtg".format(prefix)) == {
        "ambush": "viper",
        "counter": "spell",
    }
    assert etcd_client.ls("{}/mtg".format(prefix)) == {
        "{}/mtg".format(prefix): {
            "{}/mtg/ambush".format(prefix): "viper",
            "{}/mtg/counter".format(prefix): "spell",
        },
    }
    assert etcd_client.delete("{}/mtg/ambush".format(prefix))
    assert etcd_client.delete("{}/mtg".format(prefix), recurse=True)
    assert not etcd_client.get("{}/mtg".format(prefix), recurse=True)


def test_simple_operations_with_raw_keys_and_values(
    minion_opts, profile_name, prefix, use_v2
):
    if use_v2:
        pytest.skip("Not testing with raw keys using v2")
    modified_opts = copy.deepcopy(minion_opts)
    modified_opts[profile_name]["etcd.raw_keys"] = True
    modified_opts[profile_name]["etcd.raw_values"] = True
    etcd_client = get_conn(modified_opts, profile=profile_name)
    assert not etcd_client.get("{}/mtg/ambush".format(prefix))
    assert etcd_client.set("{}/mtg/ambush".format(prefix), "viper") == b"viper"
    assert etcd_client.get("{}/mtg/ambush".format(prefix)) == b"viper"
    assert etcd_client.set("{}/mtg/counter".format(prefix), "spell") == b"spell"
    assert etcd_client.tree("{}/mtg".format(prefix)) == {
        b"ambush": b"viper",
        b"counter": b"spell",
    }
    assert etcd_client.ls("{}/mtg".format(prefix)) == {
        "{}/mtg".format(prefix).encode("UTF-8"): {
            "{}/mtg/ambush".format(prefix).encode("UTF-8"): b"viper",
            "{}/mtg/counter".format(prefix).encode("UTF-8"): b"spell",
        },
    }
    assert etcd_client.delete("{}/mtg/ambush".format(prefix))
    assert etcd_client.delete("{}/mtg".format(prefix), recurse=True)
    assert not etcd_client.get("{}/mtg".format(prefix), recurse=True)


def test_get(subtests, etcd_client, prefix):
    """
    Test that get works as intended.
    """

    # Test general get case with key=value
    with subtests.test("inserted keys should be able to be retrieved"):
        etcd_client.set("{}/get-test/key".format(prefix), "value")
        assert etcd_client.get("{}/get-test/key".format(prefix)) == "value"

    # Test with recurse=True.
    with subtests.test("keys should be able to be retrieved recursively"):
        etcd_client.set("{}/get-test/key2/subkey".format(prefix), "subvalue")
        etcd_client.set("{}/get-test/key2/subkey2/1".format(prefix), "subvalue1")
        etcd_client.set("{}/get-test/key2/subkey2/2".format(prefix), "subvalue2")

        expected = {
            "subkey": "subvalue",
            "subkey2": {
                "1": "subvalue1",
                "2": "subvalue2",
            },
        }

        assert (
            etcd_client.get("{}/get-test/key2".format(prefix), recurse=True) == expected
        )


def test_read(subtests, etcd_client, prefix, use_v2):
    """
    Test that we are able to read and wait.
    """
    etcd_client.set("{}/read/1".format(prefix), "one")
    etcd_client.set("{}/read/2".format(prefix), "two")
    etcd_client.set("{}/read/3/4".format(prefix), "three/four")

    # Simple read test
    with subtests.test(
        "reading a newly inserted and existent key should return that key"
    ):
        result = etcd_client.read("{}/read/1".format(prefix))
        assert result
        assert (result if use_v2 else result.pop()).value == "one"

    # Recursive read test
    with subtests.test(
        "reading recursively should return a dictionary starting at the given key"
    ):
        expected = etcd_client._flatten(
            {
                "1": "one",
                "2": "two",
                "3": {"4": "three/four"},
            },
            path="{}/read".format(prefix),
        )

        result = etcd_client.read("{}/read".format(prefix), recurse=True)
        assert result
        assert result.children if use_v2 else len(result) > 1

        result_dict = {}
        if use_v2:
            for child in result.children:
                result_dict[child.key] = child.value
        else:
            for child in result:
                if child.key != "{}/read".format(prefix):
                    result_dict[child.key] = child.value
        assert result_dict == expected

    # Wait for an update
    with subtests.test("updates should be able to be caught by waiting in read"):
        return_list = []

        def wait_func(return_list):
            return_list.append(
                etcd_client.read("{}/read/1".format(prefix), wait=True, timeout=30)
            )

        wait_thread = threading.Thread(target=wait_func, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/read/1".format(prefix), "not one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == "{}/read/1".format(prefix)
        assert modified.value == "not one"

    # Wait for an update using recursive
    with subtests.test("nested updates should be catchable"):
        return_list = []

        def wait_func_2(return_list):
            return_list.append(
                etcd_client.read(
                    "{}/read".format(prefix), wait=True, timeout=30, recurse=True
                )
            )

        wait_thread = threading.Thread(target=wait_func_2, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/read/1".format(prefix), "one again!")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == "{}/read/1".format(prefix)
        assert modified.value == "one again!"

    # Wait for an update after last modification
    with subtests.test(
        "updates should be able to be caught after an index by waiting in read"
    ):
        return_list = []
        last_modified = modified.modifiedIndex if use_v2 else modified.mod_revision

        def wait_func_3(return_list):
            return_list.append(
                etcd_client.read(
                    "{}/read/1".format(prefix),
                    wait=True,
                    timeout=30,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_3, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/read/1".format(prefix), "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == "{}/read/1".format(prefix)
        assert modified.value == "one"

    # Wait for an update after last modification, recursively
    with subtests.test("nested updates after index should be catchable"):
        return_list = []
        last_modified = modified.modifiedIndex if use_v2 else modified.mod_revision

        def wait_func_4(return_list):
            return_list.append(
                etcd_client.read(
                    "{}/read".format(prefix),
                    wait=True,
                    timeout=30,
                    recurse=True,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_4, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/read/1".format(prefix), "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == "{}/read/1".format(prefix)
        assert modified.value == "one"


def test_update(subtests, etcd_client, prefix):
    """
    Ensure that we can update fields
    """
    etcd_client.set("{}/read/1".format(prefix), "one")
    etcd_client.set("{}/read/2".format(prefix), "two")
    etcd_client.set("{}/read/3/4".format(prefix), "three/four")

    # Update existent fields
    with subtests.test("update should work on already existent field"):
        updated = {
            "{}/read/1".format(prefix): "not one",
            "{}/read/2".format(prefix): "not two",
        }
        assert etcd_client.update(updated) == updated
        assert etcd_client.get("{}/read/1".format(prefix)) == "not one"
        assert etcd_client.get("{}/read/2".format(prefix)) == "not two"

    # Update non-existent fields
    with subtests.test("update should work on non-existent fields"):
        updated = {
            prefix: {
                "read-2": "read-2",
                "read-3": "read-3",
                "read-4": {
                    "sub-4": "subvalue-1",
                    "sub-4-2": "subvalue-2",
                },
            }
        }

        assert etcd_client.update(updated) == etcd_client._flatten(updated)
        assert etcd_client.get("{}/read-2".format(prefix)) == "read-2"
        assert etcd_client.get("{}/read-3".format(prefix)) == "read-3"
        assert (
            etcd_client.get("{}/read-4".format(prefix), recurse=True)
            == updated[prefix]["read-4"]
        )

    with subtests.test("we should be able to prepend a path within update"):
        updated = {
            "1": "path updated one",
            "2": "path updated two",
        }
        expected_return = {
            "{}/read/1".format(prefix): "path updated one",
            "{}/read/2".format(prefix): "path updated two",
        }
        assert (
            etcd_client.update(updated, path="{}/read".format(prefix))
            == expected_return
        )
        assert etcd_client.get("{}/read/1".format(prefix)) == "path updated one"
        assert etcd_client.get("{}/read/2".format(prefix)) == "path updated two"


def test_write_file(subtests, etcd_client, prefix):
    """
    Test solely writing files
    """
    with subtests.test(
        "we should be able to write a single value for a non-existent key"
    ):
        assert (
            etcd_client.write_file("{}/write/key_1".format(prefix), "value_1")
            == "value_1"
        )
        assert etcd_client.get("{}/write/key_1".format(prefix)) == "value_1"

    with subtests.test("we should be able to write a single value for an existent key"):
        assert (
            etcd_client.write_file("{}/write/key_1".format(prefix), "new_value_1")
            == "new_value_1"
        )
        assert etcd_client.get("{}/write/key_1".format(prefix)) == "new_value_1"

    with subtests.test("we should be able to write a single value with a ttl"):
        assert (
            etcd_client.write_file(
                "{}/write/ttl_key".format(prefix), "new_value_2", ttl=5
            )
            == "new_value_2"
        )
        time.sleep(10)
        assert etcd_client.get("{}/write/ttl_key".format(prefix)) is None


def test_write_directory(subtests, etcd_client, prefix, use_v2):
    """
    Test solely writing directories
    """
    if not use_v2:
        pytest.skip("write_directory is not defined for etcd v3")

    with subtests.test("we should be able to create a non-existent directory"):
        assert etcd_client.write_directory("{}/write_dir/dir1".format(prefix), None)
        assert etcd_client.get("{}/write_dir/dir1".format(prefix)) is None

    with subtests.test("writing an already existent directory should return True"):
        assert etcd_client.write_directory("{}/write_dir/dir1".format(prefix), None)
        assert etcd_client.get("{}/write_dir/dir1".format(prefix)) is None

    with subtests.test("we should be able to write to a new directory"):
        assert (
            etcd_client.write_file("{}/write_dir/dir1/key1".format(prefix), "value1")
            == "value1"
        )
        assert etcd_client.get("{}/write_dir/dir1/key1".format(prefix)) == "value1"


def test_ls(subtests, etcd_client, prefix, use_v2):
    """
    Test listing top level contents
    """
    with subtests.test("ls on a non-existent directory should return an empty dict"):
        assert not etcd_client.ls("{}/ls".format(prefix))

    with subtests.test(
        "ls should list the top level keys and values at the given path"
    ):
        etcd_client.set("{}/ls/1".format(prefix), "one")
        etcd_client.set("{}/ls/2".format(prefix), "two")
        etcd_client.set("{}/ls/3/4".format(prefix), "three/four")

        # If it's a dir, it's suffixed with a slash
        expected = {
            "{}/ls".format(prefix): {
                "{}/ls/1".format(prefix): "one",
                "{}/ls/2".format(prefix): "two",
                "{}/ls/3/".format(prefix): {},
            },
        }

        assert etcd_client.ls("{}/ls".format(prefix)) == expected


@pytest.mark.parametrize("func", ("rm", "delete"))
def test_rm_and_delete(subtests, etcd_client, prefix, func, use_v2):
    """
    Ensure we can remove keys using rm
    """
    func = getattr(etcd_client, func)

    with subtests.test("removing a non-existent key should do nothing"):
        assert func("{}/rm/key1".format(prefix)) is None

    with subtests.test("we should be able to remove an existing key"):
        etcd_client.set("{}/rm/key1".format(prefix), "value1")
        assert func("{}/rm/key1".format(prefix))
        assert etcd_client.get("{}/rm/key1".format(prefix)) is None

    with subtests.test("we should be able to remove an empty directory"):
        if use_v2:
            etcd_client.write_directory("{}/rm/dir1".format(prefix), None)
            assert func("{}/rm/dir1".format(prefix), recurse=True)
            assert etcd_client.get("{}/rm/dir1".format(prefix), recurse=True) is None

    with subtests.test("we should be able to remove a directory with keys"):
        updated = {
            "dir1": {
                "rm-1": "value-1",
                "rm-2": {
                    "sub-rm-1": "subvalue-1",
                    "sub-rm-2": "subvalue-2",
                },
            }
        }
        etcd_client.update(updated, path="{}/rm".format(prefix))

        assert func("{}/rm/dir1".format(prefix), recurse=True)
        assert etcd_client.get("{}/rm/dir1".format(prefix), recurse=True) is None
        assert etcd_client.get("{}/rm/dir1/rm-1".format(prefix), recurse=True) is None

    with subtests.test("removing a directory without recursion should do nothing"):
        updated = {
            "dir1": {
                "rm-1": "value-1",
                "rm-2": {
                    "sub-rm-1": "subvalue-1",
                    "sub-rm-2": "subvalue-2",
                },
            }
        }
        etcd_client.update(updated, path="{}/rm".format(prefix))

        assert func("{}/rm/dir1".format(prefix)) is None
        assert (
            etcd_client.get("{}/rm/dir1".format(prefix), recurse=True)
            == updated["dir1"]
        )
        assert etcd_client.get("{}/rm/dir1/rm-1".format(prefix)) == "value-1"


def test_tree(subtests, etcd_client, prefix, use_v2):
    """
    Tree should return a dictionary representing what is downstream of the prefix.
    """
    with subtests.test("the tree of a non-existent key should be None"):
        assert etcd_client.tree(prefix) is None

    with subtests.test("the tree of an file should be {key: value}"):
        etcd_client.set("{}/1".format(prefix), "one")
        assert etcd_client.tree("{}/1".format(prefix)) == {"1": "one"}

    with subtests.test("the tree of an empty directory should be empty"):
        if use_v2:
            etcd_client.write_directory("{}/2".format(prefix), None)
            assert etcd_client.tree("{}/2".format(prefix)) == {}

    with subtests.test("we should be able to recieve the tree of a directory"):
        etcd_client.set("{}/3/4".format(prefix), "three/four")
        expected = {
            "1": "one",
            "2": {},
            "3": {"4": "three/four"},
        }
        if not use_v2:
            expected.pop("2")
        assert etcd_client.tree(prefix) == expected

    with subtests.test("we should be able to recieve the tree of an outer directory"):
        etcd_client.set("{}/5/6/7".format(prefix), "five/six/seven")
        expected = {
            "6": {"7": "five/six/seven"},
        }
        assert etcd_client.tree("{}/5".format(prefix)) == expected


def test_watch(subtests, etcd_client, prefix, use_v2):
    updated = {
        "1": "one",
        "2": "two",
        "3": {
            "4": "three/four",
        },
    }
    etcd_client.update(updated, path="{}/watch".format(prefix))

    with subtests.test(
        "watching an invalid key should timeout and return an empty dict"
    ):
        assert etcd_client.watch("{}/invalid".format(prefix), timeout=3) == {}

    with subtests.test(
        "watching an valid key with no changes should timeout and return an empty dict"
    ):
        assert etcd_client.watch("{}/watch/1".format(prefix), timeout=3) == {}

    # Wait for an update
    with subtests.test("updates should be able to be caught by waiting in read"):
        return_list = []

        def wait_func(return_list):
            return_list.append(
                etcd_client.watch("{}/watch/1".format(prefix), timeout=30)
            )

        wait_thread = threading.Thread(target=wait_func, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/watch/1".format(prefix), "not one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == "{}/watch/1".format(prefix)
        assert modified["value"] == "not one"

    # Wait for an update using recursive
    with subtests.test("nested updates should be catchable"):
        return_list = []

        def wait_func_2(return_list):
            return_list.append(
                etcd_client.watch("{}/watch".format(prefix), timeout=30, recurse=True)
            )

        wait_thread = threading.Thread(target=wait_func_2, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/watch/1".format(prefix), "one again!")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == "{}/watch/1".format(prefix)
        assert modified["value"] == "one again!"

    # Wait for an update after last modification
    with subtests.test(
        "updates should be able to be caught after an index by waiting in read"
    ):
        return_list = []
        last_modified = modified["mIndex"]

        def wait_func_3(return_list):
            return_list.append(
                etcd_client.watch(
                    "{}/watch/1".format(prefix),
                    timeout=30,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_3, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/watch/1".format(prefix), "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == "{}/watch/1".format(prefix)
        assert modified["value"] == "one"

    # Wait for an update after last modification, recursively
    with subtests.test("nested updates after index should be catchable"):
        return_list = []
        last_modified = modified["mIndex"]

        def wait_func_4(return_list):
            return_list.append(
                etcd_client.watch(
                    "{}/watch".format(prefix),
                    timeout=30,
                    recurse=True,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_4, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set("{}/watch/1".format(prefix), "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == "{}/watch/1".format(prefix)
        assert modified["value"] == "one"

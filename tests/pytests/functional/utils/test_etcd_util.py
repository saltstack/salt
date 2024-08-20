import copy
import logging
import threading
import time

import pytest

from salt.utils.etcd_util import EtcdClient, EtcdClientV3, get_conn
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


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


def test_etcd_client_creation(minion_opts, profile_name, etcd_version):
    """
    Client creation using client classes, just need to assert no errors.
    """
    if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
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
    assert not etcd_client.get(f"{prefix}/mtg/ambush")
    assert etcd_client.set(f"{prefix}/mtg/ambush", "viper") == "viper"
    assert etcd_client.get(f"{prefix}/mtg/ambush") == "viper"
    assert etcd_client.set(f"{prefix}/mtg/counter", "spell") == "spell"
    assert etcd_client.tree(f"{prefix}/mtg") == {
        "ambush": "viper",
        "counter": "spell",
    }
    assert etcd_client.ls(f"{prefix}/mtg") == {
        f"{prefix}/mtg": {
            f"{prefix}/mtg/ambush": "viper",
            f"{prefix}/mtg/counter": "spell",
        },
    }
    assert etcd_client.delete(f"{prefix}/mtg/ambush")
    assert etcd_client.delete(f"{prefix}/mtg", recurse=True)
    assert not etcd_client.get(f"{prefix}/mtg", recurse=True)


def test_simple_operations_with_raw_keys_and_values(
    minion_opts, profile_name, prefix, etcd_version
):
    if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
        pytest.skip("Not testing with raw keys using v2")
    modified_opts = copy.deepcopy(minion_opts)
    modified_opts[profile_name]["etcd.raw_keys"] = True
    modified_opts[profile_name]["etcd.raw_values"] = True
    etcd_client = get_conn(modified_opts, profile=profile_name)
    assert not etcd_client.get(f"{prefix}/mtg/ambush")
    assert etcd_client.set(f"{prefix}/mtg/ambush", "viper") == b"viper"
    assert etcd_client.get(f"{prefix}/mtg/ambush") == b"viper"
    assert etcd_client.set(f"{prefix}/mtg/counter", "spell") == b"spell"
    assert etcd_client.tree(f"{prefix}/mtg") == {
        b"ambush": b"viper",
        b"counter": b"spell",
    }
    assert etcd_client.ls(f"{prefix}/mtg") == {
        f"{prefix}/mtg".encode(): {
            f"{prefix}/mtg/ambush".encode(): b"viper",
            f"{prefix}/mtg/counter".encode(): b"spell",
        },
    }
    assert etcd_client.delete(f"{prefix}/mtg/ambush")
    assert etcd_client.delete(f"{prefix}/mtg", recurse=True)
    assert not etcd_client.get(f"{prefix}/mtg", recurse=True)


def test_get(subtests, etcd_client, prefix):
    """
    Test that get works as intended.
    """

    # Test general get case with key=value
    with subtests.test("inserted keys should be able to be retrieved"):
        etcd_client.set(f"{prefix}/get-test/key", "value")
        assert etcd_client.get(f"{prefix}/get-test/key") == "value"

    # Test with recurse=True.
    with subtests.test("keys should be able to be retrieved recursively"):
        etcd_client.set(f"{prefix}/get-test/key2/subkey", "subvalue")
        etcd_client.set(f"{prefix}/get-test/key2/subkey2/1", "subvalue1")
        etcd_client.set(f"{prefix}/get-test/key2/subkey2/2", "subvalue2")

        expected = {
            "subkey": "subvalue",
            "subkey2": {
                "1": "subvalue1",
                "2": "subvalue2",
            },
        }

        assert etcd_client.get(f"{prefix}/get-test/key2", recurse=True) == expected


def test_read(subtests, etcd_client, prefix, etcd_version):
    """
    Test that we are able to read and wait.
    """
    etcd_client.set(f"{prefix}/read/1", "one")
    etcd_client.set(f"{prefix}/read/2", "two")
    etcd_client.set(f"{prefix}/read/3/4", "three/four")

    # Simple read test
    with subtests.test(
        "reading a newly inserted and existent key should return that key"
    ):
        result = etcd_client.read(f"{prefix}/read/1")
        assert result
        if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
            assert result.value == "one"
        else:
            assert result.pop().value == "one"

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
            path=f"{prefix}/read",
        )

        result = etcd_client.read(f"{prefix}/read", recurse=True)
        assert result
        if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
            assert result.children
        else:
            assert len(result) > 1

        result_dict = {}
        if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
            for child in result.children:
                result_dict[child.key] = child.value
        else:
            for child in result:
                if child.key != f"{prefix}/read":
                    result_dict[child.key] = child.value
        assert result_dict == expected

    # Wait for an update
    with subtests.test("updates should be able to be caught by waiting in read"):
        return_list = []

        def wait_func(return_list):
            return_list.append(
                etcd_client.read(f"{prefix}/read/1", wait=True, timeout=30)
            )

        wait_thread = threading.Thread(target=wait_func, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/read/1", "not one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == f"{prefix}/read/1"
        assert modified.value == "not one"

    # Wait for an update using recursive
    with subtests.test("nested updates should be catchable"):
        return_list = []

        def wait_func_2(return_list):
            return_list.append(
                etcd_client.read(f"{prefix}/read", wait=True, timeout=30, recurse=True)
            )

        wait_thread = threading.Thread(target=wait_func_2, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/read/1", "one again!")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == f"{prefix}/read/1"
        assert modified.value == "one again!"

    # Wait for an update after last modification
    with subtests.test(
        "updates should be able to be caught after an index by waiting in read"
    ):
        return_list = []
        if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
            last_modified = modified.modifiedIndex
        else:
            last_modified = modified.mod_revision

        def wait_func_3(return_list):
            return_list.append(
                etcd_client.read(
                    f"{prefix}/read/1",
                    wait=True,
                    timeout=30,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_3, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/read/1", "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == f"{prefix}/read/1"
        assert modified.value == "one"

    # Wait for an update after last modification, recursively
    with subtests.test("nested updates after index should be catchable"):
        return_list = []
        if etcd_version in (EtcdVersion.v2, EtcdVersion.v3_v2_mode):
            last_modified = modified.modifiedIndex
        else:
            last_modified = modified.mod_revision

        def wait_func_4(return_list):
            return_list.append(
                etcd_client.read(
                    f"{prefix}/read",
                    wait=True,
                    timeout=30,
                    recurse=True,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_4, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/read/1", "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified.key == f"{prefix}/read/1"
        assert modified.value == "one"


def test_update(subtests, etcd_client, prefix):
    """
    Ensure that we can update fields
    """
    etcd_client.set(f"{prefix}/read/1", "one")
    etcd_client.set(f"{prefix}/read/2", "two")
    etcd_client.set(f"{prefix}/read/3/4", "three/four")

    # Update existent fields
    with subtests.test("update should work on already existent field"):
        updated = {
            f"{prefix}/read/1": "not one",
            f"{prefix}/read/2": "not two",
        }
        assert etcd_client.update(updated) == updated
        assert etcd_client.get(f"{prefix}/read/1") == "not one"
        assert etcd_client.get(f"{prefix}/read/2") == "not two"

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
        assert etcd_client.get(f"{prefix}/read-2") == "read-2"
        assert etcd_client.get(f"{prefix}/read-3") == "read-3"
        assert (
            etcd_client.get(f"{prefix}/read-4", recurse=True)
            == updated[prefix]["read-4"]
        )

    with subtests.test("we should be able to prepend a path within update"):
        updated = {
            "1": "path updated one",
            "2": "path updated two",
        }
        expected_return = {
            f"{prefix}/read/1": "path updated one",
            f"{prefix}/read/2": "path updated two",
        }
        assert etcd_client.update(updated, path=f"{prefix}/read") == expected_return
        assert etcd_client.get(f"{prefix}/read/1") == "path updated one"
        assert etcd_client.get(f"{prefix}/read/2") == "path updated two"


def test_write_file(subtests, etcd_client, prefix):
    """
    Test solely writing files
    """
    with subtests.test(
        "we should be able to write a single value for a non-existent key"
    ):
        assert etcd_client.write_file(f"{prefix}/write/key_1", "value_1") == "value_1"
        assert etcd_client.get(f"{prefix}/write/key_1") == "value_1"

    with subtests.test("we should be able to write a single value for an existent key"):
        assert (
            etcd_client.write_file(f"{prefix}/write/key_1", "new_value_1")
            == "new_value_1"
        )
        assert etcd_client.get(f"{prefix}/write/key_1") == "new_value_1"

    with subtests.test("we should be able to write a single value with a ttl"):
        assert (
            etcd_client.write_file(f"{prefix}/write/ttl_key", "new_value_2", ttl=5)
            == "new_value_2"
        )
        time.sleep(10)
        assert etcd_client.get(f"{prefix}/write/ttl_key") is None


def test_write_directory(subtests, etcd_client, prefix, etcd_version):
    """
    Test solely writing directories
    """
    if etcd_version != EtcdVersion.v2:
        pytest.skip("write_directory is not defined for etcd v3")

    with subtests.test("we should be able to create a non-existent directory"):
        assert etcd_client.write_directory(f"{prefix}/write_dir/dir1", None)
        assert etcd_client.get(f"{prefix}/write_dir/dir1") is None

    with subtests.test("writing an already existent directory should return True"):
        assert etcd_client.write_directory(f"{prefix}/write_dir/dir1", None)
        assert etcd_client.get(f"{prefix}/write_dir/dir1") is None

    with subtests.test("we should be able to write to a new directory"):
        assert (
            etcd_client.write_file(f"{prefix}/write_dir/dir1/key1", "value1")
            == "value1"
        )
        assert etcd_client.get(f"{prefix}/write_dir/dir1/key1") == "value1"


def test_ls(subtests, etcd_client, prefix):
    """
    Test listing top level contents
    """
    with subtests.test("ls on a non-existent directory should return an empty dict"):
        assert not etcd_client.ls(f"{prefix}/ls")

    with subtests.test(
        "ls should list the top level keys and values at the given path"
    ):
        etcd_client.set(f"{prefix}/ls/1", "one")
        etcd_client.set(f"{prefix}/ls/2", "two")
        etcd_client.set(f"{prefix}/ls/3/4", "three/four")

        # If it's a dir, it's suffixed with a slash
        expected = {
            f"{prefix}/ls": {
                f"{prefix}/ls/1": "one",
                f"{prefix}/ls/2": "two",
                f"{prefix}/ls/3/": {},
            },
        }

        assert etcd_client.ls(f"{prefix}/ls") == expected


@pytest.mark.parametrize("func", ("rm", "delete"))
def test_rm_and_delete(subtests, etcd_client, prefix, func, etcd_version):
    """
    Ensure we can remove keys using rm
    """
    func = getattr(etcd_client, func)

    with subtests.test("removing a non-existent key should do nothing"):
        assert func(f"{prefix}/rm/key1") is None

    with subtests.test("we should be able to remove an existing key"):
        etcd_client.set(f"{prefix}/rm/key1", "value1")
        assert func(f"{prefix}/rm/key1")
        assert etcd_client.get(f"{prefix}/rm/key1") is None

    with subtests.test("we should be able to remove an empty directory"):
        if etcd_version == EtcdVersion.v2:
            etcd_client.write_directory(f"{prefix}/rm/dir1", None)
            assert func(f"{prefix}/rm/dir1", recurse=True)
            assert etcd_client.get(f"{prefix}/rm/dir1", recurse=True) is None

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
        etcd_client.update(updated, path=f"{prefix}/rm")

        assert func(f"{prefix}/rm/dir1", recurse=True)
        assert etcd_client.get(f"{prefix}/rm/dir1", recurse=True) is None
        assert etcd_client.get(f"{prefix}/rm/dir1/rm-1", recurse=True) is None

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
        etcd_client.update(updated, path=f"{prefix}/rm")

        assert func(f"{prefix}/rm/dir1") is None
        assert etcd_client.get(f"{prefix}/rm/dir1", recurse=True) == updated["dir1"]
        assert etcd_client.get(f"{prefix}/rm/dir1/rm-1") == "value-1"


def test_tree(subtests, etcd_client, prefix, etcd_version):
    """
    Tree should return a dictionary representing what is downstream of the prefix.
    """
    with subtests.test("the tree of a non-existent key should be None"):
        assert etcd_client.tree(prefix) is None

    with subtests.test("the tree of an file should be {key: value}"):
        etcd_client.set(f"{prefix}/1", "one")
        assert etcd_client.tree(f"{prefix}/1") == {"1": "one"}

    with subtests.test("the tree of an empty directory should be empty"):
        if etcd_version == EtcdVersion.v2:
            etcd_client.write_directory(f"{prefix}/2", None)
            assert etcd_client.tree(f"{prefix}/2") == {}

    with subtests.test("we should be able to recieve the tree of a directory"):
        etcd_client.set(f"{prefix}/3/4", "three/four")
        expected = {
            "1": "one",
            "2": {},
            "3": {"4": "three/four"},
        }
        if etcd_version != EtcdVersion.v2:
            expected.pop("2")
        assert etcd_client.tree(prefix) == expected

    with subtests.test("we should be able to recieve the tree of an outer directory"):
        etcd_client.set(f"{prefix}/5/6/7", "five/six/seven")
        expected = {
            "6": {"7": "five/six/seven"},
        }
        assert etcd_client.tree(f"{prefix}/5") == expected


def test_watch(subtests, etcd_client, prefix):
    updated = {
        "1": "one",
        "2": "two",
        "3": {
            "4": "three/four",
        },
    }
    etcd_client.update(updated, path=f"{prefix}/watch")

    with subtests.test("watching an invalid key should timeout and return None"):
        assert etcd_client.watch(f"{prefix}/invalid", timeout=3) is None

    with subtests.test(
        "watching an valid key with no changes should timeout and return None"
    ):
        assert etcd_client.watch(f"{prefix}/watch/1", timeout=3) is None

    # Wait for an update
    with subtests.test("updates should be able to be caught by waiting in read"):
        return_list = []

        def wait_func(return_list):
            return_list.append(etcd_client.watch(f"{prefix}/watch/1", timeout=30))

        wait_thread = threading.Thread(target=wait_func, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/watch/1", "not one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == f"{prefix}/watch/1"
        assert modified["value"] == "not one"

    # Wait for an update using recursive
    with subtests.test("nested updates should be catchable"):
        return_list = []

        def wait_func_2(return_list):
            return_list.append(
                etcd_client.watch(f"{prefix}/watch", timeout=30, recurse=True)
            )

        wait_thread = threading.Thread(target=wait_func_2, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/watch/1", "one again!")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == f"{prefix}/watch/1"
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
                    f"{prefix}/watch/1",
                    timeout=30,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_3, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/watch/1", "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == f"{prefix}/watch/1"
        assert modified["value"] == "one"

    # Wait for an update after last modification, recursively
    with subtests.test("nested updates after index should be catchable"):
        return_list = []
        last_modified = modified["mIndex"]

        def wait_func_4(return_list):
            return_list.append(
                etcd_client.watch(
                    f"{prefix}/watch",
                    timeout=30,
                    recurse=True,
                    start_revision=last_modified + 1,
                )
            )

        wait_thread = threading.Thread(target=wait_func_4, args=(return_list,))
        wait_thread.start()
        time.sleep(1)
        etcd_client.set(f"{prefix}/watch/1", "one")
        wait_thread.join()
        modified = return_list.pop()
        assert modified["key"] == f"{prefix}/watch/1"
        assert modified["value"] == "one"

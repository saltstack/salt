"""
    Test cases for salt.returners.etcd_return

    :codeauthor: Caleb Beard <calebb@vmware.com>
"""

import copy

import pytest

import salt.returners.etcd_return as etcd_return
import salt.utils.etcd_util as etcd_util
import salt.utils.jid
import salt.utils.json
from tests.support.mock import MagicMock, call, create_autospec, patch


@pytest.fixture
def instance():
    return create_autospec(etcd_util.EtcdBase)


@pytest.fixture
def etcd_client_mock(instance):
    mocked_client = MagicMock()
    mocked_client.return_value = instance
    return mocked_client


@pytest.fixture
def profile_name():
    return "etcd_returner_profile"


@pytest.fixture
def returner_root():
    return "/salt/test-return"


@pytest.fixture
def etcd_config(profile_name, returner_root):
    return {
        profile_name: {
            "etcd.host": "127.0.0.1",
            "etcd.port": 2379,
        },
        "etcd.returner": profile_name,
        "etcd.returner_root": returner_root,
    }


@pytest.fixture
def configure_loader_modules():
    return {
        etcd_return: {
            "__opts__": {},
        },
    }


def test__get_conn(etcd_client_mock, profile_name, returner_root, instance):
    """
    Test the _get_conn utility function in etcd_return
    """
    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock):
        # Test to make sure we get the right path back
        config = {
            profile_name: {"etcd.host": "127.0.0.1", "etcd.port": 2379},
            "etcd.returner": profile_name,
            "etcd.returner_root": returner_root,
        }
        assert etcd_return._get_conn(config, profile=profile_name) == (
            instance,
            returner_root,
        )

        # Test to make sure we get the default path back if none in opts
        config = {
            profile_name: {"etcd.host": "127.0.0.1", "etcd.port": 2379},
            "etcd.returner": profile_name,
        }
        assert etcd_return._get_conn(config, profile=profile_name) == (
            instance,
            "/salt/return",
        )


def test_returner(etcd_client_mock, instance, returner_root, profile_name, etcd_config):
    """
    Test the returner function in etcd_return
    """
    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock):
        ret = {
            "id": "test-id",
            "jid": "123456789",
            "single-key": "single-value",
            "dict-key": {
                "dict-subkey-1": "subvalue-1",
                "dict-subkey-2": "subvalue-2",
            },
        }

        # Test returner with ttl in etcd config
        config = copy.deepcopy(etcd_config)
        config[profile_name]["etcd.ttl"] = 5
        config["etcd.returner_write_profile"] = profile_name

        with patch.dict(etcd_return.__opts__, config):
            assert etcd_return.returner(ret) is None
            dest = "/".join((returner_root, "jobs", ret["jid"], ret["id"], "{}"))
            calls = [
                call("/".join((returner_root, "minions", ret["id"])), ret["jid"], ttl=5)
            ] + [
                call(dest.format(key), salt.utils.json.dumps(ret[key]), ttl=5)
                for key in ret
            ]
            instance.set.assert_has_calls(calls, any_order=True)

        # Test returner with ttl in top level config
        config = copy.deepcopy(etcd_config)
        config["etcd.ttl"] = 6
        instance.set.reset_mock()
        with patch.dict(etcd_return.__opts__, config):
            assert etcd_return.returner(ret) is None
            dest = "/".join((returner_root, "jobs", ret["jid"], ret["id"], "{}"))
            calls = [
                call("/".join((returner_root, "minions", ret["id"])), ret["jid"], ttl=6)
            ] + [
                call(dest.format(key), salt.utils.json.dumps(ret[key]), ttl=6)
                for key in ret
            ]
            instance.set.assert_has_calls(calls, any_order=True)


def test_save_load(
    etcd_client_mock, instance, returner_root, profile_name, etcd_config
):
    """
    Test the save_load function in etcd_return
    """
    load = {
        "single-key": "single-value",
        "dict-key": {
            "dict-subkey-1": "subvalue-1",
            "dict-subkey-2": "subvalue-2",
        },
    }
    jid = "23"

    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock):
        # Test save_load with ttl in etcd config
        config = copy.deepcopy(etcd_config)
        config[profile_name]["etcd.ttl"] = 5
        config["etcd.returner_write_profile"] = profile_name

        with patch.dict(etcd_return.__opts__, config):
            assert etcd_return.save_load(jid, load) is None
            instance.set.assert_called_with(
                "/".join((returner_root, "jobs", jid, ".load.p")),
                salt.utils.json.dumps(load),
                ttl=5,
            )

        # Test save_load with ttl in top level config
        config = copy.deepcopy(etcd_config)
        config["etcd.ttl"] = 6
        with patch.dict(etcd_return.__opts__, config):
            assert etcd_return.save_load(jid, load) is None
            instance.set.assert_called_with(
                "/".join((returner_root, "jobs", jid, ".load.p")),
                salt.utils.json.dumps(load),
                ttl=6,
            )

            # Test save_load with minion kwarg, unused at the moment
            assert (
                etcd_return.save_load(jid, load, minions=("minion-1", "minion-2"))
                is None
            )
            instance.set.assert_called_with(
                "/".join((returner_root, "jobs", jid, ".load.p")),
                salt.utils.json.dumps(load),
                ttl=6,
            )


def test_get_load(etcd_client_mock, instance, returner_root, profile_name, etcd_config):
    """
    Test the get_load function in etcd_return
    """
    load = {
        "single-key": "single-value",
        "dict-key": {
            "dict-subkey-1": "subvalue-1",
            "dict-subkey-2": "subvalue-2",
        },
    }
    instance.get.return_value = salt.utils.json.dumps(load)
    jid = "23"

    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock):
        # Test get_load using etcd config
        config = copy.deepcopy(etcd_config)
        config["etcd.returner_read_profile"] = profile_name

        with patch.dict(etcd_return.__opts__, config):
            assert etcd_return.get_load(jid) == load
            instance.get.assert_called_with(
                "/".join((returner_root, "jobs", jid, ".load.p"))
            )

        # Test get_load using top level config profile name
        config = copy.deepcopy(etcd_config)
        with patch.dict(etcd_return.__opts__, config):
            assert etcd_return.get_load(jid) == load
            instance.get.assert_called_with(
                "/".join((returner_root, "jobs", jid, ".load.p"))
            )


def test_get_jid(etcd_client_mock, instance, returner_root, etcd_config):
    """
    Test the get_load function in etcd_return
    """
    jid = "10"

    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock), patch.dict(
        etcd_return.__opts__, etcd_config
    ):
        # Test that no value for jid returns an empty dict
        with patch.object(instance, "get", return_value={}):
            assert etcd_return.get_jid(jid) == {}
            instance.get.assert_called_with(
                "/".join((returner_root, "jobs", jid)), recurse=True
            )

        # Test that a jid with child values returns them
        retval = {
            "test-id-1": {
                "return": salt.utils.json.dumps("test-return-1"),
            },
            "test-id-2": {
                "return": salt.utils.json.dumps("test-return-2"),
            },
        }

        with patch.object(instance, "get", return_value=retval):
            # assert etcd_return.get_jid(jid) == {}
            assert etcd_return.get_jid(jid) == {
                "test-id-1": {"return": "test-return-1"},
                "test-id-2": {"return": "test-return-2"},
            }
            instance.get.assert_called_with(
                "/".join((returner_root, "jobs", jid)), recurse=True
            )


def test_get_fun(etcd_client_mock, instance, returner_root, etcd_config):
    """
    Test the get_fun function in etcd_return
    """
    fun = "test.ping"

    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock), patch.dict(
        etcd_return.__opts__, etcd_config
    ):
        # Test that no value for jid returns an empty dict
        with patch.object(instance, "get", return_value={}):
            assert etcd_return.get_fun(fun) == {}
            instance.get.assert_called_with(
                "/".join((returner_root, "minions")), recurse=True
            )

        # Test that a jid with child values returns them
        side_effect = (
            {
                "id-1": "1",
                "id-2": "2",
            },
            '"test.ping"',
            '"test.collatz"',
        )
        instance.get.reset_mock()

        with patch.object(instance, "get", side_effect=side_effect):
            # Could be either one depending on if Python<3.6
            retval = etcd_return.get_fun(fun)
            assert retval in [{"id-1": "test.ping"}, {"id-2": "test.ping"}]
            calls = [
                call("/".join((returner_root, "minions")), recurse=True),
                call("/".join((returner_root, "jobs", "1", "id-1", "fun"))),
                call("/".join((returner_root, "jobs", "2", "id-2", "fun"))),
            ]
            instance.get.assert_has_calls(calls, any_order=True)


def test_get_jids(etcd_client_mock, instance, returner_root, etcd_config):
    """
    Test the get_jids function in etcd_return
    """
    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock), patch.dict(
        etcd_return.__opts__, etcd_config
    ):
        # Test that no value for jids returns an empty dict
        with patch.object(instance, "get", return_value={}):
            assert etcd_return.get_jids() == []
            instance.get.assert_called_with(
                "/".join((returner_root, "jobs")), recurse=True
            )

        # Test that having child job values returns them
        children = {
            "123": {},
            "456": "not a dictionary",
            "789": {},
        }

        with patch.object(instance, "get", return_value=children):
            retval = etcd_return.get_jids()
            assert len(retval) == 2
            assert "123" in retval
            assert "789" in retval
            instance.get.assert_called_with(
                "/".join((returner_root, "jobs")), recurse=True
            )


def test_get_minions(etcd_client_mock, instance, returner_root, etcd_config):
    """
    Test the get_minions function in etcd_return
    """
    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock), patch.dict(
        etcd_return.__opts__, etcd_config
    ):
        # Test that no minions returns an empty dict
        with patch.object(instance, "get", return_value={}):
            assert etcd_return.get_minions() == []
            instance.get.assert_called_with(
                "/".join((returner_root, "minions")), recurse=True
            )

        # Test that having child minion values returns them
        children = {
            "id-1": "ignored-jid-1",
            "id-2": "ignored-jid-2",
        }
        with patch.object(instance, "get", return_value=children):
            retval = etcd_return.get_minions()
            assert len(retval) == 2
            assert "id-1" in retval
            assert "id-2" in retval
            instance.get.assert_called_with(
                "/".join((returner_root, "minions")), recurse=True
            )


def test_prep_jid():
    # Test that it returns a passed_jid if available
    assert etcd_return.prep_jid(passed_jid="23") == "23"

    # Test that giving `nocache` a value does nothing extra
    assert etcd_return.prep_jid(nocache=True, passed_jid="23") == "23"

    with patch.object(salt.utils.jid, "gen_jid", return_value="10"):
        assert etcd_return.prep_jid() == "10"

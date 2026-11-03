"""Configuration fixtures must not depend on discovering the host identity."""

import salt.config
from tests.pytests.functional.loader import test_loaded_base_name as loader_tests
from tests.support.mock import patch


def test_master_opts_does_not_discover_host_id(request):
    with patch(
        "salt.utils.network.generate_minion_id",
        side_effect=AssertionError("Unexpected host ID discovery"),
    ):
        opts = request.getfixturevalue("master_opts")
        # These are the reload paths used by nested clients and MasterMinion.
        assert salt.config.client_config(opts["conf_file"])["id"] == opts["id"]
        assert (
            salt.config.minion_config(opts["conf_file"], role="master")["id"]
            == opts["id"]
        )
    assert opts["id"]


def test_loader_opts_does_not_discover_host_id():
    with patch(
        "salt.utils.network.generate_minion_id",
        side_effect=AssertionError("Unexpected host ID discovery"),
    ):
        # Exercise this factory without the functional suite's unrelated
        # autouse loaders and grains collection.
        opts = loader_tests.opts.__wrapped__("fixture-id-test")
    assert opts["id"]

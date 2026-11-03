"""Configuration fixtures must not depend on discovering the host identity."""

from tests.pytests.functional.loader import test_loaded_base_name as loader_tests
from tests.support.mock import patch


def test_master_opts_does_not_discover_host_id(request):
    with patch(
        "salt.utils.network.generate_minion_id",
        side_effect=AssertionError("Unexpected host ID discovery"),
    ):
        opts = request.getfixturevalue("master_opts")
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

import pytest
import salt.modules.pcs as pcs
from tests.support.mock import MagicMock, patch


class TestData:
    def __init__(self):
        self.nodea = "nodea"
        self.nodeb = "nodeb"
        self.nodes = [self.nodea, self.nodeb]
        self.extra_args = ["test", "extra", "args"]
        self.cluster_name = "testcluster"


@pytest.fixture
def test_data():
    return TestData()


@pytest.fixture
def configure_loader_modules():
    return {
        pcs: {"__salt__": {"pkg.version": MagicMock()}},
    }


@pytest.mark.parametrize("ver_cmp_ret,old_ver", [(1, False), (0, True)])
def test_cluster_setup(ver_cmp_ret, old_ver, test_data):
    """
    Test for seting up a cluster
    """
    exp_cmd = ["pcs", "cluster", "setup"]
    if old_ver:
        exp_cmd.append("--name")
    exp_cmd = (
        exp_cmd + [test_data.cluster_name] + test_data.nodes + test_data.extra_args
    )

    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__,
        {
            "cmd.run_all": mock_cmd,
            "pkg.version_cmp": MagicMock(return_value=ver_cmp_ret),
        },
    )
    with patch_salt:
        pcs.cluster_setup(
            test_data.nodes, test_data.cluster_name, extra_args=test_data.extra_args
        )
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


def test_cluster_node_add(test_data):
    """
    Test for adding a cluster
    """
    exp_cmd = ["pcs", "cluster", "node", "add"]
    exp_cmd = exp_cmd + [test_data.nodea] + test_data.extra_args

    mock_cmd = MagicMock()
    patch_salt = patch.dict(pcs.__salt__, {"cmd.run_all": mock_cmd})
    with patch_salt:
        pcs.cluster_node_add(test_data.nodea, extra_args=test_data.extra_args)
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd

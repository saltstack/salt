import pytest

import salt.modules.pcs as pcs
from tests.support.mock import MagicMock, patch


class TstData:
    def __init__(self):
        self.nodea = "nodea"
        self.nodeb = "nodeb"
        self.nodes = [self.nodea, self.nodeb]
        self.extra_args = ["test", "extra", "args"]
        self.cluster_name = "testcluster"
        self.username = "hacluster"
        self.password = "hacluster"
        self.cib_filename = "/tmp/cib.xml"


@pytest.fixture
def test_data():
    return TstData()


@pytest.fixture
def configure_loader_modules():
    return {
        pcs: {"__salt__": {"pkg.version": MagicMock()}},
    }


@pytest.mark.parametrize("ver_cmp_ret,old_ver", [(1, False), (0, True)])
def test_auth(ver_cmp_ret, old_ver, test_data):
    """
    Test for authorising hosts on cluster
    """
    exp_cmd = ["pcs"]
    if old_ver:
        exp_cmd.extend(["cluster", "auth"])
    else:
        exp_cmd.extend(["host", "auth"])

    exp_cmd.extend(["-u", test_data.username, "-p", test_data.password])

    if old_ver:
        exp_cmd.extend(test_data.extra_args)

    exp_cmd.extend([test_data.nodea, test_data.nodeb])

    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__,
        {
            "cmd.run_all": mock_cmd,
            "pkg.version_cmp": MagicMock(return_value=ver_cmp_ret),
        },
    )

    with patch_salt:
        pcs.auth(
            test_data.nodes,
            pcsuser=test_data.username,
            pcspasswd=test_data.password,
            extra_args=test_data.extra_args,
        )
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


def test_is_auth_old(test_data):
    """
    Test for checking it nodes are authorised.
    """
    exp_cmd = ["pcs", "cluster", "auth"]
    exp_cmd.extend(test_data.nodes)
    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__,
        {"cmd.run_all": mock_cmd, "pkg.version_cmp": MagicMock(return_value=0)},
    )

    with patch_salt:
        pcs.is_auth(
            test_data.nodes, pcsuser=test_data.username, pcspasswd=test_data.password
        )
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


def test_is_auth(test_data):
    """
    Test for checking it nodes are authorised.
    """
    exp_cmd = [
        "pcs",
        "host",
        "auth",
        "-u",
        test_data.username,
        "-p",
        test_data.password,
    ]
    exp_cmd.extend(test_data.nodes)

    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__,
        {"cmd.run_all": mock_cmd, "pkg.version_cmp": MagicMock(return_value=1)},
    )

    with patch_salt:
        pcs.is_auth(
            test_data.nodes, pcsuser=test_data.username, pcspasswd=test_data.password
        )
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


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


def test_cluster_destroy(test_data):
    """
    Test for destroying a cluster
    """
    exp_cmd = ["pcs", "cluster", "destroy"]
    exp_cmd.extend(test_data.extra_args)

    mock_cmd = MagicMock()
    patch_salt = patch.dict(pcs.__salt__, {"cmd.run_all": mock_cmd})
    with patch_salt:
        pcs.cluster_destroy(extra_args=test_data.extra_args)
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


def test_cib_push(test_data):
    """
    Test for pushing a CIB file
    """
    exp_cmd = [
        "pcs",
        "cluster",
        "cib-push",
        test_data.cib_filename,
        "scope=configuration",
    ]
    exp_cmd.extend(test_data.extra_args)

    mock_cmd = MagicMock()
    patch_salt = patch.dict(pcs.__salt__, {"cmd.run_all": mock_cmd})
    with patch_salt:
        pcs.cib_push(
            test_data.cib_filename,
            scope="configuration",
            extra_args=test_data.extra_args,
        )
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


@pytest.mark.parametrize("ver_cmp_ret,old_ver", [(1, False), (0, True)])
def test_item_show_config_defaults(ver_cmp_ret, old_ver, test_data):
    """
    Test for item show
    """
    exp_cmd = ["pcs", "resource"]
    if old_ver:
        exp_cmd.append("show")
    else:
        exp_cmd.append("config")

    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__,
        {
            "cmd.run_all": mock_cmd,
            "pkg.version_cmp": MagicMock(return_value=ver_cmp_ret),
        },
    )

    with patch_salt:
        pcs.item_show("resource")
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


@pytest.mark.parametrize("ver_cmp_ret,old_ver", [(1, False), (0, True)])
def test_item_show_set_itemid(ver_cmp_ret, old_ver, test_data):
    """
    Test for item show
    """
    exp_cmd = ["pcs", "resource"]
    if old_ver:
        exp_cmd.extend(["show", "itemid"])
    else:
        exp_cmd.extend(["config", "itemid"])

    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__,
        {
            "cmd.run_all": mock_cmd,
            "pkg.version_cmp": MagicMock(return_value=ver_cmp_ret),
        },
    )

    with patch_salt:
        pcs.item_show("resource", "itemid")
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


def test_item_show_set_itemid_config():
    """
    Test for item show
    """
    exp_cmd = ["pcs", "config", "show", "item_id"]
    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__, {"cmd.run_all": mock_cmd, "pkg.version_cmp": MagicMock(1)}
    )

    with patch_salt:
        pcs.item_show("config", item_id="item_id", item_type="item_type")
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


def test_item_show_set_itemid_constraint():
    """
    Test for item show
    """
    exp_cmd = ["pcs", "constraint", "item_type", "show", "item_id", "--full"]

    mock_cmd = MagicMock()
    patch_salt = patch.dict(
        pcs.__salt__,
        {"cmd.run_all": mock_cmd, "pkg.version_cmp": MagicMock(1)},
    )

    with patch_salt:
        pcs.item_show("constraint", item_id="item_id", item_type="item_type")
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd


def test_item_create(test_data):
    """
    Test for item create
    """

    exp_cmd = [
        "pcs",
        "-f",
        test_data.cib_filename,
        "item",
        "create",
        "item_id",
        "item_type",
    ]
    exp_cmd.extend(test_data.extra_args)

    mock_cmd = MagicMock()
    patch_salt = patch.dict(pcs.__salt__, {"cmd.run_all": mock_cmd})
    with patch_salt:
        pcs.item_create(
            "item",
            "item_id",
            "item_type",
            create="create",
            extra_args=test_data.extra_args,
            cibfile=test_data.cib_filename,
        )
    assert mock_cmd.call_args_list[0][0][0] == exp_cmd

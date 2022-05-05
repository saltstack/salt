"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest
import salt.states.rabbitmq_cluster as rabbitmq_cluster
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rabbitmq_cluster: {}}


def test_joined():
    """
    Test to ensure the current node joined
    to a cluster with node user@host
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[["rahulha@salt"], [""], [""]])
    with patch.dict(rabbitmq_cluster.__salt__, {"rabbitmq.cluster_status": mock}):
        ret.update({"comment": "Already in cluster"})
        assert rabbitmq_cluster.joined("salt", "salt", "rahulha") == ret

        with patch.dict(rabbitmq_cluster.__opts__, {"test": True}):
            ret.update(
                {
                    "result": None,
                    "comment": "Node is set to join cluster rahulha@salt",
                    "changes": {"new": "rahulha@salt", "old": ""},
                }
            )
            assert rabbitmq_cluster.joined("salt", "salt", "rahulha") == ret

        with patch.dict(rabbitmq_cluster.__opts__, {"test": False}):
            mock = MagicMock(return_value={"Error": "ERR"})
            with patch.dict(rabbitmq_cluster.__salt__, {"rabbitmq.join_cluster": mock}):
                ret.update({"result": False, "comment": "ERR", "changes": {}})
                assert rabbitmq_cluster.joined("salt", "salt", "rahulha") == ret

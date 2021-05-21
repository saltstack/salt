"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.grafana as grafana
import salt.utils.json
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {grafana: {}}


def test_dashboard_present():
    """
    Test to ensure the grafana dashboard exists and is managed.
    """
    name = "myservice"
    rows = ["systemhealth", "requests", "title"]
    row = [{"panels": [{"id": "a"}], "title": "systemhealth"}]

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    comt1 = (
        "Dashboard myservice is set to be updated. The following rows "
        "set to be updated: {}".format(["systemhealth"])
    )
    pytest.raises(SaltInvocationError, grafana.dashboard_present, name, profile=False)

    pytest.raises(SaltInvocationError, grafana.dashboard_present, name, True, True)

    mock = MagicMock(
        side_effect=[
            {"hosts": True, "index": False},
            {"hosts": True, "index": True},
            {"hosts": True, "index": True},
            {"hosts": True, "index": True},
            {"hosts": True, "index": True},
            {"hosts": True, "index": True},
            {"hosts": True, "index": True},
        ]
    )
    mock_f = MagicMock(side_effect=[False, False, True, True, True, True])
    mock_t = MagicMock(return_value="")
    mock_i = MagicMock(return_value=False)
    source = {"dashboard": '["rows", {"rows":["baz", null, 1.0, 2]}]'}
    mock_dict = MagicMock(return_value={"_source": source})
    with patch.dict(
        grafana.__salt__,
        {
            "config.option": mock,
            "elasticsearch.exists": mock_f,
            "pillar.get": mock_t,
            "elasticsearch.get": mock_dict,
            "elasticsearch.index": mock_i,
        },
    ):
        pytest.raises(SaltInvocationError, grafana.dashboard_present, name)

        with patch.dict(grafana.__opts__, {"test": True}):
            pytest.raises(SaltInvocationError, grafana.dashboard_present, name)

            comt = "Dashboard {} is set to be created.".format(name)
            ret.update({"comment": comt})
            assert grafana.dashboard_present(name, True) == ret

            mock = MagicMock(
                return_value={"rows": [{"panels": "b", "title": "systemhealth"}]}
            )
            with patch.object(salt.utils.json, "loads", mock):
                ret.update({"comment": comt1, "result": None})
                assert grafana.dashboard_present(name, True, rows=row) == ret

        with patch.object(
            salt.utils.json, "loads", MagicMock(return_value={"rows": {}})
        ):
            pytest.raises(
                SaltInvocationError,
                grafana.dashboard_present,
                name,
                rows_from_pillar=rows,
            )

            comt = "Dashboard myservice is up to date"
            ret.update({"comment": comt, "result": True})
            assert grafana.dashboard_present(name, True) == ret

        mock = MagicMock(
            return_value={"rows": [{"panels": "b", "title": "systemhealth"}]}
        )
        with patch.dict(grafana.__opts__, {"test": False}):
            with patch.object(salt.utils.json, "loads", mock):
                comt = "Failed to update dashboard myservice."
                ret.update({"comment": comt, "result": False})
                assert grafana.dashboard_present(name, True, rows=row) == ret


def test_dashboard_absent():
    """
    Test to ensure the named grafana dashboard is deleted.
    """
    name = "myservice"

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(
        side_effect=[
            {"hosts": True, "index": False},
            {"hosts": True, "index": True},
            {"hosts": True, "index": True},
        ]
    )
    mock_f = MagicMock(side_effect=[True, False])
    with patch.dict(
        grafana.__salt__, {"config.option": mock, "elasticsearch.exists": mock_f}
    ):
        pytest.raises(SaltInvocationError, grafana.dashboard_absent, name)

        with patch.dict(grafana.__opts__, {"test": True}):
            comt = "Dashboard myservice is set to be removed."
            ret.update({"comment": comt, "result": None})
            assert grafana.dashboard_absent(name) == ret

        comt = "Dashboard myservice does not exist."
        ret.update({"comment": comt, "result": True})
        assert grafana.dashboard_absent(name) == ret

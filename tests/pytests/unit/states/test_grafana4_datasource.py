import pytest

import salt.states.grafana4_datasource as grafana4_datasource
from tests.support.mock import MagicMock, patch

profile = {
    "grafana_url": "http://grafana",
    "grafana_token": "token",
    "grafana_timeout": 3,
}


@pytest.fixture
def configure_loader_modules():
    return {grafana4_datasource: {"__opts__": {"test": False}}}


def _desired():
    """
    Build the datasource body exactly as present() does via _get_json_data,
    with all the keyword arguments present() forwards (Nones included).
    """
    return grafana4_datasource._get_json_data(
        name="test",
        type="prometheus",
        url="http://localhost:8080",
        access="proxy",
        user=None,
        password=None,
        database=None,
        basicAuth=None,
        basicAuthUser=None,
        basicAuthPassword=None,
        tlsAuth=None,
        jsonData=None,
        isDefault=False,
        withCredentials=None,
        typeLogoUrl=None,
    )


def _stored(**overrides):
    """
    Simulate what grafana4.get_datasource returns: the desired body plus the
    server-managed keys Grafana always adds (id, orgId, readOnly).
    """
    stored = _desired()
    stored.update({"id": 1, "orgId": 1, "readOnly": False})
    stored.update(overrides)
    return stored


def test_present_unchanged_test_mode_54122():
    """
    test=True must not report an update for an existing, unchanged datasource.

    Regression test for issue #54122: get_datasource returns server-managed
    keys (id, orgId, readOnly) that the desired body never carries, so the old
    "data == datasource" check was never True and test mode always claimed the
    datasource "will be updated" even though a live run made no changes.
    """
    stored = _stored()
    update = MagicMock()
    with patch.dict(
        grafana4_datasource.__salt__,
        {
            "grafana4.get_datasource": MagicMock(return_value=stored),
            "grafana4.update_datasource": update,
        },
    ), patch.dict(grafana4_datasource.__opts__, {"test": True}):
        ret = grafana4_datasource.present(
            "test",
            "prometheus",
            "http://localhost:8080",
            access="proxy",
            is_default=False,
            profile=profile,
        )
    assert ret["result"] is True
    assert ret["comment"] == "Data source test already up-to-date"
    assert ret["changes"] == {}
    update.assert_not_called()


def test_present_changed_test_mode():
    """
    Inverse / must-not-regress: a real change (url differs) must still be
    reported as pending under test=True, with result left as None and no
    live update performed. Passes with and without the #54122 fix.
    """
    stored = _stored(url="http://OLD:8080")
    update = MagicMock()
    with patch.dict(
        grafana4_datasource.__salt__,
        {
            "grafana4.get_datasource": MagicMock(return_value=stored),
            "grafana4.update_datasource": update,
        },
    ), patch.dict(grafana4_datasource.__opts__, {"test": True}):
        ret = grafana4_datasource.present(
            "test",
            "prometheus",
            "http://NEW:8080",
            access="proxy",
            is_default=False,
            profile=profile,
        )
    assert ret["result"] is None
    assert ret["comment"] == "Datasource test will be updated"
    update.assert_not_called()


def test_present_unchanged_live():
    """
    Live run (test=False) on an unchanged datasource must be a no-op: result
    True, empty changes, and update_datasource never invoked.
    """
    stored = _stored()
    update = MagicMock()
    with patch.dict(
        grafana4_datasource.__salt__,
        {
            "grafana4.get_datasource": MagicMock(return_value=stored),
            "grafana4.update_datasource": update,
        },
    ), patch.dict(grafana4_datasource.__opts__, {"test": False}):
        ret = grafana4_datasource.present(
            "test",
            "prometheus",
            "http://localhost:8080",
            access="proxy",
            is_default=False,
            profile=profile,
        )
    assert ret["result"] is True
    assert ret["comment"] == "Data source test already up-to-date"
    assert ret["changes"] == {}
    update.assert_not_called()


def test_present_changed_live():
    """
    Live run (test=False) with a real change updates the datasource: it calls
    update_datasource with the stored id, reports the diff in changes, and
    returns result True.
    """
    stored = _stored(url="http://OLD:8080")
    update = MagicMock()
    with patch.dict(
        grafana4_datasource.__salt__,
        {
            "grafana4.get_datasource": MagicMock(return_value=stored),
            "grafana4.update_datasource": update,
        },
    ), patch.dict(grafana4_datasource.__opts__, {"test": False}):
        ret = grafana4_datasource.present(
            "test",
            "prometheus",
            "http://NEW:8080",
            access="proxy",
            is_default=False,
            profile=profile,
        )
    assert ret["result"] is True
    assert ret["comment"] == "Data source test updated"
    assert ret["changes"] == {
        "old": {"url": "http://OLD:8080"},
        "new": {"url": "http://NEW:8080"},
    }
    update.assert_called_once()
    assert update.call_args[0][0] == 1


def test_present_absent_creates_in_test_mode():
    """
    Peripheral coverage: when the datasource does not exist yet, test mode
    reports creation and does not touch update_datasource.
    """
    create = MagicMock()
    update = MagicMock()
    with patch.dict(
        grafana4_datasource.__salt__,
        {
            "grafana4.get_datasource": MagicMock(return_value={}),
            "grafana4.create_datasource": create,
            "grafana4.update_datasource": update,
        },
    ), patch.dict(grafana4_datasource.__opts__, {"test": True}):
        ret = grafana4_datasource.present(
            "test",
            "prometheus",
            "http://localhost:8080",
            access="proxy",
            is_default=False,
            profile=profile,
        )
    assert ret["result"] is None
    assert ret["comment"] == "Datasource test will be created"
    create.assert_not_called()
    update.assert_not_called()

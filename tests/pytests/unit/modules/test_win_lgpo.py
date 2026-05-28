"""
Unit tests for salt.modules.win_lgpo
"""

import pytest

import salt.modules.win_lgpo as win_lgpo
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]

_ADML_TAG = "{http://www.microsoft.com/GroupPolicy/2006/07/PolicyDefinitions}string"


def _make_adml(policy_id):
    fake = MagicMock()
    fake.tag = _ADML_TAG
    fake.attrib = {"id": policy_id}
    return fake


def _make_admx(name):
    fake = MagicMock()
    fake.attrib = {"name": name, "class": "Machine"}
    return fake


def test_duplicate_policies_identical_paths_returns_success():
    """
    When multiple ADMX entries share the same display name but all resolve
    to the same full path (e.g. TerminalServer.admx and
    TerminalServer-Server.admx for "Do not allow Clipboard redirection"),
    _lookup_admin_template should return True with policy info rather than
    a "multiple policies" error.
    """
    policy_name = "Do not allow Clipboard redirection"
    policy_class = "Machine"

    fake_adml = _make_adml("TS_CLIENT_CLIPBOARD")
    fake_policy_1 = _make_admx("TS_CLIENT_CLIPBOARD")
    fake_policy_2 = _make_admx("TS_CLIENT_CLIPBOARD")

    # _build_parent_list returns innermost-first; the code reverses it
    # in-place, so return a fresh list on every call.
    shared_parent = [
        "Device and Resource Redirection",
        "Remote Desktop Session Host",
        "Remote Desktop Services",
        "Windows Components",
    ]

    with (
        patch.object(win_lgpo, "_get_policy_definitions", return_value=MagicMock()),
        patch.object(win_lgpo, "_get_policy_resources", return_value=MagicMock()),
        patch.object(win_lgpo, "ADMX_SEARCH_XPATH", MagicMock(return_value=[])),
        patch.object(
            win_lgpo,
            "ADML_SEARCH_XPATH",
            MagicMock(return_value=[fake_adml]),
        ),
        patch.object(
            win_lgpo,
            "ADMX_DISPLAYNAME_SEARCH_XPATH",
            MagicMock(return_value=[fake_policy_1, fake_policy_2]),
        ),
        patch.object(
            win_lgpo,
            "_build_parent_list",
            side_effect=lambda **_: list(shared_parent),
        ),
        patch.object(win_lgpo, "_getFullPolicyName", return_value=policy_name),
    ):
        found, policy_xml, aliases, msg = win_lgpo._lookup_admin_template(
            policy_name, policy_class
        )

    assert found is True
    assert msg is None
    assert policy_xml is fake_policy_1
    assert policy_name in aliases


def test_duplicate_policies_distinct_paths_returns_error():
    """
    When multiple ADMX entries share the same display name but resolve to
    genuinely different full paths (e.g. "Access data sources across
    domains" in multiple Internet Explorer sub-trees), _lookup_admin_template
    should still return False with the existing "multiple policies" error.
    """
    policy_name = "Access data sources across domains"
    policy_class = "Machine"

    fake_adml = _make_adml("SomePolicyId")
    fake_policy_1 = _make_admx("PolicyA")
    fake_policy_2 = _make_admx("PolicyB")

    parent_path_1 = ["Security Features", "Internet Explorer", "Windows Components"]
    parent_path_2 = [
        "Internet Control Panel",
        "Internet Explorer",
        "Windows Components",
    ]

    with (
        patch.object(win_lgpo, "_get_policy_definitions", return_value=MagicMock()),
        patch.object(win_lgpo, "_get_policy_resources", return_value=MagicMock()),
        patch.object(win_lgpo, "ADMX_SEARCH_XPATH", MagicMock(return_value=[])),
        patch.object(
            win_lgpo,
            "ADML_SEARCH_XPATH",
            MagicMock(return_value=[fake_adml]),
        ),
        patch.object(
            win_lgpo,
            "ADMX_DISPLAYNAME_SEARCH_XPATH",
            MagicMock(return_value=[fake_policy_1, fake_policy_2]),
        ),
        patch.object(
            win_lgpo,
            "_build_parent_list",
            side_effect=[list(parent_path_1), list(parent_path_2)],
        ),
        patch.object(win_lgpo, "_getFullPolicyName", return_value=policy_name),
    ):
        found, policy_xml, aliases, msg = win_lgpo._lookup_admin_template(
            policy_name, policy_class
        )

    assert found is False
    assert policy_xml is None
    assert aliases == []
    assert "multiple policies" in msg
    assert policy_name in msg

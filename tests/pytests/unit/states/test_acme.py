"""
:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
"""

import pytest

import salt.states.acme as acme
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {acme: {"__opts__": {"test": False}}}


def test_cert_no_changes_test():
    """
    Test cert state with no needed changes. (test=True)
    """
    with patch.dict(
        acme.__salt__,
        {
            "acme.has": MagicMock(return_value=True),
            "acme.needs_renewal": MagicMock(return_value=False),
        },
    ), patch.dict(acme.__opts__, {"test": True}):
        match = {
            "name": "test",
            "result": True,
            "comment": ["Certificate test exists and does not need renewal."],
            "changes": {},
        }
        assert acme.cert("test") == match
        assert acme.cert("testing.example.com", certname="test") == match


def test_cert_no_changes():
    """
    Test cert state with no needed changes. (test=False)
    """
    with patch.dict(
        acme.__salt__,
        {
            "acme.has": MagicMock(return_value=True),
            "acme.needs_renewal": MagicMock(return_value=False),
        },
    ):
        match = {
            "name": "test",
            "result": True,
            "comment": ["Certificate test exists and does not need renewal."],
            "changes": {},
        }
        assert acme.cert("test") == match
        assert acme.cert("testing.example.com", certname="test") == match


def test_cert_fresh_certificate_test():
    """
    Test cert state fetching a new certificate. (test=True)
    """
    # With test=True
    with patch.dict(
        acme.__salt__,
        {
            "acme.has": MagicMock(return_value=False),
            "acme.info": MagicMock(return_value={"foo": "bar"}),
        },
    ), patch.dict(acme.__opts__, {"test": True}):
        match = {
            "name": "test",
            "result": None,
            "comment": ["Certificate test would have been obtained."],
            "changes": {"old": "current certificate", "new": "new certificate"},
        }
        assert acme.cert("test") == match
        assert acme.cert("testing.example.com", certname="test") == match


def test_cert_fresh_certificate():
    """
    Test cert state fetching a new certificate. (test=False)
    """
    with patch.dict(
        acme.__salt__,
        {
            "acme.has": MagicMock(return_value=False),
            "acme.cert": MagicMock(return_value={"result": True, "comment": "Mockery"}),
            "acme.info": MagicMock(return_value={"foo": "bar"}),
        },
    ):
        match = {
            "name": "test",
            "result": True,
            "comment": ["Mockery"],
            "changes": {"new": {"foo": "bar"}},
        }
        assert acme.cert("test") == match
        assert acme.cert("testing.example.com", certname="test") == match


def test_cert_renew_certificate_test():
    """
    Test cert state renewing a certificate. (test=True)
    """
    with patch.dict(
        acme.__salt__,
        {
            "acme.has": MagicMock(return_value=True),
            "acme.needs_renewal": MagicMock(return_value=True),
            "acme.info": MagicMock(side_effect=[{"name": "old cert"}] * 2),
            "acme.cert": MagicMock(return_value={"result": True, "comment": "Mockery"}),
        },
    ), patch.dict(acme.__opts__, {"test": True}):
        match = {
            "name": "test",
            "result": None,
            "comment": ["Certificate test would have been renewed."],
            "changes": {"old": "current certificate", "new": "new certificate"},
        }
        assert acme.cert("test") == match
        assert acme.cert("testing.example.com", certname="test") == match


def test_cert_renew_certificate():
    """
    Test cert state renewing a certificate. (test=False)
    """
    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "acme.has": MagicMock(return_value=True),
            "acme.needs_renewal": MagicMock(return_value=True),
            "acme.info": MagicMock(
                side_effect=[{"name": "old cert"}, {"name": "new cert"}] * 2
            ),
            "acme.cert": MagicMock(return_value={"result": True, "comment": "Mockery"}),
        },
    ):
        match = {
            "name": "test",
            "result": True,
            "comment": ["Mockery"],
            "changes": {"old": {"name": "old cert"}, "new": {"name": "new cert"}},
        }
        assert acme.cert("test") == match
        assert acme.cert("testing.example.com", certname="test") == match

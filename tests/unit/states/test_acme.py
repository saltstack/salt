# -*- coding: utf-8 -*-
"""
:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
"""

# Import future libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Module
import salt.states.acme as acme

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class AcmeTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.acme
    """

    def setup_loader_modules(self):
        return {acme: {"__opts__": {"test": False}}}

    def test_cert_no_changes_t(self):
        """
        Test cert state with no needed changes. (test=True)
        """
        # With test=True
        with patch.dict(
            acme.__salt__,
            {  # pylint: disable=no-member
                "acme.has": MagicMock(return_value=True),
                "acme.needs_renewal": MagicMock(return_value=False),
            },
        ), patch.dict(
            acme.__opts__, {"test": True}
        ):  # pylint: disable=no-member
            self.assertEqual(
                acme.cert("test"),
                {
                    "name": "test",
                    "result": True,
                    "comment": ["Certificate test exists and does not need renewal."],
                    "changes": {},
                },
            )

    def test_cert_no_changes(self):
        """
        Test cert state with no needed changes. (test=False)
        """
        # With test=False
        with patch.dict(
            acme.__salt__,
            {  # pylint: disable=no-member
                "acme.has": MagicMock(return_value=True),
                "acme.needs_renewal": MagicMock(return_value=False),
            },
        ):
            self.assertEqual(
                acme.cert("test"),
                {
                    "name": "test",
                    "result": True,
                    "comment": ["Certificate test exists and does not need renewal."],
                    "changes": {},
                },
            )

    def test_cert_fresh_certificate_t(self):
        """
        Test cert state fetching a new certificate. (test=True)
        """
        # With test=True
        with patch.dict(
            acme.__salt__,
            {  # pylint: disable=no-member
                "acme.has": MagicMock(return_value=False),
                # 'acme.cert': MagicMock(return_value={'result': True, 'comment': 'Mockery'}),
                "acme.info": MagicMock(return_value={"foo": "bar"}),
            },
        ), patch.dict(
            acme.__opts__, {"test": True}
        ):  # pylint: disable=no-member
            self.assertEqual(
                acme.cert("test"),
                {
                    "name": "test",
                    "result": None,
                    "comment": ["Certificate test would have been obtained."],
                    "changes": {"old": "current certificate", "new": "new certificate"},
                },
            )

    def test_cert_fresh_certificate(self):
        """
        Test cert state fetching a new certificate. (test=False)
        """
        # With test=False
        with patch.dict(
            acme.__salt__,
            {  # pylint: disable=no-member
                "acme.has": MagicMock(return_value=False),
                "acme.cert": MagicMock(
                    return_value={"result": True, "comment": "Mockery"}
                ),
                "acme.info": MagicMock(return_value={"foo": "bar"}),
            },
        ):
            self.assertEqual(
                acme.cert("test"),
                {
                    "name": "test",
                    "result": True,
                    "comment": ["Mockery"],
                    "changes": {"new": {"foo": "bar"}},
                },
            )

    def test_cert_renew_certificate_t(self):
        """
        Test cert state renewing a certificate. (test=True)
        """
        with patch.dict(
            acme.__salt__,
            {  # pylint: disable=no-member
                "acme.has": MagicMock(return_value=True),
                "acme.needs_renewal": MagicMock(return_value=True),
                "acme.info": MagicMock(
                    side_effect=[{"name": "old cert"}, {"name": "new cert"}]
                ),
                "acme.cert": MagicMock(
                    return_value={"result": True, "comment": "Mockery"}
                ),
            },
        ), patch.dict(
            acme.__opts__, {"test": True}
        ):  # pylint: disable=no-member
            self.assertEqual(
                acme.cert("test"),
                {
                    "name": "test",
                    "result": None,
                    "comment": ["Certificate test would have been renewed."],
                    "changes": {"old": "current certificate", "new": "new certificate"},
                },
            )

    def test_cert_renew_certificate(self):
        """
        Test cert state renewing a certificate. (test=False)
        """
        with patch.dict(
            acme.__salt__,
            {  # pylint: disable=no-member
                "acme.has": MagicMock(return_value=True),
                "acme.needs_renewal": MagicMock(return_value=True),
                "acme.info": MagicMock(
                    side_effect=[{"name": "old cert"}, {"name": "new cert"}]
                ),
                "acme.cert": MagicMock(
                    return_value={"result": True, "comment": "Mockery"}
                ),
            },
        ):
            self.assertEqual(
                acme.cert("test"),
                {
                    "name": "test",
                    "result": True,
                    "comment": ["Mockery"],
                    "changes": {
                        "old": {"name": "old cert"},
                        "new": {"name": "new cert"},
                    },
                },
            )

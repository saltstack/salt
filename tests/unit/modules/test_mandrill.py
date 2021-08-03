"""
Tests for the Mandrill execution module.
"""


import salt.modules.mandrill as mandrill
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

# Test data
TEST_SEND = {
    "result": True,
    "comment": "",
    "out": [
        {
            "status": "sent",
            "_id": "c4353540a3c123eca112bbdd704ab6",
            "email": "recv@example.com",
            "reject_reason": None,
        }
    ],
}


class MandrillModuleTest(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.mandrill.
    """

    def setup_loader_modules(self):
        module_globals = {
            mandrill: {
                "__salt__": {
                    "config.merge": MagicMock(
                        return_value={"mandrill": {"key": "2orgk34kgk34g"}}
                    )
                }
            }
        }
        if mandrill.HAS_REQUESTS is False:
            module_globals["sys.modules"] = {"requests": MagicMock()}
        return module_globals

    def test_send(self):
        """
        Test the send function.
        """
        mock_cmd = MagicMock(return_value=TEST_SEND)
        with patch.object(mandrill, "send", mock_cmd) as send:
            self.assertEqual(
                send(
                    message={
                        "subject": "Hi",
                        "from_email": "test@example.com",
                        "to": [{"email": "recv@example.com", "type": "to"}],
                    }
                ),
                TEST_SEND,
            )

    def test_deprecation_58640(self):
        # check that type error will be raised
        message = {
            "subject": "Hi",
            "from_email": "test@example.com",
            "to": [{"email": "recv@example.com", "type": "to"}],
        }
        self.assertRaises(
            TypeError, mandrill.send, **{"message": message, "async": True}
        )

        # check that async will raise an error
        try:
            mandrill.send(  # pylint: disable=unexpected-keyword-arg
                **{"message": message, "async": True}
            )
        except TypeError as no_async:
            self.assertEqual(
                str(no_async),
                "send() got an unexpected keyword argument 'async'",
            )

# -*- coding: utf-8 -*-
# pylint: disable=confusing-with-statement
import salt.modules.boto_iam as boto_iam
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class TestBotoIam(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            boto_iam: {"_get_conn": None, "__utils__": {"boto.get_error": lambda x: x}}
        }

    def test_create_policy_version_should_return_error_if_policy_version_failed_to_create(
        self,
    ):
        expected_error = "This is some fako error message. Not real at all."
        patch_get_conn = patch.object(boto_iam, "_get_conn")
        patch_get_error = patch.dict(
            boto_iam.__utils__, {"boto.get_error": lambda x: expected_error}
        )
        with patch_get_conn as mock_conn, patch_get_error:
            mock_conn.return_value.create_policy_version.side_effect = boto_iam.boto.exception.BotoServerError(
                "fnord", "fnord"
            )

            result = boto_iam.create_policy_version(
                policy_name="fnord", policy_document=None
            )

            self.assertFalse(result["created"])
            self.assertEqual(result["error"], expected_error)

    def test_create_policy_version_should_return_provided_policy_name_and_resulting_vid(
        self,
    ):
        expected_version_id = 42
        patch_get_conn = patch.object(boto_iam, "_get_conn")
        with patch_get_conn as mock_conn:
            mock_conn.return_value.create_policy_version.return_value = {
                "create_policy_version_response": {
                    "create_policy_version_result": {
                        "policy_version": {"version_id": expected_version_id}
                    }
                }
            }

            result = boto_iam.create_policy_version(
                policy_name="fnord", policy_document=None
            )

            self.assertTrue(result["created"])
            self.assertEqual(result["version_id"], expected_version_id)

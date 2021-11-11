import salt.modules.boto_ssm as boto_ssm
from tests.support.mock import patch
from tests.support.unit import TestCase


class BotoSsmTestCase(TestCase):
    """
    TestCase for salt.modules.boto_ssm module
    """

    @patch("salt.utils.versions.check_boto_reqs")
    @patch("salt.utils.boto3mod.assign_funcs")
    def test___virtual__has_boto_reqs_true(self, mock_assign_funcs, mock_boto_reqs):
        mock_boto_reqs.return_value = True
        mock_assign_funcs.return_value = False
        result = boto_ssm.__virtual__()
        self.assertEqual(result, True)

    @patch("salt.utils.versions.check_boto_reqs")
    def test___virtual__has_boto_reqs_false(self, mock_boto_reqs):
        mock_boto_reqs.return_value = False
        result = boto_ssm.__virtual__()
        self.assertEqual(result, False)

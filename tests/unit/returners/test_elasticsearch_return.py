"""
Test the elasticsearch returner
"""
import salt.returners.elasticsearch_return as elasticsearch_return
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ElasticSearchReturnerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test the functions in the elasticsearch returner
    """

    def setup_loader_modules(self):
        return {elasticsearch_return: {}}

    def test__virtual_no_elasticsearch(self):
        """
        Test __virtual__ function when elasticsearch is not installed
        and the elasticsearch module is not available
        """
        result = elasticsearch_return.__virtual__()
        expected = (
            False,
            "Elasticsearch module not availble.  Check that the elasticsearch library"
            " is installed.",
        )
        self.assertEqual(expected, result)

    def test__virtual_with_elasticsearch(self):
        """
        Test __virtual__ function when elasticsearch
        and the elasticsearch module is not available
        """
        with patch.dict(
            elasticsearch_return.__salt__, {"elasticsearch.index_exists": MagicMock()}
        ):
            result = elasticsearch_return.__virtual__()
            expected = "elasticsearch"
            self.assertEqual(expected, result)

"""
Test the elasticsearch returner
"""

import pytest

import salt.returners.elasticsearch_return as elasticsearch_return
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {elasticsearch_return: {}}


def test__virtual_no_elasticsearch():
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
    assert expected == result


def test__virtual_with_elasticsearch():
    """
    Test __virtual__ function when elasticsearch
    and the elasticsearch module is not available
    """
    with patch.dict(
        elasticsearch_return.__salt__, {"elasticsearch.index_exists": MagicMock()}
    ):
        result = elasticsearch_return.__virtual__()
        expected = "elasticsearch"
        assert expected == result

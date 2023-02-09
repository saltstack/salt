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
        "Cannot load module elasticsearch: elasticsearch libraries not found",
    )
    assert expected == result


def test__virtual_with_elasticsearch():
    """
    Test __virtual__ function when elasticsearch
    and the elasticsearch module is not available
    """
    with patch.multiple(
        elasticsearch_return, HAS_ELASTICSEARCH=True, ES_MAJOR_VERSION=6
    ):
        with patch.dict(
            elasticsearch_return.__salt__, {"elasticsearch.index_exists": MagicMock()}
        ):
            result = elasticsearch_return.__virtual__()
            expected = "elasticsearch"
            assert expected == result

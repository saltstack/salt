import pytest

from tests.support.mock import Mock, call, patch

pytest.importorskip("mako")

# This import needs to be after the above importorskip so that no ImportError
# is raised if Mako is not installed
from salt.utils.mako import SaltMakoTemplateLookup


def test_mako_template_lookup(minion_opts):
    """
    The shudown method can be called without raising an exception when the
    file_client does not have a destroy method
    """
    # Test SaltCacheLoader creating and destroying the file client created
    file_client = Mock()
    with patch("salt.fileclient.get_file_client", return_value=file_client):
        loader = SaltMakoTemplateLookup(minion_opts)
        assert loader._file_client is None
        assert loader.file_client() is file_client
        assert loader._file_client is file_client
        try:
            loader.destroy()
        except AttributeError:
            pytest.fail("Regression when calling SaltMakoTemplateLookup.destroy()")
        assert file_client.mock_calls == [call.destroy()]

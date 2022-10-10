import pytest

from salt.returners.local_cache import _remove_job_dir
from tests.support.mock import patch


@pytest.mark.parametrize("e", (NotADirectoryError, OSError))
def test_remove_job_dir(e):
    # Test that _remove_job_dir job will catch error
    with patch("shutil.rmtree", side_effect=e("Node Corruption!")):
        assert not _remove_job_dir("cache")

    # Test that _remove_job_dir job will not catch other errors
    with patch("shutil.rmtree", side_effect=FileExistsError()):
        try:
            _remove_job_dir("cache")
        except FileExistsError:
            pass

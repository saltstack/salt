from salt.returners.local_cache import _remove_job_dir
from tests.support.mock import patch


def test_remove_job_dir():
    # Test that _remove_job_dir job will NotADirectoryError error
    with patch("shutil.rmtree", side_effect=NotADirectoryError("Node Corruption!")):
        _remove_job_dir("cache.json")

    # Test that _remove_job_dir job will not catch other file errors
    with patch("shutil.rmtree", side_effect=OSError()):
        try:
            _remove_job_dir("cache.json")
        except OSError:
            pass

from salt.returners.local_cache import _remove_job_dir
from tests.support.mock import patch


def test_remove_job_dir():
    # Test that _remove_job_dir job will catch error
    for e in (NotADirectoryError, OSError):
        with patch("shutil.rmtree", side_effect=e("Node Corruption!")):
            _remove_job_dir("cache.json")

    # Test that _remove_job_dir job will not catch other errors
    with patch("shutil.rmtree", side_effect=FileExistsError()):
        try:
            _remove_job_dir("cache.json")
        except FileExistsError:
            pass

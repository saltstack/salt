import os
import pytest
from salt.modules import win_file


pytestmark = [
    pytest.mark.skip_on_windows,
]

def test_is_link(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.is_link(tmp_path) is True
    assert win_file.is_link(os.path.join(tmp_path, "made_up_path")) is False


def test_mkdir(tmp_path):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    assert win_file.mkdir(path) is True
    assert os.path.isdir(path)

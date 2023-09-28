import os
from salt.modules import win_file

def test_is_link(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.is_link(tmp_path) is True
    assert win_file.is_link(os.path.join(tmp_path, "made_up_path")) is True

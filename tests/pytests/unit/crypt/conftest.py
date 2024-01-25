import pytest

import salt.utils.files

from . import TEST_KEY


@pytest.fixture
def key_to_test(tmp_path):
    key_path = tmp_path / "cryptodom-3.4.6.pub"
    with salt.utils.files.fopen(key_path, "wb") as fd:
        fd.write(TEST_KEY.encode())
    return key_path

import pytest

import salt.crypt as crypt


@pytest.fixture
def key_data():
    return [
        "-----BEGIN PUBLIC KEY-----",
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoe5QSDYRWKyknbVyRrIj",
        "rm1ht5HgKzAVUber0x54+b/UgxTd1cqI6I+eDlx53LqZSH3G8Rd5cUh8LHoGedSa",
        "E62vEiLAjgXa+RdgcGiQpYS8+Z2RvQJ8oIcZgO+2AzgBRHboNWHTYRRmJXCd3dKs",
        "9tcwK6wxChR06HzGqaOTixAuQlegWbOTU+X4dXIbW7AnuQBt9MCib7SxHlscrqcS",
        "cBrRvq51YP6cxPm/rZJdBqZhVrlghBvIpa45NApP5PherGi4AbEGYte4l+gC+fOA",
        "osEBis1V27djPpIyQS4qk3XAPQg6CYQMDltHqA4Fdo0Nt7SMScxJhfH0r6zmBFAe",
        "BQIDAQAB",
        "-----END PUBLIC KEY-----",
    ]


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test__clean_key(key_data, linesep):
    tst_key = linesep.join(key_data)
    chk_key = "\n".join(key_data)
    assert crypt.clean_key(tst_key) == crypt.clean_key(chk_key)


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test__clean_key_mismatch(key_data, linesep):
    tst_key = linesep.join(key_data)
    tst_key = tst_key.replace("5", "4")
    chk_key = "\n".join(key_data)
    assert crypt.clean_key(tst_key) != crypt.clean_key(chk_key)

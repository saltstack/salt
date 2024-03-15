import pytest

import salt.channel.server as server


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
def test_compare_keys(key_data, linesep):
    src_key = linesep.join(key_data)
    tgt_key = "\n".join(key_data)
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys_newline_src(key_data, linesep):
    src_key = linesep.join(key_data) + linesep
    tgt_key = "\n".join(key_data)
    assert src_key.endswith(linesep)
    assert not tgt_key.endswith("\n")
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys_newline_tgt(key_data, linesep):
    src_key = linesep.join(key_data)
    tgt_key = "\n".join(key_data) + "\n"
    assert not src_key.endswith(linesep)
    assert tgt_key.endswith("\n")
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True

import tarfile

import pytest

import salt.utils.http


@pytest.mark.parametrize("backend", ["requests", "urllib2", "tornado"])
def test_decode_body(webserver, integration_files_dir, backend):
    with tarfile.open(integration_files_dir / "test.tar.gz", "w:gz") as tar:
        tar.add(integration_files_dir / "this.txt")

    ret = salt.utils.http.query(
        webserver.url("test.tar.gz"), backend=backend, decode_body=False
    )
    assert isinstance(ret["body"], bytes)

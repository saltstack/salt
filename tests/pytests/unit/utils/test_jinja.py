import io
import pathlib
import tempfile

import pytest
import salt.utils.jinja as jinja
from tests.support.mock import MagicMock, patch


@pytest.fixture
def loader():
    with tempfile.TemporaryDirectory() as tempdir:
        cachedir = pathlib.Path(tempdir)
        cachedir.mkdir(parents=True, exist_ok=True)
        pkidir = cachedir / "pki"
        pkidir.mkdir(parents=True, exist_ok=True)
        (cachedir / "fnord").write_text("hello")
        loader = jinja.SaltCacheLoader(
            opts={
                "cachedir": cachedir,
                "extension_modules": "ext_mods",
                "pki_dir": pkidir,
                "id": "fnord",
                "master_uri": "localhost",
                "__role": "test thing",
                "keysize": 1024,
                "file_client": "local",
                "fileserver_backend": "fnord",
            }
        )
        yield loader


@pytest.fixture
def fake_template():
    fakefile = io.BytesIO(b"whatever this is")
    with patch("os.path.getmtime", autospec=True), patch(
        "salt.utils.files.fopen", autospec=True, return_value=fakefile
    ):
        yield


def test_if_environment_and_template_then_tplroot_should_be_added_to_environment(
    loader, fake_template,
):
    expected_globals = {
        "tplfile": "foo/bar/baz/fnord",
        "tpldir": "foo/bar/baz",
        "tpldot": "foo.bar.baz",
        "tplroot": "foo",
    }
    env = MagicMock()
    env.globals = {}
    loader.get_source(environment=env, template="foo/bar/baz/fnord")
    assert env.globals == expected_globals

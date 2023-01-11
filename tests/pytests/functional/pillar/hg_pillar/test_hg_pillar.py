import shutil
import tempfile
from pathlib import Path

import pytest

import salt.pillar.hg_pillar as hg_pillar

try:
    import hglib

    HAS_HG = True
except ImportError:
    HAS_HG = False


@pytest.fixture(scope="module")
def configure_loader_modules(master_opts):
    yield {hg_pillar: {"__opts__": master_opts}}


@pytest.fixture
def hg_setup_and_teardown():
    """
    build up and tear down hg repos to test with.
    """
    sourcedirPath = Path(__file__).resolve().parent.joinpath("files")
    tempdir = tempfile.TemporaryDirectory()
    tempsubdir = tempdir.name / Path("test2/")
    tempsubdir2 = tempdir.name / Path("subdir/")
    tempsubdir3 = tempdir.name / Path("subdir/test2/")
    tempsubdir.mkdir()
    tempsubdir2.mkdir()
    tempsubdir3.mkdir()
    tempdirPath = Path(tempdir.name)
    filessrc = [
        Path("top.sls"),
        Path("test.sls"),
        Path("test2/init.sls"),
    ]
    for fnd in filessrc:
        to = tempdirPath / fnd
        to2 = tempsubdir2 / fnd
        frm = sourcedirPath / fnd
        shutil.copy(frm.as_posix(), to.as_posix())
        shutil.copy(frm.as_posix(), to2.as_posix())
    hglib.init(bytes(tempdirPath.as_posix(), encoding="utf8"))
    repo = hglib.open(bytes(tempdirPath.as_posix(), encoding="utf8"))
    repo.add(bytes(tempdirPath.as_posix(), encoding="utf8"))
    repo.commit(b"init commit", user="test")
    repo.tag(b"test", user="test")
    repo.branch(b"test")
    repo.commit(b"create test branch", user="test")
    repo.bookmark(b"bookmark_test")
    yield tempdirPath.as_uri()
    tempdir.cleanup()


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(
    reason="just testing if this or hgfs causes the issue with total crash"
)
def test_ext_pillar(hg_setup_and_teardown):
    data = hg_pillar.ext_pillar("*", None, hg_setup_and_teardown)
    assert data == {"testinfo": "info", "testinfo2": "info"}
    data = hg_pillar.ext_pillar("test", None, hg_setup_and_teardown)
    assert data == {"testinfo": "info", "testinfo2": "info"}
    data = hg_pillar.ext_pillar("*", None, hg_setup_and_teardown, root="subdir")
    assert data == {"testinfo": "info", "testinfo2": "info"}

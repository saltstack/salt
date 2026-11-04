"""
Tests for tools/pkg/pip_urllib3.py, which overlays the urllib3 Salt ships onto
the urllib3 vendored in the pip wheel packaged with the onedir.
"""

import base64
import csv
import hashlib
import importlib.util
import pathlib
import zipfile

import pytest

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[4] / "tools" / "pkg" / "pip_urllib3.py"
)

# Loaded by path: importing ``tools.pkg`` pulls in ptscripts, which is not part
# of the test environment.
_spec = importlib.util.spec_from_file_location("pip_urllib3", MODULE_PATH)
pip_urllib3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pip_urllib3)

RESPONSE_PY = """\
from __future__ import annotations

try:
    try:
        import brotlicffi as brotli  # type: ignore[import-not-found]
    except ImportError:
        import brotli  # type: ignore[import-not-found]
except ImportError:
    brotli = None

from . import util
"""

REQUEST_PY = """\
ACCEPT_ENCODING = "gzip,deflate"
try:
    try:
        import brotlicffi as _unused_module_brotli  # noqa: F401
    except ImportError:
        import brotli as _unused_module_brotli  # noqa: F401
except ImportError:
    pass
else:
    ACCEPT_ENCODING += ",br"

try:
    pass
except ImportError:
    pass
"""

URL_PY = """\
def f(name):
    '''
    .. code-block:: python

        import urllib3

        urllib3.util.parse_url("https://example.com")
    '''
    if not name.isascii():
        try:
            import idna
        except ImportError:
            raise
"""

PYOPENSSL_PY = """\
def extract():
    try:
        import urllib3.contrib.pyopenssl
        urllib3.contrib.pyopenssl.inject_into_urllib3()
    except ImportError:
        pass
"""

EMSCRIPTEN_PY = """\
from __future__ import annotations

import urllib3.connection

from ...connectionpool import HTTPConnectionPool


def inject_into_urllib3() -> None:
    urllib3.connection.HTTPConnection = EmscriptenHTTPConnection
    urllib3.connection.VerifiedHTTPSConnection = EmscriptenHTTPSConnection
"""


def _version_py(version):
    return f"__version__ = version = '{version}'\n"


def _record_row(path, content):
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
    return [path, "sha256=" + digest.decode().rstrip("="), str(len(content))]


def _write_wheel(path, files, dist_info):
    rows = [_record_row(name, data) for name, data in files.items()]
    rows.append([f"{dist_info}/RECORD", "", ""])
    lines = "".join(",".join(row) + "\n" for row in rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        zf.writestr(f"{dist_info}/RECORD", lines)
    return path


@pytest.fixture
def urllib3_wheel(tmp_path):
    files = {
        "urllib3/__init__.py": b"",
        "urllib3/_version.py": _version_py("2.9.0").encode(),
        "urllib3/response.py": RESPONSE_PY.encode(),
        "urllib3/util/request.py": REQUEST_PY.encode(),
        "urllib3/util/url.py": URL_PY.encode(),
        "urllib3/contrib/pyopenssl.py": PYOPENSSL_PY.encode(),
        "urllib3/contrib/emscripten/__init__.py": EMSCRIPTEN_PY.encode(),
        "urllib3/py.typed": b"",
    }
    return _write_wheel(
        tmp_path / "urllib3-2.9.0-py3-none-any.whl", files, "urllib3-2.9.0.dist-info"
    )


@pytest.fixture
def pip_wheel(tmp_path):
    prefix = "pip/_vendor/urllib3/"
    files = {
        "pip/__init__.py": b"__version__ = '26.2'\n",
        f"{prefix}__init__.py": b"",
        f"{prefix}_version.py": _version_py("2.7.0").encode(),
        f"{prefix}LICENSE.txt": b"MIT\n",
        f"{prefix}removed_upstream.py": b"x = 1\n",
    }
    return _write_wheel(
        tmp_path / "pip-26.2-py3-none-any.whl", files, "pip-26.2.dist-info"
    )


@pytest.mark.parametrize(
    "version,expected",
    [
        ("2.8.0", (2, 8, 0)),
        ("2.8", (2, 8)),
        ("2.8.0rc1", (2, 8, 0)),
        ("2.8.dev", (2, 8)),
        ("1.26.20", (1, 26, 20)),
    ],
)
def test_parse_version(version, expected):
    assert pip_urllib3.parse_version(version) == expected


def test_transform_response_drops_brotli_import():
    out = pip_urllib3.transform_source("response.py", RESPONSE_PY)
    assert "brotlicffi" not in out
    assert "brotli = None\n" in out
    assert "from . import util" in out


def test_transform_request_drops_brotli_accept_encoding():
    out = pip_urllib3.transform_source("util/request.py", REQUEST_PY)
    assert "brotli" not in out
    assert '",br"' not in out
    assert 'ACCEPT_ENCODING = "gzip,deflate"' in out


def test_transform_rewrites_imports_to_pip_vendor():
    out = pip_urllib3.transform_source("util/url.py", URL_PY)
    assert "        from pip._vendor import urllib3" in out
    assert "            from pip._vendor import idna" in out
    assert "import urllib3\n" not in out.replace("from pip._vendor import urllib3", "")


def test_transform_pyopenssl_and_emscripten():
    out = pip_urllib3.transform_source("contrib/pyopenssl.py", PYOPENSSL_PY)
    assert "import pip._vendor.urllib3.contrib.pyopenssl as pyopenssl" in out
    assert "        pyopenssl.inject_into_urllib3()" in out

    out = pip_urllib3.transform_source("contrib/emscripten/__init__.py", EMSCRIPTEN_PY)
    assert "import pip._vendor.urllib3.connection as urllib3_connection" in out
    assert "    urllib3_connection.HTTPConnection = " in out
    assert "    urllib3_connection.VerifiedHTTPSConnection = " in out


def test_transform_fails_when_expected_edit_is_missing():
    # A future urllib3 that restructures the brotli import must not slip
    # through with the brotli import left in place.
    with pytest.raises(ValueError, match="expected pip vendoring edit not found"):
        pip_urllib3.transform_source("response.py", "import brotli\n")


def test_transform_fails_on_unrewritten_import():
    with pytest.raises(ValueError, match="un-vendored import"):
        pip_urllib3.transform_source("util/other.py", "import urllib3\n")


def test_overlay_replaces_vendored_urllib3(pip_wheel, urllib3_wheel):
    assert pip_urllib3.vendored_version(pip_wheel) == "2.7.0"
    assert pip_urllib3.overlay_urllib3(pip_wheel, urllib3_wheel) is True
    assert pip_urllib3.vendored_version(pip_wheel) == "2.9.0"

    prefix = "pip/_vendor/urllib3/"
    with zipfile.ZipFile(pip_wheel) as zf:
        assert zf.testzip() is None
        names = set(zf.namelist())
        # Files unrelated to urllib3 are untouched.
        assert "pip/__init__.py" in names
        # pip's own LICENSE.txt is kept, files removed upstream are dropped,
        # new upstream files are added, and pip's edits are applied.
        assert f"{prefix}LICENSE.txt" in names
        assert f"{prefix}removed_upstream.py" not in names
        assert f"{prefix}py.typed" in names
        response = zf.read(f"{prefix}response.py").decode()
        assert "brotli = None\n" in response and "brotlicffi" not in response

        # RECORD lists every file with its current hash and size.
        record = list(
            csv.reader(zf.read("pip-26.2.dist-info/RECORD").decode().splitlines())
        )
        assert record[-1] == ["pip-26.2.dist-info/RECORD", "", ""]
        assert {row[0] for row in record} == names
        for path, digest, size in record:
            if not digest:
                continue
            data = zf.read(path)
            assert _record_row(path, data) == [path, digest, size]


@pytest.mark.parametrize("vendored", ["2.9.0", "3.0.0"])
def test_overlay_is_a_no_op_when_pip_is_already_new_enough(
    tmp_path, urllib3_wheel, vendored
):
    prefix = "pip/_vendor/urllib3/"
    wheel = _write_wheel(
        tmp_path / "pip-27.0-py3-none-any.whl",
        {f"{prefix}_version.py": _version_py(vendored).encode()},
        "pip-27.0.dist-info",
    )
    before = wheel.read_bytes()
    assert pip_urllib3.overlay_urllib3(wheel, urllib3_wheel) is False
    assert wheel.read_bytes() == before


def test_overlay_leaves_wheel_untouched_when_a_transform_fails(tmp_path, pip_wheel):
    bad = _write_wheel(
        tmp_path / "urllib3-2.9.0-py3-none-any.whl",
        {
            "urllib3/_version.py": _version_py("2.9.0").encode(),
            "urllib3/response.py": b"import brotli\n",
        },
        "urllib3-2.9.0.dist-info",
    )
    before = pip_wheel.read_bytes()
    with pytest.raises(ValueError):
        pip_urllib3.overlay_urllib3(pip_wheel, bad)
    assert pip_wheel.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp.whl"))


def test_pin_from_lock(tmp_path):
    lock = tmp_path / "linux.lock"
    lock.write_text("certifi==2026.6.17\nurllib3==2.8.0\nzipp==3.0\n")
    assert pip_urllib3.urllib3_pin_from_lock(lock, (3, 12)) == "2.8.0"


def test_pin_from_lock_is_none_before_python_310(tmp_path):
    lock = tmp_path / "linux.lock"
    lock.write_text("urllib3==1.26.20\n")
    assert pip_urllib3.urllib3_pin_from_lock(lock, (3, 9)) is None
    # Even a 2.x pin is ignored: urllib3 2.8 needs Python 3.10.
    lock.write_text("urllib3==2.8.0\n")
    assert pip_urllib3.urllib3_pin_from_lock(lock, (3, 9)) is None


def test_pin_from_lock_with_python_markers(tmp_path):
    lock = tmp_path / "freebsd.lock"
    lock.write_text(
        "urllib3==1.26.20 ; python_full_version < '3.10'\n"
        "urllib3==2.8.0 ; python_full_version >= '3.10'\n"
    )
    assert pip_urllib3.urllib3_pin_from_lock(lock, (3, 11)) == "2.8.0"


def test_pin_from_lock_without_urllib3(tmp_path):
    lock = tmp_path / "linux.lock"
    lock.write_text("zipp==3.0\n")
    assert pip_urllib3.urllib3_pin_from_lock(lock, (3, 12)) is None

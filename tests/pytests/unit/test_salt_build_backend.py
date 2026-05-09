"""
    tests.pytests.unit.test_salt_build_backend
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests for Salt's custom build backend tools/pkg/salt_build_backend.py
"""

import sys

import pytest

from tests.support.mock import MagicMock, patch


@pytest.fixture
def salt_build_backend():
    with patch("sys.path", ["tools/pkg"] + sys.path):
        import salt_build_backend

        yield salt_build_backend
        if "salt_build_backend" in sys.modules:
            del sys.modules["salt_build_backend"]


def test_build_editable(salt_build_backend):
    if salt_build_backend.setuptools_build_editable is None:
        pytest.skip("setuptools does not support build_editable")
    with patch(
        "salt_build_backend.setuptools_build_editable", return_value="wheel.whl"
    ) as mock_setuptools_build_editable:
        ret = salt_build_backend.build_editable("wheel_dir")
        assert ret == "wheel.whl"
        mock_setuptools_build_editable.assert_called_once_with("wheel_dir", None, None)


def test_build_editable_unsupported(salt_build_backend):
    with patch("salt_build_backend.setuptools_build_editable", None):
        with pytest.raises(NotImplementedError):
            salt_build_backend.build_editable("wheel_dir")


def test_prepare_metadata_for_build_editable(salt_build_backend):
    if salt_build_backend.setuptools_prepare_metadata is None:
        pytest.skip("setuptools does not support prepare_metadata_for_build_editable")
    with patch(
        "salt_build_backend.setuptools_prepare_metadata", return_value="metadata_dir"
    ) as mock_setuptools_prepare_metadata:
        ret = salt_build_backend.prepare_metadata_for_build_editable("metadata_dir")
        assert ret == "metadata_dir"
        mock_setuptools_prepare_metadata.assert_called_once_with("metadata_dir", None)


def test_prepare_metadata_for_build_editable_unsupported(salt_build_backend):
    with patch("salt_build_backend.setuptools_prepare_metadata", None):
        with pytest.raises(NotImplementedError):
            salt_build_backend.prepare_metadata_for_build_editable("metadata_dir")


def test_prepare_metadata_for_build_wheel(salt_build_backend):
    from setuptools import build_meta as _orig

    assert (
        salt_build_backend.prepare_metadata_for_build_wheel
        is _orig.prepare_metadata_for_build_wheel
    )


def test_build_wheel(salt_build_backend):
    from setuptools import build_meta as _orig

    assert salt_build_backend.build_wheel is _orig.build_wheel


def test_build_sdist(salt_build_backend):
    from setuptools import build_meta as _orig

    assert salt_build_backend.build_sdist is _orig.build_sdist


def test_get_requires_for_build_wheel(salt_build_backend):
    from setuptools import build_meta as _orig

    assert (
        salt_build_backend.get_requires_for_build_wheel
        is _orig.get_requires_for_build_wheel
    )


def test_get_requires_for_build_sdist(salt_build_backend):
    from setuptools import build_meta as _orig

    assert (
        salt_build_backend.get_requires_for_build_sdist
        is _orig.get_requires_for_build_sdist
    )


def test_get_salt_version(salt_build_backend):
    with patch("salt_build_backend.PROJECT_ROOT", "."), patch(
        "salt_build_backend.open",
        MagicMock(
            return_value=MagicMock(
                __enter__=lambda x: x,
                __exit__=lambda x, y, z, w: None,
                read=lambda: "__saltstack_version__ = '3006.0'",
            )
        ),
    ):
        assert salt_build_backend.get_salt_version() == "3006.0"


def test_get_install_requires(salt_build_backend):
    with patch("salt_build_backend.PROJECT_ROOT", "."), patch(
        "salt_build_backend._parse_requirements_file", return_value=["salt-req"]
    ):
        reqs = salt_build_backend.get_install_requires()
        assert "salt-req" in reqs


def test_get_extras_require(salt_build_backend):
    with patch("salt_build_backend.PROJECT_ROOT", "."), patch(
        "os.path.exists", return_value=True
    ), patch(
        "salt_build_backend._parse_requirements_file", return_value=["crypto-req"]
    ):
        extras = salt_build_backend.get_extras_require()
        assert extras["crypto"] == ["crypto-req"]


def test_get_entry_points(salt_build_backend):
    with patch("salt_build_backend.PROJECT_ROOT", "."), patch(
        "os.path.exists", return_value=True
    ):
        entry_points = salt_build_backend.get_entry_points()
        assert "console_scripts" in entry_points
        assert any("salt-call =" in s for s in entry_points["console_scripts"])


def test_get_scripts(salt_build_backend):
    with patch("salt_build_backend.PROJECT_ROOT", "."), patch(
        "os.path.exists", return_value=True
    ):
        scripts = salt_build_backend.get_scripts()
        assert "scripts/salt-call" in scripts

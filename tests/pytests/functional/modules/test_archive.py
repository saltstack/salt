"""
Tests for the archive state
"""
import os
import pathlib
import shutil
import tempfile
import textwrap

import attr
import pytest
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

try:
    import zipfile  # pylint: disable=unused-import

    HAS_ZIPFILE = True
except ImportError:
    HAS_ZIPFILE = False

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@attr.s(frozen=True, slots=True)
class Archive:
    fmt = attr.ib()
    unicode_filename = attr.ib(default=False)

    path = attr.ib(init=False)
    src = attr.ib(init=False)
    src_file = attr.ib(init=False)
    archive = attr.ib(init=False)
    dst = attr.ib(init=False)
    filename = attr.ib(init=False)

    @path.default
    def _path(self):
        return pathlib.Path(tempfile.mkdtemp())

    @src.default
    def _src(self):
        return self.path / "{}_src_dir".format(self.fmt)

    @src_file.default
    def _src_file(self):
        return self.src / "file"

    @archive.default
    def _archive(self):
        return self.path / "archive.{}".format(self.fmt)

    @dst.default
    def _dst(self):
        return self.path / "{}_dst_dir".format(self.fmt)

    @filename.default
    def _filename(self):
        if self.unicode_filename:
            return "file®"
        return "file"

    def __attrs_post_init__(self):
        # Create source
        self.src.mkdir()
        self.dst.mkdir()

        if salt.utils.platform.is_windows():
            encoding = "utf-8"
        else:
            encoding = None

        dst_filename = self.src / self.filename
        dst_filename.write_bytes(
            salt.utils.stringutils.to_bytes(
                textwrap.dedent(
                    """\
            Compression theorem of computational complexity theory:

            Given a Gödel numbering $φ$ of the computable functions and a
            Blum complexity measure $Φ$ where a complexity class for a
            boundary function $f$ is defined as

                $\\mathrm C(f) := \\{φ_i ∈ \\mathbb R^{(1)} | (∀^∞ x) Φ_i(x) ≤ f(x)\\}$.

            Then there exists a total computable function $f$ so that for
            all $i$

                $\\mathrm{Dom}(φ_i) = \\mathrm{Dom}(φ_{f(i)})$

            and

                $\\mathrm C(φ_i) ⊊ \\mathrm{C}(φ_{f(i)})$.
        """
                ),
                encoding=encoding,
            )
        )

    def assert_artifacts_in_ret(self, ret, file_only=False, unix_sep=False):
        """
        Assert that the artifact source files are printed in the source command
        output
        """

        def normdir(path):
            normdir = os.path.normcase(os.path.abspath(str(path)))
            if salt.utils.platform.is_windows():
                # Remove the drive portion of path
                if len(normdir) >= 2 and normdir[1] == ":":
                    normdir = normdir.split(":", 1)[1]
            normdir = normdir.lstrip(os.path.sep)
            # Unzipped paths might have unix line endings
            if unix_sep:
                normdir = normdir.replace(os.path.sep, "/")
            return normdir

        # Try to find source directory and file in output lines
        dir_in_ret = None
        file_in_ret = None
        for line in ret:
            if normdir(self.src) in os.path.normcase(line) and not normdir(
                self.src_file
            ) in os.path.normcase(line):
                dir_in_ret = True
            if normdir(self.src_file) in os.path.normcase(line):
                file_in_ret = True

        # Assert number of lines, reporting of source directory and file
        assert len(ret) >= 1 if file_only else 2
        if not file_only:
            assert dir_in_ret is True
        assert file_in_ret is True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        shutil.rmtree(str(self.path), ignore_errors=True)


@pytest.fixture(scope="module")
def archive(modules):
    return modules.archive


def unicode_filename_ids(value):
    return "unicode_filename={}".format(value)


@pytest.fixture(params=[True, False], ids=unicode_filename_ids)
def unicode_filename(request):
    return request.param


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("tar")
def test_tar_pack(archive, unicode_filename):
    """
    Validate using the tar function to create archives
    """
    with Archive("tar", unicode_filename=unicode_filename) as arch:
        ret = archive.tar("-cvf", str(arch.archive), sources=str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("tar")
def test_tar_unpack(archive, unicode_filename):
    """
    Validate using the tar function to extract archives
    """
    with Archive("tar", unicode_filename=unicode_filename) as arch:
        ret = archive.tar("-cvf", str(arch.archive), sources=str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)

        ret = archive.tar("-xvf", str(arch.archive), dest=str(arch.dst))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("tar")
def test_tar_list(archive, unicode_filename):
    """
    Validate using the tar function to list archives
    """
    with Archive("tar", unicode_filename=unicode_filename) as arch:
        ret = archive.tar("-cvf", str(arch.archive), sources=str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)

        ret = archive.list(str(arch.archive))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)


@pytest.mark.skip_if_binaries_missing("gzip")
def test_gzip(archive, unicode_filename):
    """
    Validate using the gzip function
    """
    with Archive("gz", unicode_filename=unicode_filename) as arch:
        ret = archive.gzip(str(arch.src_file), options="-v")
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret, file_only=True)


@pytest.mark.skip_if_binaries_missing("gzip", "gunzip")
def test_gunzip(archive, unicode_filename):
    """
    Validate using the gunzip function
    """
    with Archive("gz", unicode_filename=unicode_filename) as arch:
        ret = archive.gzip(str(arch.src_file), options="-v")
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret, file_only=True)

        ret = archive.gunzip(str(arch.src_file) + ".gz", options="-v")
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret, file_only=True)


@pytest.mark.skip_if_binaries_missing("zip")
def test_cmd_zip(archive, unicode_filename):
    """
    Validate using the cmd_zip function
    """
    with Archive("zip", unicode_filename=unicode_filename) as arch:
        ret = archive.cmd_zip(str(arch.archive), str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)


@pytest.mark.skip_if_binaries_missing("zip", "unzip")
def test_cmd_unzip(archive, unicode_filename):
    """
    Validate using the cmd_unzip function
    """
    with Archive("zip", unicode_filename=unicode_filename) as arch:
        ret = archive.cmd_zip(str(arch.archive), str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)

        ret = archive.cmd_unzip(str(arch.archive), str(arch.dst))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)


@pytest.mark.skipif(not HAS_ZIPFILE, reason="Cannot find zipfile python module")
def test_zip(archive, unicode_filename):
    """
    Validate using the zip function
    """
    with Archive("zip", unicode_filename=unicode_filename) as arch:
        ret = archive.zip(str(arch.archive), str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)


@pytest.mark.skipif(not HAS_ZIPFILE, reason="Cannot find zipfile python module")
def test_unzip(archive, unicode_filename):
    """
    Validate using the unzip function
    """
    with Archive("zip", unicode_filename=unicode_filename) as arch:
        ret = archive.zip(str(arch.archive), str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)

        ret = archive.unzip(str(arch.archive), str(arch.dst))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret, unix_sep=False)


@pytest.mark.skip_if_binaries_missing("rar")
def test_rar(archive, unicode_filename):
    """
    Validate using the rar function
    """
    with Archive("rar", unicode_filename=unicode_filename) as arch:
        ret = archive.rar(str(arch.archive), str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)


@pytest.mark.skip_if_binaries_missing("rar", "unrar")
def test_unrar(archive, unicode_filename):
    """
    Validate using the unrar function
    """
    with Archive("rar", unicode_filename=unicode_filename) as arch:
        ret = archive.rar(str(arch.archive), str(arch.src))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)

        ret = archive.unrar(str(arch.archive), str(arch.dst))
        assert isinstance(ret, list)
        arch.assert_artifacts_in_ret(ret)

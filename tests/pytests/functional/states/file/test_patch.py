import os
import pathlib
import re
import textwrap
import types

import pytest

import salt.utils.hashutils
import salt.utils.platform
import salt.utils.versions
from salt.utils.versions import Version

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_if_binaries_missing("patch"),
]


class Patches:
    def __init__(self, webserver):
        self.webserver = webserver
        self.webserver_root = pathlib.Path(webserver.root)
        self.numbers_patch_name = "numbers.patch"
        self.numbers_patch_template_name = self.numbers_patch_name + ".jinja"
        self.numbers_patch_path = "patches/" + self.numbers_patch_name
        self.numbers_patch_template_path = "patches/" + self.numbers_patch_template_name
        self.numbers_patch = "salt://" + self.numbers_patch_path
        self.numbers_patch_template = "salt://" + self.numbers_patch_template_path
        self.numbers_patch_http = self.webserver.url(self.numbers_patch_path)
        self.numbers_patch_template_http = self.webserver.url(
            self.numbers_patch_template_path
        )

        self.math_patch_name = "math.patch"
        self.math_patch_template_name = self.math_patch_name + ".jinja"
        self.math_patch_path = "patches/" + self.math_patch_name
        self.math_patch_template_path = "patches/" + self.math_patch_template_name
        self.math_patch = "salt://" + self.math_patch_path
        self.math_patch_template = "salt://" + self.math_patch_template_path
        self.math_patch_http = self.webserver.url(self.math_patch_path)
        self.math_patch_template_http = self.webserver.url(
            self.math_patch_template_path
        )

        self.all_patch_name = "all.patch"
        self.all_patch_template_name = self.all_patch_name + ".jinja"
        self.all_patch_path = "patches/" + self.all_patch_name
        self.all_patch_template_path = "patches/" + self.all_patch_template_name
        self.all_patch = "salt://" + self.all_patch_path
        self.all_patch_template = "salt://" + self.all_patch_template_path
        self.all_patch_http = self.webserver.url(self.all_patch_path)
        self.all_patch_template_http = self.webserver.url(self.all_patch_template_path)

        patches_dir = self.webserver_root / "patches"
        patches_dir.mkdir()
        numbers_patch = patches_dir / self.numbers_patch_name
        numbers_patch.write_text(
            textwrap.dedent(
                """\
                --- a/foo/numbers.txt	2018-04-09 18:43:58.014272504 -0500
                +++ b/foo/numbers.txt	2018-04-09 18:44:46.487905044 -0500
                @@ -1,7 +1,7 @@
                -one
                -two
                 three
                +two
                +one

                -1
                -2
                 3
                +2
                +1
                """
            )
        )
        numbers_patch_template = patches_dir / self.numbers_patch_template_name
        numbers_patch_template.write_text(
            numbers_patch.read_text().replace("+two", "+{{ two }}")
        )
        math_patch = patches_dir / self.math_patch_name
        math_patch.write_text(
            textwrap.dedent(
                """\
                --- a/foo/bar/math.txt	2018-04-09 18:43:52.883205365 -0500
                +++ b/foo/bar/math.txt	2018-04-09 18:44:58.525061654 -0500
                @@ -1,3 +1,3 @@
                -Five plus five is ten
                +5 + 5 = 10

                -Four squared is sixteen
                +4² = 16
                """
            )
        )
        math_patch_template = patches_dir / self.math_patch_template_name
        math_patch_template.write_text(
            math_patch.read_text().replace("= 10", "= {{ ten }}")
        )
        all_patch = patches_dir / self.all_patch_name
        all_patch.write_text(math_patch.read_text() + numbers_patch.read_text())
        all_patch_template = patches_dir / self.all_patch_template_name
        all_patch_template.write_text(
            math_patch_template.read_text() + numbers_patch_template.read_text()
        )
        self.numbers_patch_hash = salt.utils.hashutils.get_hash(
            str(patches_dir / self.numbers_patch_name)
        )
        self.numbers_patch_template_hash = salt.utils.hashutils.get_hash(
            str(patches_dir / self.numbers_patch_template_name)
        )
        self.math_patch_hash = salt.utils.hashutils.get_hash(
            str(patches_dir / self.math_patch_name)
        )
        self.math_patch_template_hash = salt.utils.hashutils.get_hash(
            str(patches_dir / self.math_patch_template_name)
        )
        self.all_patch_hash = salt.utils.hashutils.get_hash(
            str(patches_dir / self.all_patch_name)
        )
        self.all_patch_template_hash = salt.utils.hashutils.get_hash(
            str(patches_dir / self.all_patch_template_name)
        )


@pytest.fixture(scope="module")
def _check_min_patch_version(shell):
    min_patch_ver = Version("2.6")
    ret = shell.run("patch", "--version")
    assert ret.returncode == 0
    version = ret.stdout.strip().splitlines()[0].split()[-1]
    if Version(version) < min_patch_ver:
        pytest.xfail(
            "Minimum version of patch not found, expecting {}, found {}".format(
                min_patch_ver, version
            )
        )


@pytest.fixture(scope="module")
def patches(webserver, _check_min_patch_version):
    yield Patches(webserver)


@pytest.fixture
def files(tmp_path):
    numbers_contents = """
    one
    two
    three

    1
    2
    3
    """
    math_contents = """
    Five plus five is ten

    Four squared is sixteen
    """
    numbers_file = pytest.helpers.temp_file(
        "numbers.txt", directory=tmp_path / "foo", contents=numbers_contents
    )
    math_file = pytest.helpers.temp_file(
        "math.txt", directory=tmp_path / "foo" / "bar", contents=math_contents
    )
    with numbers_file as numbers_file, math_file as math_file:
        yield types.SimpleNamespace(
            numbers=numbers_file, math=math_file, base_dir=tmp_path
        )


def test_patch_single_file(file, files, patches):
    """
    Test file.patch using a patch applied to a single file
    """
    ret = file.patch(name=str(files.numbers), source=patches.numbers_patch)
    assert ret.result is True
    assert ret.changes
    assert ret.comment == "Patch successfully applied"

    # Re-run the state, should succeed and there should be a message about
    # a partially-applied hunk.
    ret = file.patch(name=str(files.numbers), source=patches.numbers_patch)
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "Patch was already applied"


@pytest.mark.skip_on_freebsd(
    reason="Previously skipped on FreeBSD. Needs investigation as to why it currently False"
)
@pytest.mark.skip_on_darwin(
    reason="Failing and previously skipped because patch wasn't >= 2.6"
)
def test_patch_directory(file, files, patches):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files.
    """
    ret = file.patch(name=str(files.base_dir), source=patches.all_patch, strip=1)
    assert ret.result is True
    assert ret.changes
    assert ret.comment == "Patch successfully applied"

    # Re-run the state, should succeed and there should be a message about
    # a partially-applied hunk.
    ret = file.patch(name=str(files.base_dir), source=patches.all_patch, strip=1)
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "Patch was already applied"


@pytest.mark.skip_on_freebsd(
    reason="Previously skipped on FreeBSD. Needs investigation as to why it currently False"
)
@pytest.mark.skip_on_darwin(
    reason="Failing and previously skipped because patch wasn't >= 2.6"
)
def test_patch_strip_parsing(file, files, patches, subtests):
    """
    Test that we successfuly parse -p/--strip when included in the options
    """
    # Run the state using -p1
    with subtests.test("options='-p1'"):
        ret = file.patch(
            name=str(files.base_dir), source=patches.all_patch, options="-p1"
        )
        assert ret.result is True
        assert ret.changes
        assert ret.comment == "Patch successfully applied"

    # Re-run the state using --strip=1
    with subtests.test("options='--strip=1'"):
        ret = file.patch(
            name=str(files.base_dir), source=patches.all_patch, options="--strip=1"
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Patch was already applied"

    # Re-run the state using --strip 1
    with subtests.test("options='--strip=1'"):
        ret = file.patch(
            name=str(files.base_dir), source=patches.all_patch, options="--strip=1"
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Patch was already applied"


def test_patch_saltenv(file, files, patches):
    """
    Test that we attempt to download the patch from a non-base saltenv
    """
    # This state will fail because we don't have a patch file in that
    # environment, but that is OK, we just want to test that we're looking
    # in an environment other than base.
    ret = file.patch(name=str(files.math), source=patches.math_patch, saltenv="prod")
    assert ret.result is False
    assert ret.comment == "Source file {} not found in saltenv 'prod'".format(
        patches.math_patch
    )


def test_patch_single_file_failure(file, tmp_path, files, patches):
    """
    Test file.patch using a patch applied to a single file. This tests a
    failed patch.
    """
    # Empty the file to ensure that the patch doesn't apply cleanly
    files.numbers.write_text("")

    ret = file.patch(name=str(files.numbers), source=patches.numbers_patch)
    assert ret.result is False
    assert "Patch would not apply cleanly" in ret.comment

    # Test the reject_file option and ensure that the rejects are written
    # to the path specified.
    reject_file = tmp_path / "rejected"
    ret = file.patch(
        name=str(files.numbers),
        source=patches.numbers_patch,
        reject_file=str(reject_file),
        strip=1,
    )
    assert ret.result is False
    assert "Patch would not apply cleanly" in ret.comment
    if salt.utils.platform.is_windows():
        assert_fpath = f".*{reject_file.name}"
    else:
        assert_fpath = reject_file
    assert re.search("saving rejects to (file )?{}".format(assert_fpath), ret.comment)


@pytest.mark.skip_on_freebsd(
    reason="Previously skipped on FreeBSD. Needs investigation as to why it currently False"
)
def test_patch_directory_failure(file, tmp_path, files, patches):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files.
    """
    # Empty the file to ensure that the patch doesn't apply cleanly
    files.numbers.write_text("")

    ret = file.patch(name=str(files.base_dir), source=patches.all_patch, strip=1)
    assert ret.result is False
    assert "Patch would not apply cleanly" in ret.comment

    # Test the reject_file option and ensure that the rejects are written
    # to the path specified.
    reject_file = tmp_path / "rejected"
    ret = file.patch(
        name=str(files.base_dir),
        source=patches.all_patch,
        reject_file=str(reject_file),
        strip=1,
    )
    assert ret.result is False
    assert "Patch would not apply cleanly" in ret.comment
    if salt.utils.platform.is_windows():
        assert_fpath = f".*{reject_file.name}"
    else:
        assert_fpath = reject_file
    assert re.search("saving rejects to (file )?{}".format(assert_fpath), ret.comment)


def test_patch_single_file_remote_source(file, files, patches, subtests):
    """
    Test file.patch using a patch applied to a single file, with the patch
    coming from a remote source.
    """
    # Try without a source_hash and without skip_verify=True, this should
    # fail with a message about the source_hash
    with subtests.test("source_hash=None"):
        ret = file.patch(name=str(files.math), source=patches.math_patch_http)
        assert ret.result is False
        assert "Unable to verify upstream hash" in ret.comment

    # Re-run the state with a source hash, it should now succeed
    with subtests.test("source_hash!=None"):
        ret = file.patch(
            name=str(files.math),
            source=patches.math_patch_http,
            source_hash=patches.math_patch_hash,
        )
        assert ret.result is True
        assert ret.changes
        assert ret.comment == "Patch successfully applied"

    # Re-run again, this time with no hash and skip_verify=True to test
    # skipping hash verification
    with subtests.test("source_hash=None and skip_verify=True"):
        ret = file.patch(
            name=str(files.math), source=patches.math_patch_http, skip_verify=True
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Patch was already applied"


@pytest.mark.skip_on_freebsd(
    reason="Previously skipped on FreeBSD. Needs investigation as to why it currently False"
)
@pytest.mark.skip_on_darwin(
    reason="Failing and previously skipped because patch wasn't >= 2.6"
)
def test_patch_directory_remote_source(file, files, patches, subtests):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files, and the patch file coming from a remote
    source.
    """
    # Try without a source_hash and without skip_verify=True, this should
    # fail with a message about the source_hash
    with subtests.test("source_hash=None"):
        ret = file.patch(
            name=str(files.base_dir), source=patches.all_patch_http, strip=1
        )
        assert ret.result is False
        assert "Unable to verify upstream hash" in ret.comment

    # Re-run the state with a source hash, it should now succeed
    with subtests.test("source_hash!=None"):
        ret = file.patch(
            name=str(files.base_dir),
            source=patches.all_patch_http,
            source_hash=patches.all_patch_hash,
            strip=1,
        )
        assert ret.result is True
        assert ret.changes
        assert ret.comment == "Patch successfully applied"

    # Re-run again, this time with no hash and skip_verify=True to test
    # skipping hash verification
    with subtests.test("source_hash=None and skip_verify=True"):
        ret = file.patch(
            name=str(files.base_dir),
            source=patches.all_patch_http,
            skip_verify=True,
            strip=1,
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Patch was already applied"


def test_patch_single_file_template(file, files, patches):
    """
    Test file.patch using a patch applied to a single file, with jinja
    templating applied to the patch file.
    """
    ret = file.patch(
        name=str(files.numbers),
        source=patches.numbers_patch_template,
        template="jinja",
        context={"two": "two", "ten": 10},
    )
    assert ret.result is True
    assert ret.comment == "Patch successfully applied"

    # Re-run the state, should succeed and there should be a message about
    # a partially-applied hunk.
    ret = file.patch(
        name=str(files.numbers),
        source=patches.numbers_patch_template,
        template="jinja",
        context={"two": "two", "ten": 10},
    )
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "Patch was already applied"


@pytest.mark.skip_on_freebsd(
    reason="Previously skipped on FreeBSD. Needs investigation as to why it currently False"
)
@pytest.mark.skip_on_darwin(
    reason="Failing and previously skipped because patch wasn't >= 2.6"
)
def test_patch_directory_template(file, files, patches):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files, and with jinja templating applied to the patch
    file.
    """
    if salt.utils.platform.is_windows() and os.environ.get("PYTHONUTF8", "0") == "0":
        pytest.skip("Test will fail if PYTHONUTF8=1 is not set on windows")
    ret = file.patch(
        name=str(files.base_dir),
        source=patches.all_patch_template,
        template="jinja",
        context={"two": "two", "ten": 10},
        strip=1,
    )
    assert ret.result is True
    assert ret.changes
    assert ret.comment == "Patch successfully applied"

    # Re-run the state, should succeed and there should be a message about
    # a partially-applied hunk.
    ret = file.patch(
        name=str(files.base_dir),
        source=patches.all_patch_template,
        template="jinja",
        context={"two": "two", "ten": 10},
        strip=1,
    )
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "Patch was already applied"


def test_patch_single_file_remote_source_template(file, files, patches, subtests):
    """
    Test file.patch using a patch applied to a single file, with the patch
    coming from a remote source.
    """
    if salt.utils.platform.is_windows() and os.environ.get("PYTHONUTF8", "0") == "0":
        pytest.skip("Test will fail if PYTHONUTF8=1 is not set on windows")
    # Try without a source_hash and without skip_verify=True, this should
    # fail with a message about the source_hash
    with subtests.test("source_hash=None and skip_verify=False"):
        ret = file.patch(
            name=str(files.math),
            source=patches.math_patch_template_http,
            template="jinja",
            context={"two": "two", "ten": 10},
        )
        assert ret.result is False
        assert not ret.changes
        assert "Unable to verify upstream hash" in ret.comment

    # Re-run the state with a source hash, it should now succeed
    with subtests.test("source_hash!=None"):
        ret = file.patch(
            name=str(files.math),
            source=patches.math_patch_template_http,
            source_hash=patches.math_patch_template_hash,
            template="jinja",
            context={"two": "two", "ten": 10},
        )
        assert ret.result is True
        assert ret.changes
        assert ret.comment == "Patch successfully applied"
    with subtests.test("source_hash=None and skip_verify=True"):
        ret = file.patch(
            name=str(files.math),
            source=patches.math_patch_template_http,
            template="jinja",
            context={"two": "two", "ten": 10},
            skip_verify=True,
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Patch was already applied"


@pytest.mark.skip_on_freebsd(
    reason="Previously skipped on FreeBSD. Needs investigation as to why it currently False"
)
@pytest.mark.skip_on_darwin(
    reason="Failing and previously skipped because patch wasn't >= 2.6"
)
def test_patch_directory_remote_source_template(file, files, patches, subtests):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files, and the patch file coming from a remote
    source.
    """
    if salt.utils.platform.is_windows() and os.environ.get("PYTHONUTF8", "0") == "0":
        pytest.skip("Test will fail if PYTHONUTF8=1 is not set on windows")
    # Try without a source_hash and without skip_verify=True, this should
    # fail with a message about the source_hash
    with subtests.test("source_hash=None and skip_verify=False"):
        ret = file.patch(
            name=str(files.base_dir),
            source=patches.all_patch_template_http,
            template="jinja",
            context={"two": "two", "ten": 10},
            strip=1,
        )
        assert ret.result is False
        assert not ret.changes
        assert "Unable to verify upstream hash" in ret.comment

    # Re-run the state with a source hash, it should now succeed
    with subtests.test("source_hash!=None"):
        ret = file.patch(
            name=str(files.base_dir),
            source=patches.all_patch_template_http,
            source_hash=patches.all_patch_template_hash,
            template="jinja",
            context={"two": "two", "ten": 10},
            strip=1,
        )
        assert ret.result is True
        assert ret.changes
        assert ret.comment == "Patch successfully applied"
    with subtests.test("source_hash=None and skip_verify=True"):
        ret = file.patch(
            name=str(files.base_dir),
            source=patches.all_patch_template_http,
            template="jinja",
            context={"two": "two", "ten": 10},
            skip_verify=True,
            strip=1,
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Patch was already applied"


def test_patch_test_mode(file, files, patches):
    """
    Test file.patch using test=True
    """
    ret = file.patch(name=str(files.numbers), source=patches.numbers_patch, test=True)
    assert ret.result is None
    assert ret.changes
    assert ret.comment == "The patch would be applied"

    # Apply the patch for real. We'll then be able to test below that we
    # exit with a True rather than a None result if test=True is used on an
    # already-applied patch.
    ret = file.patch(name=str(files.numbers), source=patches.numbers_patch)
    assert ret.result is True
    assert ret.changes
    assert ret.comment == "Patch successfully applied"

    # Run again with test=True. Since the pre-check happens before we do
    # the __opts__['test'] check, we should exit with a True result just
    # the same as if we try to run this state on an already-patched file
    # *without* test=True.
    ret = file.patch(name=str(files.numbers), source=patches.numbers_patch, test=True)
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "Patch was already applied"

    # Empty the file to ensure that the patch doesn't apply cleanly
    files.numbers.write_text("")

    # Run again with test=True. Similar to the above run, we are testing
    # that we return before we reach the __opts__['test'] check. In this
    # case we should return a False result because we should already know
    # by this point that the patch will not apply cleanly.
    ret = file.patch(name=str(files.numbers), source=patches.numbers_patch, test=True)
    assert ret.result is False
    assert not ret.changes
    assert "Patch would not apply cleanly" in ret.comment

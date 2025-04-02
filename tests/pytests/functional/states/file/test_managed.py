import functools
import hashlib
import os
import shutil
import stat
import subprocess
import types

import psutil
import pytest

import salt.utils.files
import salt.utils.platform

try:
    import gnupg as gnupglib

    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False

pytestmark = [
    pytest.mark.windows_whitelisted,
]

IS_WINDOWS = salt.utils.platform.is_windows()
BINARY_FILE = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"


@pytest.fixture
def remote_grail_scene33(
    webserver,
    grail_scene33_file,
    grail_scene33_file_hash,
    grail_scene33_clearsign_file,
    grail_scene33_clearsign_file_hash,
):
    return types.SimpleNamespace(
        file=grail_scene33_file,
        file_clearsign=grail_scene33_clearsign_file,
        hash=grail_scene33_file_hash,
        hash_clearsign=grail_scene33_clearsign_file_hash,
        hash_file=grail_scene33_file.with_suffix(".SHA256"),
        url=webserver.url("grail/scene33"),
        url_hash=webserver.url("grail/scene33.SHA256"),
    )


@pytest.fixture
def gpghome(tmp_path):
    root = tmp_path / "gpghome"
    root.mkdir(mode=0o0700)
    try:
        yield root
    finally:
        # Make sure we don't leave any gpg-agents running behind
        gpg_connect_agent = shutil.which("gpg-connect-agent")
        if gpg_connect_agent:
            gnupghome = root / ".gnupg"
            if not gnupghome.is_dir():
                gnupghome = root
            try:
                subprocess.run(
                    [gpg_connect_agent, "killagent", "/bye"],
                    env={"GNUPGHOME": str(gnupghome)},
                    shell=False,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                # This is likely CentOS 7 or Amazon Linux 2
                pass

        # If the above errored or was not enough, as a last resort, let's check
        # the running processes.
        for proc in psutil.process_iter():
            try:
                if "gpg-agent" in proc.name():
                    for arg in proc.cmdline():
                        if str(root) in arg:
                            proc.terminate()
            except Exception:  # pylint: disable=broad-except
                pass


@pytest.fixture
def gnupg(gpghome):
    return gnupglib.GPG(gnupghome=str(gpghome))


@pytest.fixture
def a_pubkey():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4fxHQEEAJvXEaaw+o/yZCwMOJbt5FQHbVMMDX/0YI8UdzsE5YCC4iKnoC3x
FwFdkevKj3qp+45iBGLLnalfXIcVGXJGACB+tPHgsfHaXSDQPSfmX6jbZ6pHosSm
v1tTixY+NTJzGL7hDLz2sAXTbYmTbXeE9ifWWk6NcIwZivUbhNRBM+KxABEBAAG0
LUtleSBBIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5YUBleGFtcGxlPojR
BBMBCAA7FiEE7wN2X1nukEkwyKeBVTqCoFjAx5UFAmOH8R0CGy8FCwkIBwICIgIG
FQoJCAsCBBYCAwECHgcCF4AACgkQVTqCoFjAx5XURAQAguOwI+49lG0Kby+Bsyv3
of3GgxvhS1Qa7+ysj088az5GVt0pqVe3SbRVvn/jyC6yZvWuv94KdL3R7hCeEz2/
JakCRJ4wxEsdeASE8t9H/oTqD0I5asMa9EMvn5ICEGeLsTeQb7OYYihTQj7HJLG6
pDEmK8EhJDvV/9o0lnhm/9w=
=Wc0O
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def a_fp():
    return "EF03765F59EE904930C8A781553A82A058C0C795"


@pytest.fixture
def b_pubkey():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4fxNQEEAOgAzbpheJrOq4il5BrMVtP1G1kU94QX2+xLXEgW/wPdE4HD6Zbg
vliIg18v7Na4x8ubWy/7CkXC83EJ8SoSqcCccvuKjIWsm6tfeCidNstNCjewFMUR
7ZOQmAe/I2JAlz2SgNxS3ZDiCZpGkxqE0GZ+1N7Mz2WHImnExG149RVHABEBAAG0
LUtleSBCIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5YkBleGFtcGxlPojR
BBMBCAA7FiEEEYtPq3gDjLLfe2niD2xCJkdGXJMFAmOH8TUCGy8FCwkIBwICIgIG
FQoJCAsCBBYCAwECHgcCF4AACgkQD2xCJkdGXJNR3AQAk5ZoN+/ViIX3vA/LbXPn
2VE1E7ETTeIGqsb5f98UfjIbYfkNE8+OtnPxnDbSOPWBEOT+XPPjmxnE0a2UNTfn
ECO71/ZUiyC3ZN50IZ0vgzwBH+DeIV6PDAAun5FGx4RI7v6n0CPlrUcWKYe8wY1F
COflOxnEyLVHXnX8wUIzZwo=
=Hq0X
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def b_fp():
    return "118B4FAB78038CB2DF7B69E20F6C422647465C93"


@pytest.fixture
def pub_ec():
    return """\
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEACXBqu2ndMLUS/Z0X/fKUGAgRUfe
nYBie3erw/QNOYfQpgDIjNu+6xVxMLRRvSYGrQ2JREwUVXR0SR5pERAnoQ==
-----END PUBLIC KEY-----"""


@pytest.fixture
def pub_ec2():
    return """\
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErtBZ3qL5m97SzlSwOoxFzzG/1v5a
sLzOIrXykh4yO8tDn4h6JMOe+P0HuoUbENxk4+f/1D9hTEI88rj70bi7Ig==
-----END PUBLIC KEY-----"""


@pytest.fixture
def _gpg_keys_present(gnupg, a_pubkey, b_pubkey, a_fp, b_fp):
    pubkeys = [a_pubkey, b_pubkey]
    fingerprints = [a_fp, b_fp]
    gnupg.import_keys("\n".join(pubkeys))
    present_keys = gnupg.list_keys()
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_keys)
    yield
    # cleanup is taken care of by gpghome and tmp_path


def _format_ids(key, value):
    return f"{key}={value}"


def test_managed(file, tmp_path, grail_scene33_file):
    """
    file.managed
    """
    name = tmp_path / "grail_scene33"
    ret = file.managed(name=str(name), source="salt://grail/scene33")
    fileserver_data = grail_scene33_file.read_text()
    local_data = name.read_text()
    assert local_data == fileserver_data
    assert ret.result is True


def test_managed_test(file, tmp_path, grail_scene33_file):
    """
    file.managed test interface
    """
    name = tmp_path / "grail_scene33"
    ret = file.managed(name=str(name), source="salt://grail/scene33", test=True)
    assert ret.result is None
    assert name.exists() is False


def test_managed_file_mode(file, tmp_path, grail_scene33_file):
    """
    file.managed, correct file permissions
    """
    desired_mode = "0o770"  # 0770 octal
    name = tmp_path / "grail_scene33"
    ret = file.managed(name=str(name), mode="0770", source="salt://grail/scene33")

    if IS_WINDOWS:
        assert ret.result is False
        assert ret.comment == "The 'mode' option is not supported on Windows"
    else:
        assert ret.result is True
        resulting_mode = stat.S_IMODE(name.stat().st_mode)
        assert oct(resulting_mode) == desired_mode


@pytest.mark.parametrize(
    "mode",
    [0o650, 0o645],  # Yes, the modes are "weird" on purpose
    ids=functools.partial(_format_ids, "mode"),
)
@pytest.mark.parametrize(
    "local", [False, True], ids=functools.partial(_format_ids, "local")
)
@pytest.mark.skip_on_windows(reason="Windows does not report any file modes. Skipping.")
def test_managed_file_mode_keep(file, tmp_path, grail_scene33_file, local, mode):
    """
    Test using "mode: keep" in a file.managed state
    """
    name = tmp_path / "grail_scene33"

    # Set the mode we want to keep
    grail_scene33_file.chmod(mode)

    if local is True:
        source = str(grail_scene33_file)
    else:
        source = "salt://grail/scene33"

    ret = file.managed(name=str(name), mode="keep", source=source, local=local)
    assert ret.result is True
    # Ensure the mode on the dest file is the same as the source file
    assert stat.S_IMODE(name.stat().st_mode) == mode


@pytest.mark.parametrize(
    "mode",
    [0o650, 0o645],  # Yes, the modes are "weird" on purpose
    ids=functools.partial(_format_ids, "mode"),
)
@pytest.mark.parametrize(
    "replace", [False, True], ids=functools.partial(_format_ids, "replace")
)
@pytest.mark.skip_on_windows(reason="Windows does not report any file modes. Skipping.")
def test_managed_file_mode_file_exists_replace(
    file, tmp_path, grail_scene33_file, mode, replace
):
    """
    file.managed, existing file with replace=True, change permissions
    """
    name = tmp_path / "grail_scene33"
    # Set the mode on the state tree file to 0600
    grail_scene33_file.chmod(0o600)
    # The file should exist, copy it
    shutil.copyfile(str(grail_scene33_file), str(name))
    shutil.copymode(str(grail_scene33_file), str(name))

    # The initial mode of the fail should not match the mode we want
    assert stat.S_IMODE(name.stat().st_mode) != mode

    # Regardless if the file was replaced or not, the mode should be updated
    ret = file.managed(
        name=str(name), mode=oct(mode), replace=replace, source="salt://grail/scene33"
    )
    assert ret.result is True

    assert stat.S_IMODE(name.stat().st_mode) == mode


def test_managed_file_with_grains_data(file, tmp_path, state_tree, minion_id):
    """
    Test to ensure we can render grains data into a managed
    file.
    """
    name = tmp_path / "grains-get-contents.txt"
    tmpl_contents = """
    {{ salt['grains.get']('id') }}
    """
    with pytest.helpers.temp_file("grainsget.tmpl", tmpl_contents, state_tree):
        ret = file.managed(
            name=str(name), source="salt://grainsget.tmpl", template="jinja"
        )
    assert ret.result is True
    assert name.is_file()
    assert name.read_text().strip() == minion_id


@pytest.mark.skip_on_windows(reason="Windows does not report any file modes. Skipping.")
def test_managed_dir_mode(file, tmp_path, grail_scene33_file):
    """
    Tests to ensure that file.managed creates directories with the
    permissions requested with the dir_mode argument
    """
    desired_mode = 0o777
    name = tmp_path / "a" / "managed_dir_mode_test_file"
    ret = file.managed(
        name=str(name),
        source="salt://grail/scene33",
        mode="600",
        makedirs=True,
        dir_mode=oct(desired_mode),  # 0777
    )
    assert ret.result is True
    # Sanity check. File exists and contents match
    assert name.exists()
    assert name.read_text() == grail_scene33_file.read_text()
    # Now the real test, the created directories mode match
    resulting_mode = stat.S_IMODE(name.parent.stat().st_mode)
    assert resulting_mode == desired_mode


@pytest.mark.parametrize(
    "show_changes", [False, True], ids=functools.partial(_format_ids, "show_changes")
)
def test_managed_show_changes_false(file, tmp_path, grail_scene33_file, show_changes):
    """
    file.managed test interface
    """
    name = tmp_path / "grail_not_scene33"
    name.write_text("test_managed_show_changes_false\n")

    ret = file.managed(
        name=str(name), source="salt://grail/scene33", show_changes=False
    )
    assert ret.result is True

    assert name.exists()

    if show_changes is True:
        assert "diff" in ret.changes
    else:
        assert ret.changes["diff"] == "<show_changes=False>"


@pytest.mark.skip_on_windows(reason="Don't know how to fix for Windows")
def test_managed_escaped_file_path(file, tmp_path, state_tree):
    """
    file.managed test that 'salt://|' protects unusual characters in file path
    """
    funny_file = tmp_path / "?f!le? n@=3&-blah-.file type"
    funny_url = f"salt://|{funny_file.name}"
    with pytest.helpers.temp_file(funny_file.name, "", state_tree):
        ret = file.managed(name=str(funny_file), source=funny_url)
    assert ret.result is True
    assert funny_file.exists()


@pytest.mark.parametrize(
    "name, contents",
    [
        ("bool", True),
        ("str", "Salt was here."),
        ("int", 340282366920938463463374607431768211456),
        ("float", 1.7518e-45),  # gravitational coupling constant
        ("list", [1, 1, 2, 3, 5, 8, 13]),
        ("dict", {"C": "charge", "P": "parity", "T": "time"}),
    ],
)
def test_managed_contents(file, tmp_path, name, contents):
    """
    test file.managed with contents that is a boolean, string, integer,
    float, list, and dictionary
    """
    name = tmp_path / f"managed-{name}"
    ret = file.managed(name=str(name), contents=contents)
    assert ret.result is True
    assert "diff" in ret.changes
    assert name.exists()


@pytest.mark.parametrize(
    "contents",
    [
        # Single Line
        "the contents of the file",
        "the contents of the file\n",
        "the contents of the file\n\n",
        # Multiple lines
        "this is a cookie\nthis is another cookie",
        "this is a cookie\nthis is another cookie\n",
        "this is a cookie\nthis is another cookie\n\n",
    ],
)
def test_managed_contents_with_contents_newline(file, tmp_path, contents):
    """
    test file.managed with contents by using the default contents_newline flag.
    """
    name = tmp_path / "foo"

    # Create a file named foo with contents as above but with a \n at EOF
    ret = file.managed(name=str(name), contents=contents, contents_newline=True)
    assert ret.result is True
    assert name.exists()
    expected = contents
    if not expected.endswith("\n"):
        expected += "\n"
    assert name.read_text() == expected


@pytest.mark.skip_on_windows(reason="Windows does not report any file modes. Skipping.")
def test_managed_check_cmd(file, tmp_path):
    """
    Test file.managed passing a basic check_cmd kwarg. See Issue #38111.
    """
    name = tmp_path / "sudoers"
    ret = file.managed(name=str(name), mode="0440", check_cmd="test -f")
    assert ret.result is True
    assert "Empty file" in ret.comment
    assert ret.changes == {
        "new": f"file {name} created",
        "mode": "0440",
    }


@pytest.mark.parametrize("proto", ["file://", ""])
@pytest.mark.parametrize("dest_file_exists", [False, True])
def test_managed_local_source_with_source_hash(
    file, tmp_path, grail_scene33_file, grail_scene33_file_hash, proto, dest_file_exists
):
    """
    Make sure that we enforce the source_hash even with local files
    """
    name = tmp_path / "local_source_with_source_hash"

    if dest_file_exists:
        name.touch()

    # Test with wrong hash
    bad_hash = grail_scene33_file_hash[::-1]

    ret = file.managed(
        name=str(name),
        source=proto + str(grail_scene33_file),
        source_hash=f"sha256={bad_hash}",
    )
    assert ret.result is False
    assert not ret.changes
    assert "does not match actual checksum" in ret.comment

    # Now with the right hash
    ret = file.managed(
        name=str(name),
        source=proto + str(grail_scene33_file),
        source_hash=f"sha256={grail_scene33_file_hash}",
    )
    assert ret.result is True


@pytest.mark.parametrize("proto", ["file://", ""])
def test_managed_local_source_does_not_exist(file, tmp_path, grail_scene33_file, proto):
    """
    Make sure that we exit gracefully when a local source doesn't exist
    """
    name = tmp_path / "local_source_does_not_exist"

    ret = file.managed(
        name=str(name),
        source=proto + str(grail_scene33_file.with_name("scene99")),
    )
    assert ret.result is False
    assert not ret.changes
    assert "does not exist" in ret.comment


def test_managed_unicode_jinja_with_tojson_filter(file, tmp_path, state_tree, modules):
    """
    Using {{ varname }} with a list or dictionary which contains unicode
    types on Python 2 will result in Jinja rendering the "u" prefix on each
    string. This tests that using the "tojson" jinja filter will dump them
    to a format which can be successfully loaded by our YAML loader.

    The two lines that should end up being rendered are meant to test two
    issues that would trip up PyYAML if the "tojson" filter were not used:

    1. A unicode string type would be loaded as a unicode literal with the
       leading "u" as well as the quotes, rather than simply being loaded
       as the proper unicode type which matches the content of the string
       literal. In other words, u'foo' would be loaded literally as
       u"u'foo'". This test includes actual non-ascii unicode in one of the
       strings to confirm that this also handles these international
       characters properly.

    2. Any unicode string type (such as a URL) which contains a colon would
       cause a ScannerError in PyYAML, as it would be assumed to delimit a
       mapping node.

    Dumping the data structure to JSON using the "tojson" jinja filter
    should produce an inline data structure which is valid YAML and will be
    loaded properly by our YAML loader.
    """
    if salt.utils.platform.is_windows() and os.environ.get("PYTHONUTF8", "0") == "0":
        pytest.skip("Test will fail if PYTHONUTF8=1 is not set on windows")
    test_file = tmp_path / "test-tojson.txt"
    jinja_template_contents = """
    {%- for key in ('Die Webseite', 'Der Zucker') -%}
    {{ key }} ist {{ data[key] }}.
    {% endfor -%}
    """
    sls_contents = (
        """
        {%- set data = '{"Der Zucker": "süß", "Die Webseite": "https://saltproject.io"}'|load_json -%}
        """
        + str(test_file)
        + """:
          file.managed:
            - source: salt://template.jinja
            - template: jinja
            - context:
                data: {{ data|tojson }}
        """
    )
    with pytest.helpers.temp_file(
        "template.jinja", jinja_template_contents, state_tree
    ), pytest.helpers.temp_file("tojson.sls", sls_contents, state_tree):
        ret = modules.state.apply("tojson")
        for state_run in ret:
            assert state_run.result is True

    expected = "Die Webseite ist https://saltproject.io.\nDer Zucker ist süß.\n\n"
    assert test_file.read_text() == expected


@pytest.mark.parametrize("test", [False, True])
def test_managed_source_hash_indifferent_case(file, tmp_path, state_tree, test):
    """
    Test passing a source_hash as an uppercase hash.

    This is a regression test for Issue #38914 and Issue #48230 (test=true use).
    """
    name = tmp_path / "source_hash_indifferent_case"
    hello_world_contents = "Hello, World!"
    with pytest.helpers.temp_file(
        "hello_world.txt", hello_world_contents, state_tree
    ) as local_path:
        actual_hash = hashlib.sha256(local_path.read_bytes()).hexdigest()

        # `name` needs to exist for this test, like a previous file.managed run
        shutil.copyfile(str(local_path), str(name))

        # Test uppercase source_hash: should return True with no changes
        ret = file.managed(
            name=str(name),
            source=str(local_path),
            source_hash=actual_hash.upper(),
            test=test,
        )
        assert ret.result is True
        assert ret.changes == {}


def test_managed_latin1_diff(file, tmp_path, state_tree):
    """
    Tests that latin-1 file contents are represented properly in the diff
    """
    contents = "<html>\n<body>\n{}</body>\n</html>\n"
    testfile = tmp_path / "issue-48777.html"
    testfile.write_text(contents.format(""))

    # Replace it with the new file and check the diff
    with pytest.helpers.temp_file("issue-48777.html", "", state_tree) as src:
        src.write_bytes(contents.format("räksmörgås").encode("latin1"))

        ret = file.managed(name=str(testfile), source="salt://issue-48777.html")
        assert ret.result is True
        assert "+räksmörgås" in ret.changes["diff"]


def test_managed_keep_source_false_salt(modules, file, grail_scene33_file, tmp_path):
    """
    This test ensures that we properly clean the cached file if keep_source
    is set to False, for source files using a salt:// URL
    """

    name = tmp_path / "grail_scene33"
    source = "salt://grail/scene33"
    saltenv = "base"

    # Check that it's not cached already
    ret = modules.cp.is_cached(source, saltenv)
    assert ret == ""

    # Let's try caching it
    ret = file.managed(name=str(name), source=source, saltenv=saltenv, keep_source=True)
    assert ret.result is True

    # Now make sure that the file is cached
    ret = modules.cp.is_cached(source, saltenv)
    assert ret != ""

    # Delete the test file
    name.unlink()

    # Run the state
    ret = file.managed(
        name=str(name), source=source, saltenv=saltenv, keep_source=False
    )
    assert ret.result is True

    # Now make sure that the file is still not cached
    ret = modules.cp.is_cached(source, saltenv)
    assert ret == ""


@pytest.mark.parametrize("requisite", ["onchanges", "prereq"])
def test_file_managed_requisites(modules, tmp_path, state_tree, requisite):
    """
    Test file.managed state with onchanges
    """
    file1 = tmp_path / "file1"
    file2 = tmp_path / "file2"

    sls_contents = """
    one:
      file.managed:
        - name: {file1}
        - source: salt://testfile

    # This should run because there were changes
    two:
      test.succeed_without_changes:
        - {requisite}:
          - file: one

    # Run the same state as "one" again, this should not cause changes
    three:
      file.managed:
        - name: {file2}
        - source: salt://testfile

    # This should not run because there should be no changes
    four:
      test.succeed_without_changes:
        - {requisite}:
          - file: three
    """.format(
        file1=file1, file2=file2, requisite=requisite
    )
    testfile_contents = "The test file contents!\n"

    # Lay down the file used in the below SLS to ensure that when it is
    # run, there are no changes.
    file2.write_text(testfile_contents)

    with pytest.helpers.temp_file(
        "onchanges-prereq.sls", sls_contents, state_tree
    ), pytest.helpers.temp_file("testfile", testfile_contents, state_tree):
        ret = modules.state.apply("onchanges-prereq", test=True)

        # The file states should both exit with None
        assert ret["one"].result is None
        assert ret["three"].result is True
        # The first file state should have changes, since a new file was
        # created. The other one should not, since we already created that file
        # before applying the SLS file.
        assert ret["one"].changes
        assert not ret["three"].changes
        # The state watching 'one' should have been run due to changes
        assert ret["two"].comment == "Success!"
        # The state watching 'three' should not have been run
        if requisite == "onchanges":
            expected_comment = (
                "State was not run because none of the onchanges reqs changed"
            )
        else:
            expected_comment = "No changes detected"
        assert ret["four"].comment == expected_comment


@pytest.mark.parametrize("prefix", ("", "file://"))
def test_template_local_file(file, tmp_path, prefix):
    """
    Test a file.managed state with a local file as the source. Test both
    with the file:// protocol designation prepended, and without it.
    """
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.write_text("{{ foo }}\n")

    ret = file.managed(
        name=str(dest),
        source=f"{prefix}{source}",
        template="jinja",
        context={"foo": "Hello world!"},
    )
    assert ret.result is True
    assert dest.read_text() == "Hello world!\n"


def test_template_local_file_noclobber(file, tmp_path):
    """
    Test the case where a source file is in the minion's local filesystem,
    and the source path is the same as the destination path.
    """
    source = dest = tmp_path / "source"
    source.write_text("{{ foo }}\n")

    ret = file.managed(
        name=str(dest),
        source=str(source),
        template="jinja",
        context={"foo": "Hello world!"},
    )
    assert ret.result is False
    assert "Source file cannot be the same as destination" in ret.comment


def test_binary_contents(file, tmp_path):
    """
    This tests to ensure that binary contents do not cause a traceback.
    """
    name = tmp_path / "1px.gif"
    ret = file.managed(name=str(name), contents=BINARY_FILE)
    assert ret.result is True


def test_binary_contents_twice(file, tmp_path):
    """
    This test ensures that after a binary file is created, salt can confirm
    that the file is in the correct state.
    """
    name = tmp_path / "1px.gif"

    # First run state ensures file is created
    ret = file.managed(name=str(name), contents=BINARY_FILE)
    assert ret.result is True

    # Second run of state ensures file is in correct state
    ret = file.managed(name=str(name), contents=BINARY_FILE)
    assert ret.result is True


def test_issue_8947_utf8_sls(modules, tmp_path, state_tree, subtests):
    """
    Test some file operation with utf-8 characters on the sls

    This is more generic than just a file test. Feel free to move
    """
    if salt.utils.platform.is_windows() and os.environ.get("PYTHONUTF8", "0") == "0":
        pytest.skip("Test will fail if PYTHONUTF8=1 is not set on windows")
    korean_1 = "한국어 시험"
    korean_2 = "첫 번째 행"
    korean_3 = "마지막 행"
    test_file = tmp_path / f"{korean_1}.txt"
    with subtests.test(f"test_file={test_file}"):
        # create the sls template
        sls_contents = """
        some-utf8-file-create:
          file.managed:
            - name: {test_file}
            - contents: {korean_1}
        """.format(
            test_file=test_file.as_posix().replace("\\", "/"),
            korean_1=korean_1,
        )
        with pytest.helpers.temp_file(
            "issue-8947.sls", directory=state_tree, contents=sls_contents
        ):
            ret = modules.state.sls("issue-8947")
            for state_run in ret:
                assert state_run.result is True

        assert test_file.read_text() == f"{korean_1}\n"

    test_file = tmp_path / f"{korean_2}.txt"
    with subtests.test(f"test_file={test_file}"):
        sls_contents = """
        some-utf8-file-create2:
          file.managed:
            - name: {test_file}
            - contents: |
               {korean_2}
               {korean_1}
               {korean_3}
        """.format(
            test_file=test_file.as_posix().replace("\\", "/"),
            korean_1=korean_1,
            korean_2=korean_2,
            korean_3=korean_3,
        )
        with pytest.helpers.temp_file(
            "issue-8947.sls", directory=state_tree, contents=sls_contents
        ):
            ret = modules.state.sls("issue-8947")
            for state_run in ret:
                assert state_run.result is True

        assert test_file.read_text() == "{}\n{}\n{}\n".format(
            korean_2, korean_1, korean_3
        )


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="Windows does not support setuid. Skipping.")
def test_owner_after_setuid(file, modules, tmp_path, state_file_account):
    """
    Test to check file user/group after setting setuid or setgid.
    Because Python os.chown() does reset the setuid/setgid to 0.
    https://github.com/saltstack/salt/pull/45257

    See also issue #48336
    """

    # Desired configuration.
    desired_file = tmp_path / "file_with_setuid"
    mode = "4750"

    # Run the state.
    ret = file.managed(
        name=str(desired_file),
        user=state_file_account.username,
        group=state_file_account.group.name,
        mode=mode,
    )
    assert ret.result is True
    # Check result.
    user_check = modules.file.get_user(str(desired_file))
    assert user_check == state_file_account.username
    group_check = modules.file.get_group(str(desired_file))
    assert group_check == state_file_account.group.name
    mode_check = modules.file.get_mode(str(desired_file))
    assert salt.utils.files.normalize_mode(mode_check) == mode


def test_managed_file_issue_51208(file, tmp_path, state_tree):
    """
    Test to ensure we can handle a file with escaped double-quotes
    """
    vimrc_contents = """
    set number
    syntax on
    set paste
    set ruler
    if has("autocmd")
      au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g'\"" | endif
    endif

    """
    with pytest.helpers.temp_file(
        "vimrc.stub", directory=state_tree / "issue-51208", contents=vimrc_contents
    ) as vimrc_file:
        name = tmp_path / "issue_51208.txt"
        ret = file.managed(name=str(name), source="salt://issue-51208/vimrc.stub")
        assert ret.result is True
        assert name.read_text() == vimrc_file.read_text()


def test_file_managed_http_source_no_hash(file, tmp_path, remote_grail_scene33):
    """
    Test a remote file with no hash
    """
    name = str(tmp_path / "testfile")
    ret = file.managed(name=name, source=remote_grail_scene33.url, skip_verify=False)
    # This should fail because no hash was provided
    assert ret.result is False


def test_file_managed_http_source(file, tmp_path, remote_grail_scene33):
    """
    Test a remote file with no hash
    """
    name = str(tmp_path / "testfile")
    ret = file.managed(
        name=name,
        source=remote_grail_scene33.url,
        source_hash=remote_grail_scene33.hash,
        skip_verify=False,
    )
    assert ret.result is True


def test_file_managed_http_source_skip_verify(file, tmp_path, remote_grail_scene33):
    """
    Test a remote file using skip_verify
    """
    name = str(tmp_path / "testfile")
    ret = file.managed(name=name, source=remote_grail_scene33.url, skip_verify=True)
    assert ret.result is True


def test_file_managed_keep_source_false_http(
    file, tmp_path, remote_grail_scene33, modules
):
    """
    This test ensures that we properly clean the cached file if keep_source
    is set to False, for source files using an http:// URL
    """
    name = str(tmp_path / "testfile")
    # Run the state
    ret = file.managed(
        name=name,
        source=remote_grail_scene33.url,
        source_hash=remote_grail_scene33.hash,
        keep_source=False,
    )
    assert ret.result is True

    # Now make sure that the file is not cached
    ret = modules.cp.is_cached(remote_grail_scene33.url)
    assert not ret, f"File is still cached at {ret}"


@pytest.mark.parametrize("verify_ssl", [True, False])
def test_verify_ssl_https_source(file, tmp_path, ssl_webserver, verify_ssl):
    """
    test verify_ssl when its False and True when managing
    a file with an https source and skip_verify is false.
    """
    name = tmp_path / "test_verify_ssl_true.txt"
    source = ssl_webserver.url("this.txt")
    source_hash = f"{source}.sha256"

    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        verify_ssl=verify_ssl,
        skip_verify=False,
    )
    if verify_ssl is True:
        assert ret.result is False
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.comment
        assert not name.exists()
    else:
        if IS_WINDOWS and not os.environ.get("GITHUB_ACTIONS_PIPELINE"):
            pytest.xfail(
                "This test fails when running from Jenkins but not on the GitHub "
                "Actions Pipeline"
            )
        assert ret.result is True
        assert ret.changes
        # mode, if present is not important for this test
        ret.changes.pop("mode", None)
        assert ret.changes == {"diff": "New file"}
        assert name.exists()


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("_gpg_keys_present")
@pytest.mark.parametrize("signature", [True, ".asc"])
def test_file_managed_signature(
    file, tmp_path, signature, remote_grail_scene33, gpghome
):
    name = tmp_path / "test_file_managed_signature.txt"
    source = remote_grail_scene33.url
    if signature is True:
        source += ".clearsign.asc"
        contents_file = remote_grail_scene33.file_clearsign
        source_hash = remote_grail_scene33.hash_clearsign
    else:
        signature = source + signature
        contents_file = remote_grail_scene33.file
        source_hash = remote_grail_scene33.hash
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        signature=signature,
        gnupghome=str(gpghome),
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert name.read_text() == contents_file.read_text()


@pytest.mark.requires_salt_modules("asymmetric.verify")
@pytest.mark.parametrize("is_list", (False, True))
def test_file_managed_signature_sig_backend(
    file, tmp_path, remote_grail_scene33, pub_ec, pub_ec2, is_list
):
    name = tmp_path / "test_file_managed_signature.txt"
    source = remote_grail_scene33.url
    signature = source + ".sig"
    contents_file = remote_grail_scene33.file
    source_hash = remote_grail_scene33.hash
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        signature=[signature] if is_list else signature,
        signed_by_any=[pub_ec2, pub_ec] if is_list else pub_ec,
        sig_backend="asymmetric",
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert name.read_text() == contents_file.read_text()


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("_gpg_keys_present")
def test_file_managed_signature_fail(
    file, tmp_path, remote_grail_scene33, gpghome, modules
):
    name = tmp_path / "test_file_managed_signature_fail.txt"
    source = remote_grail_scene33.url
    signature = source + ".asc"
    source_hash = remote_grail_scene33.hash
    # although there are valid signatures, this will be denied since the one below is required
    signed_by_all = ["DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"]
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        signature=signature,
        gnupghome=str(gpghome),
        signed_by_all=signed_by_all,
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()
    # Ensure that a new state run will attempt to redownload the source
    # instead of verifying the invalid signature again
    assert not modules.cp.is_cached(source)
    assert not modules.cp.is_cached(signature)


@pytest.mark.requires_salt_modules("asymmetric.verify")
def test_file_managed_signature_sig_backend_fail(
    file, tmp_path, remote_grail_scene33, pub_ec2, modules
):
    name = tmp_path / "test_file_managed_signature.txt"
    source = remote_grail_scene33.url
    signature = source + ".sig"
    source_hash = remote_grail_scene33.hash
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        signature=[signature],
        signed_by_any=pub_ec2,
        sig_backend="asymmetric",
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()
    # Ensure that a new state run will attempt to redownload the source
    # instead of verifying the invalid signature again
    assert not modules.cp.is_cached(source)
    assert not modules.cp.is_cached(signature)


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("_gpg_keys_present")
@pytest.mark.parametrize("sig", [True, ".asc"])
def test_file_managed_source_hash_sig(
    file, tmp_path, sig, remote_grail_scene33, gpghome
):
    name = tmp_path / "test_file_managed_source_hash_sig.txt"
    source = remote_grail_scene33.url
    source_hash = remote_grail_scene33.url_hash
    contents_file = remote_grail_scene33.file
    if sig is True:
        source_hash += ".clearsign.asc"
    else:
        sig = source_hash + sig
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        source_hash_sig=sig,
        gnupghome=str(gpghome),
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert name.read_text() == contents_file.read_text()


@pytest.mark.requires_salt_modules("asymmetric.verify")
@pytest.mark.parametrize("is_list", (False, True))
def test_file_managed_source_hash_sig_sig_backend(
    file, tmp_path, remote_grail_scene33, pub_ec, pub_ec2, is_list
):
    name = tmp_path / "test_file_managed_source_hash_sig.txt"
    source = remote_grail_scene33.url
    source_hash = remote_grail_scene33.url_hash
    contents_file = remote_grail_scene33.file
    signature = source_hash + ".sig"
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        source_hash_sig=[signature] if is_list else signature,
        signed_by_any=[pub_ec2, pub_ec] if is_list else pub_ec,
        sig_backend="asymmetric",
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert name.read_text() == contents_file.read_text()


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("_gpg_keys_present")
def test_file_managed_source_hash_sig_fail(
    file, tmp_path, remote_grail_scene33, gpghome
):
    name = tmp_path / "test_file_managed_source_hash_sig.txt"
    source = remote_grail_scene33.url
    source_hash = remote_grail_scene33.url_hash
    sig = source_hash + ".asc"
    signed_by_all = ["DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"]
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        source_hash_sig=sig,
        gnupghome=str(gpghome),
        signed_by_all=signed_by_all,
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()


@pytest.mark.requires_salt_modules("asymmetric.verify")
def test_file_managed_source_hash_sig_sig_backend_fail(
    file, tmp_path, remote_grail_scene33, pub_ec2
):
    name = tmp_path / "test_file_managed_source_hash_sig.txt"
    source = remote_grail_scene33.url
    source_hash = remote_grail_scene33.url_hash
    signature = source_hash + ".sig"
    ret = file.managed(
        str(name),
        source=source,
        source_hash=source_hash,
        source_hash_sig=[signature],
        signed_by_any=pub_ec2,
        sig_backend="asymmetric",
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()


def test_issue_60203(
    file,
    tmp_path,
):
    name = tmp_path / "test.tar.gz"
    source = "https://account:dontshowme@notahost.saltstack.io/files/test.tar.gz"
    source_hash = (
        "https://account:dontshowme@notahost.saltstack.io/files/test.tar.gz.sha256"
    )
    ret = file.managed(str(name), source=source, source_hash=source_hash)
    assert ret.result is False
    assert ret.comment
    assert "Unable to manage file" in ret.comment
    assert "/files/test.tar.gz.sha256" in ret.comment
    assert "dontshowme" not in ret.comment


def test_file_managed_new_file_diff(file, tmp_path):
    name = tmp_path / "new_file_diff.txt"
    ret = file.managed(str(name), contents="EITR", new_file_diff=True, test=True)
    assert ret.changes == {
        "diff": f"--- \n+++ \n@@ -0,0 +1 @@\n+EITR{os.linesep}",
    }
    assert not name.exists()
    ret = file.managed(str(name), contents="EITR", new_file_diff=True)
    assert ret.changes == {"diff": f"--- \n+++ \n@@ -0,0 +1 @@\n+EITR{os.linesep}"}
    assert name.exists()


def test_file_managed_remote_source_does_not_refetch_existing_file_with_correct_digest(
    file, tmp_path, grail_scene33_file, grail_scene33_file_hash
):
    """
    If an existing file is managed from a remote source and its source hash is
    known beforehand, ensure that `file.managed` checks the local file's digest
    and if it matches the expected one, does not download the file to the local
    cache unnecessarily.
    This is especially important when huge files are managed with `keep_source`
    set to False.
    Issue #64373
    """
    name = tmp_path / "scene33"
    name.write_bytes(grail_scene33_file.read_bytes())
    ret = file.managed(
        str(name),
        source="http://127.0.0.1:1337/does/not/exist",
        source_hash=grail_scene33_file_hash,
    )
    assert ret.result is True
    assert not ret.changes

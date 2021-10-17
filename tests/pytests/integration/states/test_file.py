"""
Tests for the file state
"""
import logging
import os
import pathlib
import re
import textwrap

import pytest
import salt.utils.files
import salt.utils.path
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def context():
    return {"two": "two", "ten": 10}


@pytest.fixture
def content():
    numbers_file_contents = textwrap.dedent(
        """\
    one
    two
    three

    1
    2
    3
    """
    )
    math_file_contents = textwrap.dedent(
        """\
    Five plus five is ten

    Four squared is sixteen
    """
    )
    return numbers_file_contents, math_file_contents


@pytest.fixture
def patch_file_dest(base_env_state_tree_root_dir):
    yield pathlib.Path(base_env_state_tree_root_dir).resolve()


@pytest.fixture
def all_patch_file():
    return os.path.join("salt://", "patches/", "all.patch")


@pytest.fixture
def numbers_patch_file():
    return os.path.join("salt://", "patches/", "numbers.patch")


@pytest.fixture
def math_patch_file():
    return os.path.join("salt://", "patches/", "math.patch")


@pytest.fixture
def numbers_patch_template():
    return os.path.join("salt://", "patches/", "numbers.patch.jinja")


@pytest.fixture
def all_patch_template():
    return os.path.join("salt://", "patches/", "all.patch.jinja")


@pytest.fixture(scope="module")
def pillar_tree(salt_master, salt_minion, salt_call_cli):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = """
    monty: python
    companions:
      three:
        - liz
        - jo
        - sarah jane
    """
    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    basic_tempfile = salt_master.pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    )

    try:
        with top_tempfile, basic_tempfile:
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.exitcode == 0
            assert ret.json is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True


@pytest.mark.skip_on_windows
def test_verify_ssl_skip_verify_false(
    salt_master, salt_call_cli, tmpdir, ssl_webserver
):
    """
    test verify_ssl when its False and True when managing
    a file with an https source and skip_verify is false.
    """
    web_file = ssl_webserver.url("this.txt")
    true_content = """
    test_verify_ssl:
      file.managed:
        - name: {}
        - source: {}
        - source_hash: {}
    """.format(
        tmpdir.join("test_verify_ssl_true.txt"), web_file, web_file + ".sha256"
    )

    false_content = true_content + "    - verify_ssl: False"

    # test when verify_ssl is True
    with salt_master.state_tree.base.temp_file(
        "verify_ssl.sls", true_content
    ) as sfpath:
        ret = salt_call_cli.run("--local", "state.apply", "verify_ssl")
        assert ret.exitcode == 1
        assert (
            "SSL: CERTIFICATE_VERIFY_FAILED"
            in ret.json[next(iter(ret.json))]["comment"]
        )

    # test when verify_ssl is False
    with salt_master.state_tree.base.temp_file(
        "verify_ssl.sls", false_content
    ) as sfpath:
        ret = salt_call_cli.run("--local", "state.apply", "verify_ssl")
        assert ret.exitcode == 0
        assert ret.json[next(iter(ret.json))]["changes"] == {
            "diff": "New file",
            "mode": "0644",
        }


def test_contents_pillar_with_pillar_list(
    salt_master, salt_call_cli, pillar_tree, tmp_path
):
    """
    This tests for any regressions for this issue:
    https://github.com/saltstack/salt/issues/30934
    """
    target_path = tmp_path / "add-contents-pillar-target.txt"
    sls_name = "file-contents-pillar"
    sls_contents = """
    add_contents_pillar_sls:
      file.managed:
        - name: {}
        - contents_pillar: companions:three
    """.format(
        target_path
    )
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.sls", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()


def test_managed_file_with_pillar_sls(
    salt_master, salt_call_cli, pillar_tree, tmp_path
):
    """
    Test to ensure pillar data in sls file
    is rendered properly and file is created.
    """
    ret = salt_call_cli.run("pillar.get", "monty")
    assert ret.exitcode == 0
    assert ret.json

    target_path = tmp_path / "file-pillar-{}-target.txt".format(ret.json)
    sls_name = "file-pillar-get"
    sls_contents = (
        """
    {%- set filedir = '"""
        + str(tmp_path).replace("\\", "/")
        + """' %}
    {%- set filename = "file-pillar-{}-target.txt".format(salt["pillar.get"]("monty", "")) %}
    create-file:
      file.managed:
        - name: {{ filedir | path_join(filename) }}
    """
    )
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.sls", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()


def test_issue_50221(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
    ext_pillar_file_tree_root_dir,
):
    expected_content = "abc\n\n\n"
    target_path = tmp_path / "issue-50221-target.txt"
    sls_name = "issue-50221"
    sls_contents = """
    {{ pillar["target-path"] }}:
      file.managed:
        - contents_pillar: issue-50221
    """
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    issue_50221_ext_pillar_tempfile = pytest.helpers.temp_file(
        "issue-50221",
        expected_content,
        ext_pillar_file_tree_root_dir / "hosts" / salt_minion.id,
    )
    with sls_tempfile, issue_50221_ext_pillar_tempfile:
        ret = salt_call_cli.run("pillar.get", "issue-50221")
        assert ret.exitcode == 0
        assert ret.json
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert ret.json.replace("\r\n", "\n") == expected_content
        ret = salt_call_cli.run(
            "state.apply", sls_name, pillar={"target-path": str(target_path)}
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert target_path.read_text().replace("\r\n", "\n") == expected_content


def test_issue_60426(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
):
    target_path = tmp_path / "/etc/foo/bar"
    jinja_name = "foo_bar"
    jinja_contents = (
        "{% for item in accumulator['accumulated configstuff'] %}{{ item }}{% endfor %}"
    )

    sls_name = "issue-60426"
    sls_contents = """
    configuration file:
      file.managed:
        - name: {target_path}
        - source: salt://foo_bar.jinja
        - template: jinja
        - makedirs: True

    accumulated configstuff:
      file.accumulated:
        - filename: {target_path}
        - text:
          - some
          - good
          - stuff
        - watch_in:
          - configuration file
    """.format(
        target_path=target_path
    )

    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )

    jinja_tempfile = salt_master.state_tree.base.temp_file(
        "{}.jinja".format(jinja_name), jinja_contents
    )

    with sls_tempfile, jinja_tempfile:
        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert target_path.read_text() == "somegoodstuff"

    sls_name = "issue-60426"
    sls_contents = """
    configuration file:
      file.managed:
        - name: {target_path}
        - source: salt://foo_bar.jinja
        - template: jinja
        - makedirs: True

    accumulated configstuff:
      file.accumulated:
        - filename: {target_path}
        - text:
          - some
          - good
          - stuff
        - watch_in:
          - file: configuration file
    """.format(
        target_path=target_path
    )

    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )

    jinja_tempfile = salt_master.state_tree.base.temp_file(
        "{}.jinja".format(jinja_name), jinja_contents
    )

    with sls_tempfile, jinja_tempfile:
        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert target_path.read_text() == "somegoodstuff"


def test_issue_60203(
    salt_master,
    salt_call_cli,
    tmp_path,
    salt_minion,
):
    target_path = tmp_path / "issue-60203-target.txt"
    sls_name = "issue-60203"
    sls_contents = """
    credentials exposed via file:
      file.managed:
        - name: /tmp/test.tar.gz
        - source: 'https://account:dontshowme@notahost.saltstack.io/files/test.tar.gz'
        - source_hash: 'https://account:dontshowme@notahost.saltstack.io/files/test.tar.gz.sha256'
    """
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.exitcode == 1
        assert ret.json
        assert (
            "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            in ret.json
        )
        assert (
            "comment"
            in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]
        )
        assert (
            "Unable to manage"
            in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]["comment"]
        )
        assert (
            "/files/test.tar.gz.sha256"
            in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]["comment"]
        )
        assert (
            "dontshowme"
            not in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]["comment"]
        )


@pytest.fixture
def min_patch_ver():
    return "2.6"


def _check_minimum_version(salt_call_cli, minimum_patch_ver):
    version = salt_call_cli.run("--local", "cmd.run", "patch --version")
    version = version.json.split()[2]
    if _LooseVersion(version) < _LooseVersion(minimum_patch_ver):
        pytest.xfail(
            "Minimum version of patch not found,"
            " expecting {}, found {}".format(minimum_patch_ver, version)
        )


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
def test_patch_single_file(salt_call_cli, min_patch_ver, patch_file_dest):
    """
    Test file.patch using a patch applied to a single file
    """
    _check_minimum_version(salt_call_cli, min_patch_ver)
    name_file = patch_file_dest / "name_file.txt"
    source_file = patch_file_dest / "source_file.patch"
    name_file_contents = """
    salt
    patch
    file
    """
    source_file_contents = """
    1,3c1,5
    < salt
    < patch
    < file
    ---
    > salt
    > will
    > patch
    > this
    > file
    """
    sls_contents = """
    do-patch:
      file.patch:
        - name: {name_file}
        - source: {source_file}
    """.format(
        name_file=name_file, source_file=source_file
    )
    sls_temp = pytest.helpers.temp_file("test_patch.sls", sls_contents, patch_file_dest)
    name_temp = pytest.helpers.temp_file(
        "name_file.txt", name_file_contents, patch_file_dest
    )
    source_temp = pytest.helpers.temp_file(
        "source_file.patch", source_file_contents, patch_file_dest
    )

    with sls_temp, name_temp, source_temp:
        # Store the original contents and make sure they change
        ret = salt_call_cli.run("state.apply", "test_patch")
        # Check to make sure the patch was applied okay
        assert ret.exitcode == 0

        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_directory(
    salt_call_cli,
    content,
    all_patch_file,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files.
    """
    _check_minimum_version(salt_call_cli, min_patch_ver)
    # Create a new unpatched set of files
    os.makedirs(patch_file_dest / "foo" / "bar")
    numbers_file = patch_file_dest / "foo" / "numbers.txt"
    math_file = patch_file_dest / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - strip: 1
        """.format(
        base_dir=patch_file_dest, all_patch=all_patch_file
    )

    sls_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_contents, patch_file_dest
    )
    numbers_tempfile = pytest.helpers.temp_file(
        numbers_file, content[0], patch_file_dest
    )
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], patch_file_dest)

    with sls_tempfile, numbers_tempfile, math_tempfile:
        # Run the state file
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json
        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_strip_parsing(
    salt_call_cli,
    content,
    all_patch_file,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test that we successfuly parse -p/--strip when included in the options
    """
    _check_minimum_version(salt_call_cli, min_patch_ver)
    # Create a new unpatched set of files
    os.makedirs(patch_file_dest / "foo" / "bar")
    numbers_file = patch_file_dest / "foo" / "numbers.txt"
    math_file = patch_file_dest / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - options: "-p1"
        """.format(
        base_dir=patch_file_dest, all_patch=all_patch_file
    )

    sls_patch_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - strip: 1
        """.format(
        base_dir=patch_file_dest, all_patch=all_patch_file
    )

    sls_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_contents, patch_file_dest
    )
    sls_patch_tempfile = pytest.helpers.temp_file(
        "test_patch_strip.sls", sls_patch_contents, patch_file_dest
    )
    numbers_tempfile = pytest.helpers.temp_file(
        numbers_file, content[0], patch_file_dest
    )
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], patch_file_dest)

    with sls_tempfile, sls_patch_tempfile, numbers_tempfile, math_tempfile:
        # Run the state using -p1
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state using --strip=1
        ret = salt_call_cli.run("state.apply", "test_patch_strip")
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_saltenv(
    salt_call_cli,
    content,
    math_patch_file,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test that we attempt to download the patch from a non-base saltenv
    """
    # This state will fail because we don't have a patch file in that
    # environment, but that is OK, we just want to test that we're looking
    # in an environment other than base.
    _check_minimum_version(salt_call_cli, min_patch_ver)
    # Create a new unpatched set of files
    os.makedirs(patch_file_dest / "foo" / "bar")
    math_file = patch_file_dest / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {math_file}
            - source: {math_patch}
            - saltenv: "prod"
        """.format(
        math_file=math_file, math_patch=math_patch_file
    )
    sls_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_contents, patch_file_dest
    )
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], patch_file_dest)

    with sls_tempfile, math_tempfile:
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 1
        assert ret.json

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is False
        assert state_run[
            "comment"
        ] == "Source file {} not found in saltenv 'prod'".format(math_patch_file)


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_single_file_failure(
    salt_call_cli,
    content,
    numbers_patch_file,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test file.patch using a patch applied to a single file. This tests a
    failed patch.
    """
    _check_minimum_version(salt_call_cli, min_patch_ver)
    # Create a new unpatched set of files
    os.makedirs(patch_file_dest / "foo" / "bar")
    numbers_file = patch_file_dest / "foo" / "numbers.txt"
    math_file = patch_file_dest / "foo" / "bar" / "math.txt"
    reject_file = patch_file_dest / "reject.txt"

    sls_patch_contents = """
        do-patch:
          file.patch:
            - name: {numbers_file}
            - source: {numbers_patch}
        """.format(
        numbers_file=numbers_file, numbers_patch=numbers_patch_file
    )
    sls_patch_reject_contents = """
        do-patch:
          file.patch:
            - name: {numbers_file}
            - source: {numbers_patch}
            - reject_file: {reject_file}
            - strip: 1
        """.format(
        numbers_file=numbers_file,
        numbers_patch=numbers_patch_file,
        reject_file=reject_file,
    )

    sls_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_patch_contents, patch_file_dest
    )
    sls_reject_tempfile = pytest.helpers.temp_file(
        "test_patch_reject.sls", sls_patch_reject_contents, patch_file_dest
    )
    numbers_tempfile = pytest.helpers.temp_file(
        numbers_file, content[0], patch_file_dest
    )
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], patch_file_dest)
    reject_tempfile = pytest.helpers.temp_file("reject.txt", "", patch_file_dest)

    with sls_tempfile, sls_reject_tempfile, numbers_tempfile, math_tempfile, reject_tempfile:
        # Empty the file to ensure that the patch doesn't apply cleanly
        with salt.utils.files.fopen(numbers_file, "w"):
            pass

        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 1
        assert ret.json
        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is False
        assert "Patch would not apply cleanly" in state_run["comment"]

        # Test the reject_file option and ensure that the rejects are written
        # to the path specified.
        ret = salt_call_cli.run("state.apply", "test_patch_reject")
        assert ret.exitcode == 1
        assert ret.json

        state_run = next(iter(ret.json.values()))
        assert "Patch would not apply cleanly" in state_run["comment"]
        assert (
            re.match(
                state_run["comment"], "saving rejects to (file )?{}".format(reject_file)
            )
            is None
        )


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_directory_failure(
    salt_call_cli,
    content,
    all_patch_file,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files.
    """
    _check_minimum_version(salt_call_cli, min_patch_ver)
    # Create a new unpatched set of files
    os.makedirs(patch_file_dest / "foo" / "bar")
    numbers_file = patch_file_dest / "foo" / "numbers.txt"
    math_file = patch_file_dest / "foo" / "bar" / "math.txt"
    reject_file = patch_file_dest / "reject.txt"

    sls_patch_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - strip: 1
        """.format(
        base_dir=patch_file_dest, all_patch=all_patch_file
    )
    sls_patch_reject_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - reject_file: {reject_file}
            - strip: 1
        """.format(
        base_dir=patch_file_dest, all_patch=all_patch_file, reject_file=reject_file
    )
    sls_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_patch_contents, patch_file_dest
    )
    sls_reject_tempfile = pytest.helpers.temp_file(
        "test_patch_reject.sls", sls_patch_reject_contents, patch_file_dest
    )

    numbers_tempfile = pytest.helpers.temp_file(
        numbers_file, content[0], patch_file_dest
    )
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], patch_file_dest)
    reject_tempfile = pytest.helpers.temp_file("reject.txt", "", patch_file_dest)

    with sls_tempfile, sls_reject_tempfile, numbers_tempfile, math_tempfile, reject_tempfile:
        # Empty the file to ensure that the patch doesn't apply cleanly
        with salt.utils.files.fopen(math_file, "w"):
            pass

        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 1
        assert ret.json
        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is False
        assert "Patch would not apply cleanly" in state_run["comment"]

        # Test the reject_file option and ensure that the rejects are written
        # to the path specified.
        ret = salt_call_cli.run("state.apply", "test_patch_reject")
        assert ret.exitcode == 1
        assert ret.json

        state_run = next(iter(ret.json.values()))
        assert "Patch would not apply cleanly" in state_run["comment"]
        assert (
            re.match(
                state_run["comment"], "saving rejects to (file )?{}".format(reject_file)
            )
            is None
        )


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_single_file_template(
    salt_call_cli,
    context,
    content,
    numbers_patch_template,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test file.patch using a patch applied to a single file, with jinja
    templating applied to the patch file.
    """
    # Create a new unpatched set of files
    _check_minimum_version(salt_call_cli, min_patch_ver)

    os.makedirs(patch_file_dest / "foo" / "bar", exist_ok=True)
    numbers_file = patch_file_dest / "foo" / "numbers.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {numbers_file}
            - source: {numbers_patch_template}
            - template: "jinja"
            - context: {context}
        """.format(
        numbers_file=numbers_file,
        numbers_patch_template=numbers_patch_template,
        context=context,
    )

    sls_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_contents, patch_file_dest
    )
    numbers_tempfile = pytest.helpers.temp_file(
        numbers_file, content[0], patch_file_dest
    )

    with sls_tempfile, numbers_tempfile:
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_directory_template(
    salt_call_cli,
    context,
    content,
    all_patch_template,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files, and with jinja templating applied to the patch
    file.
    """
    # Create a new unpatched set of files
    _check_minimum_version(salt_call_cli, min_patch_ver)
    os.makedirs(patch_file_dest / "foo" / "bar", exist_ok=True)
    numbers_file = patch_file_dest / "foo" / "numbers.txt"
    math_file = patch_file_dest / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch_template}
            - template: "jinja"
            - context: {context}
        """.format(
        base_dir=patch_file_dest, all_patch_template=all_patch_template, context=context
    )

    sls_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_contents, patch_file_dest
    )
    numbers_tempfile = pytest.helpers.temp_file(
        numbers_file, content[0], patch_file_dest
    )
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], patch_file_dest)

    with sls_tempfile, numbers_tempfile, math_tempfile:
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skipif(not salt.utils.path.which("patch"), reason="patch is not installed")
def test_patch_test_mode(
    salt_call_cli,
    content,
    numbers_patch_file,
    min_patch_ver,
    patch_file_dest,
):
    """
    Test file.patch using test=True
    """
    _check_minimum_version(salt_call_cli, min_patch_ver)
    # Create a new unpatched set of files
    os.makedirs(patch_file_dest / "foo" / "bar")
    numbers_file = patch_file_dest / "foo" / "numbers.txt"

    sls_patch_contents = """
        do-patch:
          file.patch:
            - name: {numbers_file}
            - source: {numbers_patch}
        """.format(
        numbers_file=numbers_file, numbers_patch=numbers_patch_file
    )

    sls_patch_tempfile = pytest.helpers.temp_file(
        "test_patch.sls", sls_patch_contents, patch_file_dest
    )
    numbers_tempfile = pytest.helpers.temp_file(
        numbers_file, content[0], patch_file_dest
    )

    with sls_patch_tempfile, numbers_tempfile:
        # Test application with test=True mode
        ret = salt_call_cli.run("state.apply", "test_patch", test=True)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is None
        assert state_run["comment"] == "The patch would be applied"

        # Apply the patch for real. We'll then be able to test below that we
        # exit with a True rather than a None result if test=True is used on an
        # already-applied patch.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.exitcode == 0
        assert ret.json

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Run again with test=True. Since the pre-check happens before we do
        # the __opts__['test'] check, we should exit with a True result just
        # the same as if we try to run this state on an already-patched file
        # *without* test=True.
        ret = salt_call_cli.run("state.apply", "test_patch", test=True)
        assert ret.exitcode == 0
        assert ret.json

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"

        # Empty the file to ensure that the patch doesn't apply cleanly
        with salt.utils.files.fopen(numbers_file, "w"):
            pass

        # Run again with test=True. Similar to the above run, we are testing
        # that we return before we reach the __opts__['test'] check. In this
        # case we should return a False result because we should already know
        # by this point that the patch will not apply cleanly.
        ret = salt_call_cli.run("state.apply", "test_patch", test=True)
        assert ret.exitcode == 1
        assert ret.json

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is False
        assert "Patch would not apply cleanly" in state_run["comment"]

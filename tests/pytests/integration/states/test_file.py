"""
Tests for the file state
"""

import logging
import os
import pathlib
import re
import stat
import subprocess
import textwrap

import pytest
from pytestshellutils.utils import ports

import salt.utils.files
import salt.utils.path
import salt.utils.platform
from salt.utils.versions import Version
from tests.conftest import FIPS_TESTRUN

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
def all_patch_file(salt_master):
    contents = """
    diff -ur a/foo/bar/math.txt b/foo/bar/math.txt
    --- a/foo/bar/math.txt	2018-04-09 18:43:52.883205365 -0500
    +++ b/foo/bar/math.txt	2018-04-09 18:44:58.525061654 -0500
    @@ -1,3 +1,3 @@
    -Five plus five is ten
    +5 + 5 = 10

    -Four squared is sixteen
    +4² = 16
    diff -ur a/foo/numbers.txt b/foo/numbers.txt
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
    patch_filename = "all.patch"
    with salt_master.state_tree.base.temp_file(f"patches/{patch_filename}", contents):
        yield f"salt://patches/{patch_filename}"


@pytest.fixture
def numbers_patch_file(salt_master):
    contents = """
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
    patch_filename = "numbers.patch"
    with salt_master.state_tree.base.temp_file(f"patches/{patch_filename}", contents):
        yield f"salt://patches/{patch_filename}"


@pytest.fixture
def math_patch_file(salt_master):
    contents = """
    --- a/foo/bar/math.txt	2018-04-09 18:43:52.883205365 -0500
    +++ b/foo/bar/math.txt	2018-04-09 18:44:58.525061654 -0500
    @@ -1,3 +1,3 @@
    -Five plus five is ten
    +5 + 5 = 10

    -Four squared is sixteen
    +4² = 16
    """
    patch_filename = "math.patch"
    with salt_master.state_tree.base.temp_file(f"patches/{patch_filename}", contents):
        yield f"salt://patches/{patch_filename}"


@pytest.fixture
def numbers_patch_template(salt_master):
    contents = """
    --- a/foo/numbers.txt	2018-04-09 18:43:58.014272504 -0500
    +++ b/foo/numbers.txt	2018-04-09 18:44:46.487905044 -0500
    @@ -1,7 +1,7 @@
    -one
    -two
     three
    +{{ two }}
    +one

    -1
    -2
     3
    +2
    +1
    """
    patch_filename = "numbers.patch.jinja"
    with salt_master.state_tree.base.temp_file(f"patches/{patch_filename}", contents):
        yield f"salt://patches/{patch_filename}"


@pytest.fixture
def all_patch_template(salt_master):
    contents = """
    diff -ur a/foo/bar/math.txt b/foo/bar/math.txt
    --- a/foo/bar/math.txt	2018-04-09 18:43:52.883205365 -0500
    +++ b/foo/bar/math.txt	2018-04-09 18:44:58.525061654 -0500
    @@ -1,3 +1,3 @@
    -Five plus five is ten
    +5 + 5 = {{ ten }}

    -Four squared is sixteen
    +4² = 16
    diff -ur a/foo/numbers.txt b/foo/numbers.txt
    --- a/foo/numbers.txt	2018-04-09 18:43:58.014272504 -0500
    +++ b/foo/numbers.txt	2018-04-09 18:44:46.487905044 -0500
    @@ -1,7 +1,7 @@
    -one
    -two
     three
    +{{ two }}
    +one

    -1
    -2
     3
    +2
    +1
    """
    patch_filename = "all.patch.jinja"
    with salt_master.state_tree.base.temp_file(f"patches/{patch_filename}", contents):
        yield f"salt://patches/{patch_filename}"


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
            assert ret.returncode == 0
            assert ret.data is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True


@pytest.fixture(scope="module")
def salt_secondary_master(request, salt_factories):
    #
    # Enable a secondary Salt master so we can disable follow_symlinks
    #
    publish_port = ports.get_unused_localhost_port()
    ret_port = ports.get_unused_localhost_port()

    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "fileserver_followsymlinks": False,
        "publish_port": publish_port,
        "ret_port": ret_port,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }

    factory = salt_factories.salt_master_daemon(
        "secondary-master",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="module")
def salt_secondary_minion(salt_secondary_master):
    #
    # Enable a secondary Salt minion so we can
    # point it at athe secondary Salt master
    #
    config_defaults = {}
    config_overrides = {
        "master": salt_secondary_master.config["interface"],
        "master_port": salt_secondary_master.config["ret_port"],
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }

    factory = salt_secondary_master.salt_minion_daemon(
        "secondary-minion",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="module")
def salt_cli_secondary_wrapper(salt_secondary_master, salt_secondary_minion):
    def run_command(*command, **kwargs):
        salt_cli = salt_secondary_master.salt_cli()
        return salt_cli.run(*command, minion_tgt=salt_secondary_minion.id, **kwargs)

    return run_command


@pytest.mark.usefixtures("pillar_tree")
def test_contents_pillar_with_pillar_list(salt_master, salt_call_cli, tmp_path):
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
        f"{sls_name}.sls", sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.sls", sls_name)
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()


@pytest.mark.usefixtures("pillar_tree")
def test_managed_file_with_pillar_sls(salt_master, salt_call_cli, tmp_path):
    """
    Test to ensure pillar data in sls file
    is rendered properly and file is created.
    """
    ret = salt_call_cli.run("pillar.get", "monty")
    assert ret.returncode == 0
    assert ret.data

    target_path = tmp_path / f"file-pillar-{ret.data}-target.txt"
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
        f"{sls_name}.sls", sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.sls", sls_name)
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()


@pytest.mark.usefixtures("pillar_tree")
def test_issue_50221(
    salt_master,
    salt_call_cli,
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
        f"{sls_name}.sls", sls_contents
    )
    issue_50221_ext_pillar_tempfile = pytest.helpers.temp_file(
        "issue-50221",
        expected_content,
        ext_pillar_file_tree_root_dir / "hosts" / salt_minion.id,
    )
    with sls_tempfile, issue_50221_ext_pillar_tempfile:
        ret = salt_call_cli.run("pillar.get", "issue-50221")
        assert ret.returncode == 0
        assert ret.data
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert ret.data.replace("\r\n", "\n") == expected_content
        ret = salt_call_cli.run(
            "state.apply", sls_name, pillar={"target-path": str(target_path)}
        )
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert target_path.read_text().replace("\r\n", "\n") == expected_content


@pytest.fixture
def _check_min_patch_version(shell):
    min_patch_ver = "2.6"
    ret = shell.run("patch", "--version")
    assert ret.returncode == 0
    version = ret.stdout.strip().split()[2]
    if Version(version) < Version(min_patch_ver):
        pytest.xfail(
            "Minimum version of patch not found, expecting {}, found {}".format(
                min_patch_ver, version
            )
        )


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_single_file(salt_call_cli, salt_master, tmp_path):
    """
    Test file.patch using a patch applied to a single file
    """
    name_file = tmp_path / "name_file.txt"
    source_file = tmp_path / "source_file.patch"
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
    sls_temp = salt_master.state_tree.base.temp_file("test_patch.sls", sls_contents)
    name_temp = pytest.helpers.temp_file("name_file.txt", name_file_contents, tmp_path)
    source_temp = pytest.helpers.temp_file(
        "source_file.patch", source_file_contents, tmp_path
    )

    with sls_temp, name_temp, source_temp:
        # Store the original contents and make sure they change
        ret = salt_call_cli.run("state.apply", "test_patch")
        # Check to make sure the patch was applied okay
        assert ret.returncode == 0

        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_directory(salt_call_cli, content, all_patch_file, salt_master, tmp_path):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files.
    """
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar")
    numbers_file = tmp_path / "foo" / "numbers.txt"
    math_file = tmp_path / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - strip: 1
        """.format(
        base_dir=tmp_path, all_patch=all_patch_file
    )

    sls_tempfile = salt_master.state_tree.base.temp_file("test_patch.sls", sls_contents)
    numbers_tempfile = pytest.helpers.temp_file(numbers_file, content[0], tmp_path)
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], tmp_path)

    with sls_tempfile, numbers_tempfile, math_tempfile:
        # Run the state file
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data
        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_strip_parsing(
    salt_call_cli, content, all_patch_file, salt_master, tmp_path
):
    """
    Test that we successfuly parse -p/--strip when included in the options
    """
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar")
    numbers_file = tmp_path / "foo" / "numbers.txt"
    math_file = tmp_path / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - options: "-p1"
        """.format(
        base_dir=tmp_path, all_patch=all_patch_file
    )

    sls_patch_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - strip: 1
        """.format(
        base_dir=tmp_path, all_patch=all_patch_file
    )

    sls_tempfile = salt_master.state_tree.base.temp_file("test_patch.sls", sls_contents)
    sls_patch_tempfile = salt_master.state_tree.base.temp_file(
        "test_patch_strip.sls", sls_patch_contents
    )
    numbers_tempfile = pytest.helpers.temp_file(numbers_file, content[0], tmp_path)
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], tmp_path)

    with sls_tempfile, sls_patch_tempfile, numbers_tempfile, math_tempfile:
        # Run the state using -p1
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state using --strip=1
        ret = salt_call_cli.run("state.apply", "test_patch_strip")
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_saltenv(salt_call_cli, content, math_patch_file, salt_master, tmp_path):
    """
    Test that we attempt to download the patch from a non-base saltenv
    """
    # This state will fail because we don't have a patch file in that
    # environment, but that is OK, we just want to test that we're looking
    # in an environment other than base.
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar")
    math_file = tmp_path / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {math_file}
            - source: {math_patch}
            - saltenv: "prod"
        """.format(
        math_file=math_file, math_patch=math_patch_file
    )
    sls_tempfile = salt_master.state_tree.base.temp_file("test_patch.sls", sls_contents)
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], tmp_path)

    with sls_tempfile, math_tempfile:
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 1
        assert ret.data

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is False
        assert (
            state_run["comment"]
            == f"Source file {math_patch_file} not found in saltenv 'prod'"
        )


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_single_file_failure(
    salt_call_cli, content, numbers_patch_file, salt_master, tmp_path
):
    """
    Test file.patch using a patch applied to a single file. This tests a
    failed patch.
    """
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar")
    numbers_file = tmp_path / "foo" / "numbers.txt"
    math_file = tmp_path / "foo" / "bar" / "math.txt"
    reject_file = tmp_path / "reject.txt"

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

    sls_tempfile = salt_master.state_tree.base.temp_file(
        "test_patch.sls", sls_patch_contents
    )
    sls_reject_tempfile = salt_master.state_tree.base.temp_file(
        "test_patch_reject.sls", sls_patch_reject_contents
    )
    numbers_tempfile = pytest.helpers.temp_file(numbers_file, content[0], tmp_path)
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], tmp_path)
    reject_tempfile = pytest.helpers.temp_file("reject.txt", "", tmp_path)

    with (
        sls_tempfile
    ), sls_reject_tempfile, numbers_tempfile, math_tempfile, reject_tempfile:
        # Empty the file to ensure that the patch doesn't apply cleanly
        with salt.utils.files.fopen(numbers_file, "w"):
            pass

        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 1
        assert ret.data
        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is False
        assert "Patch would not apply cleanly" in state_run["comment"]

        # Test the reject_file option and ensure that the rejects are written
        # to the path specified.
        ret = salt_call_cli.run("state.apply", "test_patch_reject")
        assert ret.returncode == 1
        assert ret.data

        state_run = next(iter(ret.data.values()))
        assert "Patch would not apply cleanly" in state_run["comment"]
        assert (
            re.match(state_run["comment"], f"saving rejects to (file )?{reject_file}")
            is None
        )


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_directory_failure(
    salt_call_cli, content, all_patch_file, salt_master, tmp_path
):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files.
    """
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar")
    numbers_file = tmp_path / "foo" / "numbers.txt"
    math_file = tmp_path / "foo" / "bar" / "math.txt"
    reject_file = tmp_path / "reject.txt"

    sls_patch_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - strip: 1
        """.format(
        base_dir=tmp_path, all_patch=all_patch_file
    )
    sls_patch_reject_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch}
            - reject_file: {reject_file}
            - strip: 1
        """.format(
        base_dir=tmp_path, all_patch=all_patch_file, reject_file=reject_file
    )
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "test_patch.sls", sls_patch_contents
    )
    sls_reject_tempfile = salt_master.state_tree.base.temp_file(
        "test_patch_reject.sls", sls_patch_reject_contents
    )

    numbers_tempfile = pytest.helpers.temp_file(numbers_file, content[0], tmp_path)
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], tmp_path)
    reject_tempfile = pytest.helpers.temp_file("reject.txt", "", tmp_path)

    with (
        sls_tempfile
    ), sls_reject_tempfile, numbers_tempfile, math_tempfile, reject_tempfile:
        # Empty the file to ensure that the patch doesn't apply cleanly
        with salt.utils.files.fopen(math_file, "w"):
            pass

        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 1
        assert ret.data
        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is False
        assert "Patch would not apply cleanly" in state_run["comment"]

        # Test the reject_file option and ensure that the rejects are written
        # to the path specified.
        ret = salt_call_cli.run("state.apply", "test_patch_reject")
        assert ret.returncode == 1
        assert ret.data

        state_run = next(iter(ret.data.values()))
        assert "Patch would not apply cleanly" in state_run["comment"]
        assert (
            re.match(state_run["comment"], f"saving rejects to (file )?{reject_file}")
            is None
        )


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_single_file_template(
    salt_call_cli, context, content, numbers_patch_template, salt_master, tmp_path
):
    """
    Test file.patch using a patch applied to a single file, with jinja
    templating applied to the patch file.
    """
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar", exist_ok=True)
    numbers_file = tmp_path / "foo" / "numbers.txt"

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

    sls_tempfile = salt_master.state_tree.base.temp_file("test_patch.sls", sls_contents)
    numbers_tempfile = pytest.helpers.temp_file(numbers_file, content[0], tmp_path)

    with sls_tempfile, numbers_tempfile:
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_directory_template(
    salt_call_cli, context, content, all_patch_template, salt_master, tmp_path
):
    """
    Test file.patch using a patch applied to a directory, with changes
    spanning multiple files, and with jinja templating applied to the patch
    file.
    """
    if salt.utils.platform.is_windows() and os.environ.get("PYTHONUTF8", "0") == "0":
        pytest.skip("Test will fail if PYTHONUTF8=1 is not set on windows")
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar", exist_ok=True)
    numbers_file = tmp_path / "foo" / "numbers.txt"
    math_file = tmp_path / "foo" / "bar" / "math.txt"

    sls_contents = """
        do-patch:
          file.patch:
            - name: {base_dir}
            - source: {all_patch_template}
            - template: "jinja"
            - context: {context}
            - strip: 1
        """.format(
        base_dir=tmp_path, all_patch_template=all_patch_template, context=context
    )

    sls_tempfile = salt_master.state_tree.base.temp_file("test_patch.sls", sls_contents)
    numbers_tempfile = pytest.helpers.temp_file(numbers_file, content[0], tmp_path)
    math_tempfile = pytest.helpers.temp_file(math_file, content[1], tmp_path)

    with sls_tempfile, numbers_tempfile, math_tempfile:
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch was already applied"
        assert state_run["changes"] == {}


@pytest.mark.skip_unless_on_windows
@pytest.mark.skip_if_binaries_missing("patch")
@pytest.mark.usefixtures("_check_min_patch_version")
def test_patch_test_mode(
    salt_call_cli,
    content,
    numbers_patch_file,
    tmp_path,
    salt_master,
):
    """
    Test file.patch using test=True
    """
    # Create a new unpatched set of files
    os.makedirs(tmp_path / "foo" / "bar")
    numbers_file = tmp_path / "foo" / "numbers.txt"

    sls_patch_contents = """
        do-patch:
          file.patch:
            - name: {numbers_file}
            - source: {numbers_patch}
        """.format(
        numbers_file=numbers_file, numbers_patch=numbers_patch_file
    )

    sls_patch_tempfile = salt_master.state_tree.base.temp_file(
        "test_patch.sls", sls_patch_contents
    )
    numbers_tempfile = pytest.helpers.temp_file(numbers_file, content[0], tmp_path)

    with sls_patch_tempfile, numbers_tempfile:
        # Test application with test=True mode
        ret = salt_call_cli.run("state.apply", "test_patch", test=True)
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is None
        assert state_run["comment"] == "The patch would be applied"

        # Apply the patch for real. We'll then be able to test below that we
        # exit with a True rather than a None result if test=True is used on an
        # already-applied patch.
        ret = salt_call_cli.run("state.apply", "test_patch")
        assert ret.returncode == 0
        assert ret.data

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Patch successfully applied"

        # Run again with test=True. Since the pre-check happens before we do
        # the __opts__['test'] check, we should exit with a True result just
        # the same as if we try to run this state on an already-patched file
        # *without* test=True.
        ret = salt_call_cli.run("state.apply", "test_patch", test=True)
        assert ret.returncode == 0
        assert ret.data

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
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
        assert ret.returncode == 1
        assert ret.data

        # Check to make sure the patch was applied okay
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is False
        assert "Patch would not apply cleanly" in state_run["comment"]


@pytest.mark.usefixtures("pillar_tree")
def test_recurse(
    salt_master,
    salt_call_cli,
    tmp_path,
    salt_minion,
):
    target_path = tmp_path / "test_recurse"

    sls_name = "file_recurse_test"
    sls_contents = """
    tmp_recurse_dir_dir:
      file.recurse:
        - name: {target_path}
        - source: salt://tmp_dir/
        - keep_symlinks: True
    """.format(
        target_path=target_path
    )

    test_tempdir = salt_master.state_tree.base.write_path / "tmp_dir"
    test_tempdir.mkdir(parents=True, exist_ok=True)
    sls_tempfile = salt_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )

    with sls_tempfile:
        for _dir in "test1", "test2", "test3":
            test_tempdir.joinpath(_dir).mkdir(parents=True, exist_ok=True)

            for _file in range(1, 4):
                test_tempdir.joinpath(_dir, str(_file)).touch()

        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True

        # Check to make sure the directories and files were created
        for _dir in "test1", "test2", "test3":
            assert test_tempdir.joinpath(_dir).is_dir()
            for _file in range(1, 4):
                assert test_tempdir.joinpath(_dir, str(_file)).is_file()


@pytest.mark.skip_on_windows
@pytest.mark.usefixtures("pillar_tree")
def test_recurse_keep_symlinks_in_fileserver_root(
    salt_master,
    salt_call_cli,
    tmp_path,
    salt_minion,
):
    target_path = tmp_path / "test_recurse"

    sls_name = "file_recurse_test"
    sls_contents = """
    tmp_recurse_dir_dir:
      file.recurse:
        - name: {target_path}
        - source: salt://tmp_dir/
        - keep_symlinks: True
    """.format(
        target_path=target_path
    )

    test_tempdir = salt_master.state_tree.base.write_path / "tmp_dir"
    test_tempdir.mkdir(parents=True, exist_ok=True)
    sls_tempfile = salt_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )

    with sls_tempfile:
        for _dir in "test1", "test2", "test3":
            test_tempdir.joinpath(_dir).mkdir(parents=True, exist_ok=True)

            for _file in range(1, 4):
                test_tempdir.joinpath(_dir, str(_file)).touch()

        with pytest.helpers.change_cwd(str(test_tempdir)):
            pathlib.Path("test").symlink_to("test3", target_is_directory=True)

        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True

        # Check to make sure the directories and files were created
        for _dir in "test1", "test2", "test3":
            assert target_path.joinpath(_dir).is_dir()
            for _file in range(1, 4):
                assert target_path.joinpath(_dir, str(_file)).is_file()

        assert target_path.joinpath("test").is_symlink()


@pytest.mark.skip_on_windows
@pytest.mark.usefixtures("pillar_tree")
def test_recurse_keep_symlinks_outside_fileserver_root(
    salt_secondary_minion,
    salt_secondary_master,
    salt_cli_secondary_wrapper,
    tmp_path,
):
    target_path = tmp_path / "test_recurse"

    sls_name = "file_recurse_test"
    sls_contents = """
    tmp_recurse_dir_dir:
      file.recurse:
        - name: {target_path}
        - source: salt://tmp_dir/
        - keep_symlinks: True
    """.format(
        target_path=target_path
    )

    test_tempdir = salt_secondary_master.state_tree.base.write_path / "tmp_dir"
    test_tempdir.mkdir(parents=True, exist_ok=True)
    sls_tempfile = salt_secondary_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )

    with sls_tempfile:
        for _dir in "test1", "test2", "test3":
            test_tempdir.joinpath(_dir).mkdir(parents=True, exist_ok=True)

            for _file in range(1, 4):
                test_tempdir.joinpath(_dir, str(_file)).touch()

        with pytest.helpers.change_cwd(str(test_tempdir)):
            pathlib.Path("/tmp/test_recurse_outside").mkdir(parents=True, exist_ok=True)
            pathlib.Path("test4").symlink_to(
                "/tmp/test_recurse_outside", target_is_directory=True
            )

        ret = salt_cli_secondary_wrapper("state.apply", sls_name)
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True

        # Check to make sure the directories and files were created
        for _dir in "test1", "test2", "test3":
            assert target_path.joinpath(_dir).is_dir()
            for _file in range(1, 4):
                assert target_path.joinpath(_dir, str(_file)).is_file()

        assert target_path.joinpath("test4").is_symlink()


@pytest.mark.usefixtures("pillar_tree")
def test_issue_62117(
    salt_master,
    salt_call_cli,
    tmp_path,
    salt_minion,
):
    name = "test_jinja/issue-62117"

    yaml_contents = "{%- set grains = grains.get('os', '') %}"

    jinja_contents = '{%- import_yaml "./issue-62117.yaml" as grains %}'

    sls_contents = """
    {%- from "./issue-62117.jinja" import grains with context %}

    test_jinja/issue-62117/cmd.run:
      cmd.run:
        - name: pwd
    """

    yaml_tempfile = salt_master.state_tree.base.temp_file(f"{name}.yaml", yaml_contents)

    jinja_tempfile = salt_master.state_tree.base.temp_file(
        f"{name}.jinja", jinja_contents
    )

    sls_tempfile = salt_master.state_tree.base.temp_file(f"{name}.sls", sls_contents)

    with yaml_tempfile, jinja_tempfile, sls_tempfile:
        ret = salt_call_cli.run("--local", "state.apply", name.replace("/", "."))
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True


@pytest.mark.usefixtures("pillar_tree")
def test_issue_62611(
    salt_master,
    salt_call_cli,
    tmp_path,
    salt_minion,
):
    name = "test_jinja/issue-62611"

    jinja_contents = '{% set myvar = "MOOP" -%}'

    jinja_file = salt_master.state_tree.base.write_path / f"{name}.jinja"
    if salt.utils.platform.is_windows():
        jinja_file = str(jinja_file).replace("\\", "\\\\")

    sls_contents = """
    {%- from "REPLACEME" import myvar with context %}

    test_jinja/issue-62611/cmd.run:
      cmd.run:
        - name: echo MEEP {{ myvar }}
    """.replace(
        "REPLACEME", str(jinja_file)
    )

    jinja_tempfile = salt_master.state_tree.base.temp_file(
        f"{name}.jinja", jinja_contents
    )

    sls_tempfile = salt_master.state_tree.base.temp_file(f"{name}.sls", sls_contents)

    with jinja_tempfile, sls_tempfile:
        ret = salt_call_cli.run("--local", "state.apply", name.replace("/", "."))
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["name"] == "echo MEEP MOOP"
        assert state_run["result"] is True


def test_state_skip_req(
    salt_master,
    salt_call_cli,
    tmp_path,
    salt_minion,
):
    target_path = tmp_path / "skip-req-file-target.txt"
    target_path.write_text(
        textwrap.dedent(
            """
            foo=bar
            # some comment
            fizz=buzz
            """
        )
    )
    name = "test_skip_req/skip_req"

    sls_contents = """
    modify_contents_with_ignore_params_to_skip:
      file.managed:
        - name: {}
        - ignore_ordering: True
        - ignore_whitespace: True
        - ignore_comment_characters: '#'
        - contents: |
            fizz=buzz
            foo=bar

    this_req_should_not_trigger:
      cmd.run:
        - name: echo NEVER
        - onchanges:
          - file: modify_contents_with_ignore_params_to_skip
    """.format(
        target_path
    )

    sls_tempfile = salt_master.state_tree.base.temp_file(f"{name}.sls", sls_contents)

    with sls_tempfile:
        ret = salt_call_cli.run("state.apply", name.replace("/", "."))
        assert ret.returncode == 0
        assert ret.data
        state_runs = list(ret.data.values())
        # file.managed returns changes but doesn't trigger reqs
        assert state_runs[0]["name"] == str(target_path)
        assert state_runs[0]["result"] is True
        assert state_runs[0]["changes"]
        assert state_runs[0]["skip_req"] is True
        # cmd.run is not run
        assert state_runs[1]["name"] == "echo NEVER"
        assert state_runs[1]["result"] is True
        assert not state_runs[1]["changes"]
        assert (
            state_runs[1]["comment"]
            == "State was not run because requisites were skipped by another state"
        )


def test_contents_file(salt_master, salt_call_cli, tmp_path):
    """
    test calling file.managed multiple times
    with salt-call
    """
    target_path = tmp_path / "add-contents-file.txt"
    sls_name = "file-contents"
    sls_contents = """
    add_contents_file_sls:
      file.managed:
        - name: {}
        - contents: 1234
    """.format(
        target_path
    )
    sls_tempfile = salt_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )
    with sls_tempfile:
        for i in range(1, 4):
            ret = salt_call_cli.run("state.sls", sls_name)
            assert ret.returncode == 0
            assert ret.data
            state_run = next(iter(ret.data.values()))
            assert state_run["result"] is True
            # Check to make sure the file was created
            assert target_path.is_file()


@pytest.mark.skip_on_windows
def test_directory_recurse(salt_master, salt_call_cli, tmp_path, grains):
    """
    Test modifying ownership of symlink without affecting the link target's
    permissions.
    """
    target_dir = tmp_path / "test-dir"
    target_dir.mkdir()

    target_file = target_dir / "test-file"
    target_file.write_text("this is a test file")

    target_link = target_dir / "test-link"
    target_link.symlink_to(target_file)

    # Change the ownership of the sybolic link to 'nobody'
    ret = subprocess.run(["chown", "-h", "nobody", str(target_link)], check=False)
    assert ret.returncode == 0

    file_perms = stat.S_IFREG | stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP
    if grains["os"] != "VMware Photon OS":
        file_perms |= stat.S_IROTH

    # The permissions of the file should be 644.
    assert target_file.stat().st_mode == file_perms

    sls_name = "test"
    sls_contents = f"""
    {target_dir}:
      file.directory:
        - user: root
        - recurse:
          - user
    """
    sls_tempfile = salt_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.sls", sls_name)
        key = f"file_|-{target_dir}_|-{target_dir}_|-directory"
        assert key in ret.json
        result = ret.json[key]
        assert "changes" in result and result["changes"]

    # Permissions of file should not have changed.
    assert target_file.stat().st_mode == file_perms
